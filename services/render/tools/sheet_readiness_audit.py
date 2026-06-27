#!/usr/bin/env python3
"""Audit whether view=sheet is ready to become a render default.

The tool renders every DXF twice through a running vemcad-render service:
view=extents and view=sheet. It writes a JSON summary plus contact sheets for
human review. It intentionally takes a directory at runtime; training/customer
drawings do not need to be committed to the repository.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageOps


@dataclass(frozen=True)
class Thresholds:
    min_ink_px: int = 600
    retained_review: float = 0.55
    retained_fail: float = 0.35
    edge_review: float = 0.020
    edge_fail: float = 0.060
    ink_threshold: int = 24
    edge_px: int = 4


@dataclass
class ImageStats:
    width: int
    height: int
    ink_px: int
    ink_fraction: float
    edge_ink_fraction: float
    bbox: list[int] | None


@dataclass
class AuditResult:
    file: str
    status: str
    sheet_mode: str
    resolved_view: str | None
    extents_png: str | None
    sheet_png: str | None
    retained_ink_fraction: float | None
    extents: ImageStats | None
    sheet: ImageStats | None
    notes: list[str]
    error: str | None = None


def _safe_name(path: Path, index: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._") or "drawing"
    return f"{index:04d}_{stem}"


def _background_rgb(arr: np.ndarray) -> np.ndarray:
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]], axis=0)
    return np.median(border, axis=0)


def image_stats(path: Path, thresholds: Thresholds = Thresholds()) -> ImageStats:
    img = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    rgb = np.asarray(bg.convert("RGB"), dtype=np.int16)
    H, W = rgb.shape[:2]
    background = _background_rgb(rgb)
    diff = np.max(np.abs(rgb - background), axis=2)
    mask = diff > thresholds.ink_threshold
    ink_px = int(mask.sum())
    if ink_px:
        ys, xs = np.where(mask)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    else:
        bbox = None
    edge = np.zeros_like(mask, dtype=bool)
    n = max(1, thresholds.edge_px)
    edge[:n, :] = True
    edge[-n:, :] = True
    edge[:, :n] = True
    edge[:, -n:] = True
    edge_ink = int(np.logical_and(mask, edge).sum())
    return ImageStats(
        width=W,
        height=H,
        ink_px=ink_px,
        ink_fraction=float(ink_px / max(W * H, 1)),
        edge_ink_fraction=float(edge_ink / max(ink_px, 1)),
        bbox=bbox,
    )


def analyse_pair(
    dxf: Path,
    extents_png: Path,
    sheet_png: Path,
    *,
    sheet_mode: str,
    resolved_view: str | None = None,
    thresholds: Thresholds = Thresholds(),
    out_root: Path | None = None,
) -> AuditResult:
    extents = image_stats(extents_png, thresholds)
    sheet = image_stats(sheet_png, thresholds)
    notes: list[str] = []
    status = "pass"
    retained = float(sheet.ink_px / max(extents.ink_px, 1))

    if extents.ink_px < thresholds.min_ink_px:
        status = "fail"
        notes.append("extents render has too little ink")
    if sheet.ink_px < thresholds.min_ink_px:
        status = "fail"
        notes.append("sheet render has too little ink")
    if retained < thresholds.retained_fail:
        status = "fail"
        notes.append("sheet retained very little extents ink")
    elif retained < thresholds.retained_review and status != "fail":
        status = "review"
        notes.append("sheet retained substantially less ink; inspect for over-crop vs stray removal")
    if sheet.edge_ink_fraction > thresholds.edge_fail:
        status = "fail"
        notes.append("sheet ink touches image edge heavily; possible crop")
    elif sheet.edge_ink_fraction > thresholds.edge_review and status == "pass":
        status = "review"
        notes.append("sheet ink touches image edge; inspect for crop")
    if sheet_mode in ("fallback", "unknown") and status == "pass":
        status = "review"
    if sheet_mode == "fallback":
        notes.append("sheet detector fell back to extents")
    elif sheet_mode == "unknown":
        notes.append("sheet detector provenance unavailable")

    def rel(p: Path | None) -> str | None:
        if p is None:
            return None
        return str(p.relative_to(out_root)) if out_root else str(p)

    return AuditResult(
        file=str(dxf),
        status=status,
        sheet_mode=sheet_mode,
        resolved_view=resolved_view,
        extents_png=rel(extents_png),
        sheet_png=rel(sheet_png),
        retained_ink_fraction=retained,
        extents=extents,
        sheet=sheet,
        notes=notes,
    )


def _multipart_upload(url: str, file_path: Path, auth_token: str | None = None) -> tuple[bytes, dict[str, str]]:
    boundary = "----vemcad-sheet-audit-%d" % time.time_ns()
    data = file_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    headers = {"Content-Type": "multipart/form-data; boundary=%s" % boundary}
    if auth_token:
        headers["Authorization"] = "Bearer %s" % auth_token
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.read(), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError("HTTP %d from /render: %s" % (exc.code, detail)) from exc


def render_file(
    base_url: str,
    dxf: Path,
    out_png: Path,
    *,
    view: str,
    width: int,
    height: int,
    bg: str,
    style: str,
    auth_token: str | None,
) -> dict[str, str]:
    query = urllib.parse.urlencode(
        {"format": "png", "width": width, "height": height, "bg": bg, "view": view, "style": style}
    )
    body, headers = _multipart_upload("%s/render?%s" % (base_url.rstrip("/"), query), dxf, auth_token)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(body)
    return headers


def _thumb(path: Path, size: tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB")
    thumb = ImageOps.contain(img, size)
    out = Image.new("RGB", size, "white")
    out.paste(thumb, ((size[0] - thumb.width) // 2, (size[1] - thumb.height) // 2))
    return out


def write_contact_sheets(
    results: list[AuditResult],
    out_dir: Path,
    *,
    tile_size: tuple[int, int] = (360, 255),
    rows_per_page: int = 18,
) -> list[str]:
    sheets: list[str] = []
    if not results:
        return sheets
    colors = {"pass": "#2f8f46", "review": "#c08a00", "fail": "#c7352c"}
    label_h = 42
    pad = 10
    font = None
    for page_index in range(0, len(results), rows_per_page):
        chunk = results[page_index:page_index + rows_per_page]
        W = pad * 3 + tile_size[0] * 2
        H = pad + len(chunk) * (tile_size[1] + label_h + pad)
        canvas = Image.new("RGB", (W, H), "white")
        draw = ImageDraw.Draw(canvas)
        y = pad
        for item in chunk:
            color = colors.get(item.status, "#777777")
            draw.text((pad, y), "%s  %s" % (item.status.upper(), Path(item.file).name), fill=color, font=font)
            draw.text((pad, y + 18), "sheet=%s retained=%.3f" % (
                item.sheet_mode,
                item.retained_ink_fraction if item.retained_ink_fraction is not None else -1.0,
            ), fill="#333333", font=font)
            y_img = y + label_h
            for col, png_rel in enumerate((item.extents_png, item.sheet_png)):
                x = pad + col * (tile_size[0] + pad)
                if png_rel:
                    img = _thumb(out_dir / png_rel, tile_size)
                    canvas.paste(img, (x, y_img))
                draw.rectangle((x, y_img, x + tile_size[0] - 1, y_img + tile_size[1] - 1), outline=color, width=3)
                draw.text((x + 5, y_img + 5), "extents" if col == 0 else "sheet", fill=color, font=font)
            y += tile_size[1] + label_h + pad
        name = "contact_sheet_%02d.png" % (len(sheets) + 1)
        canvas.save(out_dir / name)
        sheets.append(name)
    return sheets


def iter_dxf_files(input_dir: Path, patterns: Iterable[str], limit: int | None) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in patterns:
        for item in sorted(input_dir.rglob(pattern)):
            if item.is_file() and item not in seen:
                seen.add(item)
                files.append(item)
                if limit and len(files) >= limit:
                    return files
    return files


def run_audit(args) -> tuple[dict, int]:
    input_dir = Path(args.input_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ext_dir = out_dir / "extents"
    sheet_dir = out_dir / "sheet"
    thresholds = Thresholds(
        retained_review=args.retained_review,
        retained_fail=args.retained_fail,
        edge_review=args.edge_review,
        edge_fail=args.edge_fail,
    )
    files = iter_dxf_files(input_dir, args.pattern, args.limit)
    results: list[AuditResult] = []
    for i, dxf in enumerate(files, 1):
        base = _safe_name(dxf, i) + ".png"
        ext_png = ext_dir / base
        sheet_png = sheet_dir / base
        try:
            render_file(
                args.base_url, dxf, ext_png, view="extents", width=args.width, height=args.height,
                bg=args.bg, style=args.style, auth_token=args.auth_token,
            )
            h = render_file(
                args.base_url, dxf, sheet_png, view="sheet", width=args.width, height=args.height,
                bg=args.bg, style=args.style, auth_token=args.auth_token,
            )
            result = analyse_pair(
                dxf, ext_png, sheet_png,
                sheet_mode=h.get("x-render-sheet-mode", "unknown"),
                resolved_view=h.get("x-render-resolved-view"),
                thresholds=thresholds,
                out_root=out_dir,
            )
        except Exception as exc:  # keep auditing the rest of the corpus
            result = AuditResult(
                file=str(dxf),
                status="fail",
                sheet_mode="error",
                resolved_view=None,
                extents_png=str(ext_png.relative_to(out_dir)) if ext_png.exists() else None,
                sheet_png=str(sheet_png.relative_to(out_dir)) if sheet_png.exists() else None,
                retained_ink_fraction=None,
                extents=None,
                sheet=None,
                notes=["render/audit failed"],
                error=str(exc),
            )
        results.append(result)
        print("[%s] %s" % (result.status, dxf.name), file=sys.stderr)

    contact = write_contact_sheets(results, out_dir)
    totals = {status: sum(1 for r in results if r.status == status) for status in ("pass", "review", "fail")}
    summary = {
        "schema": "vemcad.sheet_readiness_audit/v1",
        "params": {
            "input_dir": str(input_dir),
            "base_url": args.base_url,
            "width": args.width,
            "height": args.height,
            "bg": args.bg,
            "style": args.style,
            "patterns": list(args.pattern),
            "thresholds": asdict(thresholds),
        },
        "totals": {"count": len(results), **totals},
        "contact_sheets": contact,
        "results": [
            {
                **asdict(r),
                "extents": asdict(r.extents) if r.extents else None,
                "sheet": asdict(r.sheet) if r.sheet else None,
            }
            for r in results
        ],
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    exit_code = 0
    if totals["fail"] or (args.fail_on_review and totals["review"]):
        exit_code = 1
    return summary, exit_code


def parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", required=True, help="Directory containing DXF files to audit.")
    p.add_argument("--out-dir", required=True, help="Directory for summary.json, renders, and contact sheets.")
    p.add_argument("--base-url", default="http://127.0.0.1:8077", help="vemcad-render base URL.")
    p.add_argument("--pattern", action="append", default=["*.dxf", "*.DXF"], help="Glob pattern, repeatable.")
    p.add_argument("--limit", type=int, default=None, help="Optional max drawing count.")
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--height", type=int, default=1131)
    p.add_argument("--bg", default="white")
    p.add_argument("--style", choices=("source", "acad-plot", "acad-display"), default="source")
    p.add_argument("--auth-token", default=None)
    p.add_argument("--retained-review", type=float, default=0.55)
    p.add_argument("--retained-fail", type=float, default=0.35)
    p.add_argument("--edge-review", type=float, default=0.020)
    p.add_argument("--edge-fail", type=float, default=0.060)
    p.add_argument("--fail-on-review", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    _, code = run_audit(parse_args(argv))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
