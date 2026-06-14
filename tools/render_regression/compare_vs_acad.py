"""X3 — quantify "媲美 AutoCAD". Compare our render of a drawing against an
AutoCAD reference render of the SAME drawing (same extents, white background),
producing a similarity score + a difference overlay. Turns the "does it look
like AutoCAD?" eyeball into a number you can cite.

Reuses the D2 comparator (compare.py: aligned dilation-tolerant ink IoU + color
/aspect guards) and the diff engine (diff.py: 3-colour overlay). No rendering
here — feed it two PNGs.

Capture the AutoCAD reference fairly (so it's apples-to-apples):
  - PLOT / EXPORTPNG (or PUBLISH) the layout/extents to PNG,
  - white background, monochrome OFF (keep colours), the SAME aspect as our
    render (e.g. fit extents), long edge >= 1600 px.
Then:
  python3 tools/render_regression/compare_vs_acad.py acad.png ours.png --out x3_overlay.png

Reads: red in the overlay = ink AutoCAD has that we are MISSING; green = ink we
drew that AutoCAD does NOT have; grey = matches.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # so `import compare/diff` work as a CLI

import compare as cmp  # noqa: E402
import diff as dff      # noqa: E402


def _verdict(band: str, comparable: bool, skip_reason: str) -> str:
    if not comparable:
        return "NOT COMPARABLE (%s) — re-export the AutoCAD PNG at the same extents/bg/aspect." % (
            skip_reason or "view-space/bg/colour differ")
    return {
        "pass": "EXCELLENT — our render matches AutoCAD closely (媲美 AutoCAD).",
        "review": "CLOSE — high ink overlap but colour/aspect/text differs; inspect the overlay.",
        "fallback": "DIVERGENT — significant difference; inspect the overlay and investigate.",
    }.get(band, "UNKNOWN")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="compare_vs_acad",
        description="Score our render against an AutoCAD reference (X3).")
    ap.add_argument("acad", type=Path, help="AutoCAD reference render (PNG)")
    ap.add_argument("ours", type=Path, help="our render of the same drawing (PNG)")
    ap.add_argument("--out", type=Path, default=None, help="difference overlay PNG to write")
    ap.add_argument("--capture-method", default="offscreen-render",
                    help="trust tier for the comparison (default offscreen-render)")
    args = ap.parse_args(argv)

    # ref = AutoCAD (ground truth), cand = ours.
    res = cmp.compare(args.acad, args.ours, capture_method=args.capture_method)
    overlay_note = ""
    if args.out is not None:
        ov = dff.diff_overlay(args.acad, args.ours, out_path=args.out)
        if ov.overlay_path:
            overlay_note = "  overlay      : %s  (red=AutoCAD has/we miss; green=we drew extra; grey=match)" % args.out
        elif not ov.comparable:
            overlay_note = "  overlay      : (skipped — %s)" % ov.skip_reason

    print("媲美 AutoCAD 对比 (X3)")
    print("  reference    : %s  (AutoCAD)" % args.acad)
    print("  candidate    : %s  (ours)" % args.ours)
    print("  ink IoU      : %-7s [PASS >=0.97]  墨迹重合度(越接近 1 越像 AutoCAD)" % res.ink_iou)
    print("  SSIM         : %-7s (informational)" % res.ssim)
    print("  color dist   : %-7s [ok <=%.0f]  墨迹平均颜色差" % (res.color_dist, cmp.COLOR_TOL))
    print("  aspect delta : %-7s [ok <=%.2f]  纵横比/缩放一致性" % (res.aspect_delta, cmp.ASPECT_TOL))
    print("  comparable   : %s" % res.comparable)
    print("  band         : %s" % res.band)
    if overlay_note:
        print(overlay_note)
    print("verdict: %s" % _verdict(res.band, res.comparable, res.skip_reason))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
