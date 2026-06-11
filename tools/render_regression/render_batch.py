#!/usr/bin/env python3
"""A8 批渲驱动（M1a/M1b 验收工具，后并入 D2）。

对冻结清单（corpus_manifest_*.json）或构造样张目录逐张调用渲染服务
`POST /render`，断言：
  1. 逐张得到 图像 或 结构化错误（HTTP 信封含 error_code）；
  2. 图像尺寸 == 请求尺寸；
  3. 非空白（墨迹像素占比 >= --min-ink；例外清单内的样张跳过此项并记录
     —— 垃圾-extents 类在 B5 落地前的 plan 例外）；
  4. （清单模式）文件 sha256 与冻结清单一致（语料完整性）。

预期文件（--expectations，JSON，可选）：{"<file_name>": "image" | "error" |
"blank-ok"}，缺省 "image"。

退出码：0 全过；1 存在 gate 失败；2 用法/环境错误。
报告：--report 输出 JSON（私有存储，遵守 D0 治理——不进公共 CI 工件）。
"""

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    print("httpx required: pip install httpx", file=sys.stderr)
    sys.exit(2)

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ink_fraction(png_bytes: bytes) -> float:
    """Fraction of pixels that differ from the dominant (background) color."""
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    small = img.resize((min(img.width, 1200), min(img.height, 850)))
    colors = small.getcolors(maxcolors=small.width * small.height)
    dominant = max(colors, key=lambda c: c[0])
    total = small.width * small.height
    return 1.0 - dominant[0] / float(total)


def iter_inputs(args):
    if args.manifest:
        doc = json.loads(Path(args.manifest).read_text("utf-8"))
        base = Path(args.dir) if args.dir else Path(doc["source_dir"]).expanduser()
        for item in doc["files"]:
            yield base / item["file_name"], item["sha256"]
    else:
        for p in sorted(Path(args.samples).glob("*.dxf")):
            yield p, None


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest", help="冻结清单 JSON（corpus_manifest_dxf.json）")
    src.add_argument("--samples", help="构造样张目录（*.dxf）")
    ap.add_argument("--dir", help="覆盖清单 source_dir")
    ap.add_argument("--base-url", default="http://127.0.0.1:8077")
    ap.add_argument("--width", type=int, default=2400)
    ap.add_argument("--height", type=int, default=1697)
    ap.add_argument("--bg", default="dark")
    ap.add_argument("--min-ink", type=float, default=0.0005)
    ap.add_argument("--exceptions", help="例外清单 JSON：[{file_name, reason}]（blank 检查豁免）")
    ap.add_argument("--expectations", help="预期 JSON：{file_name: image|error|blank-ok}")
    ap.add_argument("--report", help="输出报告 JSON 路径（私有存储）")
    args = ap.parse_args()

    if Image is None:
        print("Pillow required for blank checks: pip install Pillow", file=sys.stderr)
        return 2

    exceptions = {}
    if args.exceptions:
        for item in json.loads(Path(args.exceptions).read_text("utf-8")):
            exceptions[item["file_name"]] = item.get("reason", "")
    expectations = {}
    if args.expectations:
        expectations = json.loads(Path(args.expectations).read_text("utf-8"))

    client = httpx.Client(base_url=args.base_url, timeout=180.0)
    health = client.get("/healthz")
    if health.status_code != 200:
        print("service not healthy: %s %s" % (health.status_code, health.text), file=sys.stderr)
        return 2

    rows, failures = [], 0
    t0 = time.monotonic()
    for path, want_sha in iter_inputs(args):
        row = {"file_name": path.name, "outcome": None, "detail": ""}
        rows.append(row)
        expect = expectations.get(path.name, "image")
        if not path.is_file():
            row["outcome"], row["detail"] = "FAIL", "file missing"
            failures += 1
            continue
        if want_sha:
            got = sha256_file(path)
            if got != want_sha:
                row["outcome"], row["detail"] = "FAIL", "sha256 mismatch vs frozen manifest"
                failures += 1
                continue
        r = client.post(
            "/render",
            params={"format": "png", "width": args.width, "height": args.height, "bg": args.bg},
            files={"file": (path.name, path.read_bytes(), "application/octet-stream")},
        )
        ctype = r.headers.get("content-type", "")
        if ctype.startswith("image/png"):
            if expect == "error":
                row["outcome"], row["detail"] = "FAIL", "expected structured error, got image"
                failures += 1
                continue
            img = Image.open(io.BytesIO(r.content))
            if (img.width, img.height) != (args.width, args.height):
                row["outcome"], row["detail"] = "FAIL", "size %sx%s != requested" % img.size
                failures += 1
                continue
            ink = ink_fraction(r.content)
            row["ink"] = round(ink, 6)
            row["cache"] = r.headers.get("X-Render-Cache", "")
            if ink < args.min_ink and expect != "blank-ok" and path.name not in exceptions:
                row["outcome"], row["detail"] = "FAIL", "blank image (ink=%.6f)" % ink
                failures += 1
            else:
                if ink < args.min_ink:
                    row["detail"] = "blank exempted: %s" % (
                        exceptions.get(path.name) or expect
                    )
                row["outcome"] = "OK"
        else:
            try:
                body = r.json()
            except ValueError:
                row["outcome"], row["detail"] = "FAIL", "non-image non-JSON response (%d)" % r.status_code
                failures += 1
                continue
            if body.get("status") == "error" and body.get("error_code"):
                row["error_code"] = body["error_code"]
                if expect in ("error",):
                    row["outcome"] = "OK"
                    row["detail"] = body.get("error", "")[:120]
                else:
                    row["outcome"], row["detail"] = "FAIL", "structured error: %s" % body.get("error", "")[:200]
                    failures += 1
            else:
                row["outcome"], row["detail"] = "FAIL", "unstructured failure (%d)" % r.status_code
                failures += 1

    duration = time.monotonic() - t0
    summary = {
        "total": len(rows),
        "failed": failures,
        "duration_s": round(duration, 1),
        "params": {"width": args.width, "height": args.height, "bg": args.bg,
                    "min_ink": args.min_ink},
        "rows": rows,
    }
    if args.report:
        Path(args.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1), "utf-8")
    for row in rows:
        if row["outcome"] != "OK":
            print("FAIL %-50s %s" % (row["file_name"], row["detail"]))
    print("batch: %d total, %d failed, %.1fs" % (len(rows), failures, duration))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
