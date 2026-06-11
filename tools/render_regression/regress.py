#!/usr/bin/env python3
"""D2 regression harness — render each golden/corpus drawing, compare to its
best available baseline (acad > ref-render > self), and emit a banded report.
Gated drawings whose gate-trust score lands in the `fallback` band fail the
run (CI). The render step is injectable so the aggregation logic is unit-
tested with synthetic images; the default renderer shells out to render_cli.

Usage:
  regress.py --golden golden/golden.json --baselines baselines.json \
             --render-cli /path/render_cli --out-dir /tmp/out [--report r.json]
  regress.py ... --update-baseline self --approver NAME   # record self-baselines
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from compare import compare, INK_FLOOR  # noqa: E402
from baseline import BaselineStore  # noqa: E402


def _ink_fraction(path: Path) -> float:
    """Fraction of non-background pixels (background = frame-border median)."""
    g = np.asarray(Image.open(path).convert("L"), dtype=np.float64)
    b = 3
    edge = np.concatenate([g[:b, :].ravel(), g[-b:, :].ravel(),
                           g[:, :b].ravel(), g[:, -b:].ravel()])
    bg = float(np.median(edge))
    return float((np.abs(g - bg) > 32.0).mean())

# (drawing dict, output png path) -> True on a successful non-empty render.
RenderFn = Callable[[dict, Path], bool]


def render_cli_renderer(render_cli: Path, golden_dir: Path) -> RenderFn:
    def _render(drawing: dict, out: Path) -> bool:
        src = golden_dir / (drawing["name"] + ".dxf")
        r = drawing.get("render", {})
        argv = [str(render_cli), "--input", str(src), "--out", str(out),
                "--width", str(r.get("width", 2400)), "--height", str(r.get("height", 1697)),
                "--bg", r.get("bg", "white")]
        if r.get("window"):
            argv += ["--window", r["window"]]
        try:
            res = subprocess.run(argv, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired:
            return False
        return res.returncode == 0 and out.is_file() and out.stat().st_size > 0
    return _render


def run(golden: dict, baselines: BaselineStore, render_fn: RenderFn,
        out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: List[dict] = []
    for d in golden.get("drawings", []):
        name = d["name"]
        gate = bool(d.get("gate", False))
        out = out_dir / (name + ".png")
        row: Dict = {"drawing": name, "category": d.get("category"), "gate": gate}
        if not render_fn(d, out):
            row.update(outcome="FAIL", reason="render-failed", band="fallback")
            rows.append(row); continue
        # Non-blank check (the A8 gate, folded in): a blank render of a gated
        # drawing fails regardless of any baseline.
        if _ink_fraction(out) < INK_FLOOR:
            row.update(outcome="BLANK", reason="render produced a blank image", band="fallback")
            rows.append(row); continue
        base = baselines.best(name)
        if base is None:
            row.update(outcome="NO-BASELINE", band="n/a",
                       reason="no baseline recorded (run --update-baseline self)")
            rows.append(row); continue
        base_img = out_dir / ("_baseline_" + name + ".png")
        # Baseline image comes from the artifact store / a prior recording run.
        # A gated drawing whose baseline image is absent/mismatched FAILS CLOSED
        # — never silently passes (else CI goes green comparing nothing).
        if not base_img.is_file() or not baselines.verify_image(name, base.tier, base_img):
            row.update(outcome="BASELINE-MISSING", tier=base.tier,
                       band="fallback" if gate else "n/a",
                       reason="baseline image absent/mismatched in artifact store")
            rows.append(row); continue
        res = compare(base_img, out, capture_method=getattr(base, "capture_method", "offscreen-render"))
        row.update(outcome="OK", tier=base.tier, score=res.ink_iou,
                   ssim=res.ssim, band=res.band, trust=res.trust,
                   aspect_delta=res.aspect_delta, color_dist=res.color_dist,
                   comparable=res.comparable, dx=res.dx, dy=res.dy)
        rows.append(row)

    # Gated failure: a gated drawing that render-failed, came out blank, has a
    # missing/mismatched baseline, or whose gate-trust comparison is fallback.
    # advisory/record trust and NO-BASELINE never gate.
    def _is_gated_failure(r: dict) -> bool:
        if not r["gate"]:
            return False
        if r.get("reason") in ("render-failed", "render produced a blank image"):
            return True
        if r.get("outcome") == "BASELINE-MISSING":
            return True
        return r.get("trust") == "gate" and r.get("band") == "fallback"
    failures = [r for r in rows if _is_gated_failure(r)]
    return {
        "schema": "vemcad.render_regression_report",
        "total": len(rows), "gated_failures": len(failures),
        "rows": rows,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", type=Path, default=HERE / "golden" / "golden.json")
    ap.add_argument("--baselines", type=Path, default=HERE / "baselines.json")
    ap.add_argument("--render-cli", type=Path, required=True)
    ap.add_argument("--golden-dir", type=Path, default=HERE / "golden")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--update-baseline", choices=["self"], default=None)
    ap.add_argument("--approver", default=None)
    args = ap.parse_args(argv)

    golden = json.loads(args.golden.read_text("utf-8"))
    store = BaselineStore(args.baselines)
    render_fn = render_cli_renderer(args.render_cli, args.golden_dir)

    if args.update_baseline == "self":
        if not args.approver:
            print("--update-baseline requires --approver", file=sys.stderr); return 2
        args.out_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        for d in golden.get("drawings", []):
            out = args.out_dir / ("_baseline_" + d["name"] + ".png")
            if render_fn(d, out):
                store.record(d["name"], "self", out, approver=args.approver,
                             note="self-baseline")
                n += 1
        store.save()
        print("recorded %d self-baselines (approver=%s)" % (n, args.approver))
        return 0

    report = run(golden, store, render_fn, args.out_dir)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    for r in report["rows"]:
        if r.get("outcome") not in ("OK",) or r.get("band") == "fallback":
            print("%-18s %-12s %s" % (r["drawing"], r.get("outcome"),
                                       r.get("reason") or "band=%s score=%s" % (r.get("band"), r.get("score"))))
    print("regression: %d drawings, %d gated failures" % (report["total"], report["gated_failures"]))
    return 1 if report["gated_failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
