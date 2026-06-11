#!/usr/bin/env python3
"""Render every golden drawing via render_cli — runs INSIDE the A6 container
(stdlib only: the container has python3 + render_cli but not numpy/PIL). Each
drawing is rendered `--passes` times so the host step can check determinism.
The host (numpy/PIL) then runs the compare/non-blank checks (ci_e2e_check.py).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--golden-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--render-cli", default="/usr/local/bin/render_cli")
    ap.add_argument("--passes", type=int, default=2)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    golden = json.loads(args.golden.read_text("utf-8"))
    failures = 0
    for d in golden.get("drawings", []):
        name = d["name"]
        src = args.golden_dir / (name + ".dxf")
        r = d.get("render", {})
        for p in range(1, args.passes + 1):
            out = args.out / ("%s.p%d.png" % (name, p))
            argv = [args.render_cli, "--input", str(src), "--out", str(out),
                    "--width", str(r.get("width", 2400)),
                    "--height", str(r.get("height", 1697)),
                    "--bg", r.get("bg", "white")]
            if r.get("window"):
                argv += ["--window", r["window"]]
            res = subprocess.run(argv, capture_output=True, text=True)
            ok = res.returncode == 0 and out.is_file() and out.stat().st_size > 0
            print("%-18s pass%d %s" % (name, p, "OK" if ok else "FAIL " + res.stderr.strip()[:200]))
            if not ok:
                failures += 1
    print("rendered %d drawings x %d passes, %d failures"
          % (len(golden.get("drawings", [])), args.passes, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
