#!/usr/bin/env python3
"""Host-side end-to-end golden check (numpy/PIL). Consumes the per-pass PNGs
that ci_render_golden.py produced inside the A6 container and asserts, for
each golden drawing:
  1. pass-1 render is non-blank and matches the requested dimensions (the
     A8/M1a check, now against the REAL Linux render_cli in the image);
  2. pass-1 vs pass-2 compare lands in the `pass` band (render determinism +
     the full compare/scoring loop verified on real Linux renders).

This is the shipped render→compare end-to-end CI gate for the golden corpus.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from compare import compare, INK_FLOOR  # noqa: E402
from regress import _ink_fraction  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--render-dir", type=Path, required=True)
    args = ap.parse_args()

    golden = json.loads(args.golden.read_text("utf-8"))
    failures = []
    for d in golden.get("drawings", []):
        name = d["name"]
        r = d.get("render", {})
        p1 = args.render_dir / ("%s.p1.png" % name)
        p2 = args.render_dir / ("%s.p2.png" % name)
        if not p1.is_file() or not p2.is_file():
            failures.append("%s: missing render output" % name); continue
        # 1. non-blank + dimensions
        ink = _ink_fraction(p1)
        if ink < INK_FLOOR:
            failures.append("%s: blank render (ink=%.5f)" % (name, ink)); continue
        w, h = Image.open(p1).size
        if (w, h) != (r.get("width", 2400), r.get("height", 1697)):
            failures.append("%s: dims %dx%d != requested" % (name, w, h)); continue
        # 2. determinism: pass1 vs pass2 must band 'pass'
        res = compare(p1, p2)
        if res.band != "pass":
            failures.append("%s: non-deterministic render (band=%s ink_iou=%s)"
                            % (name, res.band, res.ink_iou))
        print("%-18s ink=%.4f dims=%dx%d determinism-band=%s"
              % (name, ink, w, h, res.band))

    if failures:
        print("\nE2E FAILURES:")
        for f in failures:
            print("  " + f)
        return 1
    print("\ngolden E2E: all %d drawings non-blank + deterministic"
          % len(golden.get("drawings", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
