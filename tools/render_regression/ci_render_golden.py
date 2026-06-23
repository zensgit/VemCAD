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


def _font_records(report_path: Path):
    try:
        rep = json.loads(report_path.read_text("utf-8"))
    except (OSError, ValueError) as e:
        raise RuntimeError("report unreadable (%s)" % e)
    records = ((rep.get("fonts") or {}).get("records") or [])
    if not isinstance(records, list):
        raise RuntimeError("fonts.records is not a list")
    return records


def _check_font_resolution(name: str, report_path: Path, exp: dict) -> list[str]:
    try:
        records = _font_records(report_path)
    except RuntimeError as e:
        return ["%s font resolution: %s" % (name, e)]

    if not records:
        return ["%s font resolution: no font records in report" % name]

    failures = []
    forbidden = {str(f).casefold() for f in exp.get("forbid_resolved", [])}
    required_tokens = [str(t).casefold() for t in exp.get("require_resolved_contains_any", [])]

    resolved = []
    for rec in records:
        got = str((rec or {}).get("resolved", ""))
        resolved.append(got)
        if got.casefold() in forbidden:
            failures.append("%s font resolution: forbidden resolved family %r" % (name, got))

    if required_tokens:
        if not any(any(tok in got.casefold() for tok in required_tokens) for got in resolved):
            failures.append("%s font resolution: resolved families %s do not contain any of %s"
                            % (name, resolved, exp.get("require_resolved_contains_any", [])))

    if not failures:
        print("%-18s font_resolution OK (resolved=%s)" % (name, ", ".join(resolved)))
    return failures


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
        report_path = args.out / (name + ".report.json")
        for p in range(1, args.passes + 1):
            out = args.out / ("%s.p%d.png" % (name, p))
            argv = [args.render_cli, "--input", str(src), "--out", str(out),
                    "--width", str(r.get("width", 2400)),
                    "--height", str(r.get("height", 1697)),
                    "--bg", r.get("bg", "white"),
                    "--report", str(report_path)]
            if r.get("window"):
                argv += ["--window", r["window"]]
            res = subprocess.run(argv, capture_output=True, text=True)
            ok = res.returncode == 0 and out.is_file() and out.stat().st_size > 0
            print("%-18s pass%d %s" % (name, p, "OK" if ok else "FAIL " + res.stderr.strip()[:200]))
            if not ok:
                failures += 1

        # common-window v2: assert render_cli's report content_bbox captures the
        # REAL geometry (>= expected), proving it exceeds a stale-small header —
        # i.e. why v1's header-window clips and v2's content_bbox-window doesn't.
        exp = d.get("expect_content_bbox")
        if exp:
            cb = None
            try:
                rep = json.loads(report_path.read_text("utf-8"))
                cb = (rep.get("view") or {}).get("content_bbox")
            except (OSError, ValueError) as e:
                print("%-18s content_bbox: report unreadable (%s)" % (name, e))
                failures += 1
            if cb is None:
                print("%-18s content_bbox MISSING in report" % name)
                failures += 1
            else:
                got_x, got_y = cb.get("max_x", -1e18), cb.get("max_y", -1e18)
                if got_x >= exp.get("min_max_x", -1e18) and got_y >= exp.get("min_max_y", -1e18):
                    print("%-18s content_bbox OK (max_x=%.1f max_y=%.1f >= %s)"
                          % (name, got_x, got_y, exp))
                else:
                    print("%-18s content_bbox FAIL (got max_x=%.1f max_y=%.1f, want >= %s)"
                          % (name, got_x, got_y, exp))
                    failures += 1

        font_exp = d.get("expect_font_resolution")
        if font_exp:
            font_failures = _check_font_resolution(name, report_path, font_exp)
            for f in font_failures:
                print(f)
            failures += len(font_failures)
    print("rendered %d drawings x %d passes, %d failures"
          % (len(golden.get("drawings", [])), args.passes, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
