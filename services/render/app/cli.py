"""validate_package CLI — the contract conformance tool (plan A4):
plugin dev loop, CI gate, golden-set assertion carrier.

Usage:
  python3 -m app.cli validate <package_dir> [--expect-level LEVEL] [--quiet]

Exit codes: 0 = validation ran and (if given) --expect-level satisfied;
2 = manifest rejected; 3 = --expect-level not met; 4 = usage/IO error.
"""

import argparse
import json
import sys
from pathlib import Path

from .validator import LEVELS, load_package_dir, validate_package


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="validate_package")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("package_dir", type=Path)
    v.add_argument("--expect-level", choices=LEVELS, default=None)
    v.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest, payloads = load_package_dir(args.package_dir)
    except (OSError, ValueError) as e:
        print(json.dumps({"error": "cannot load package: %s" % e}), file=sys.stderr)
        return 4

    result = validate_package(manifest, payloads)
    report = result.report()
    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    if not result.ok_manifest:
        return 2
    if args.expect_level is not None:
        got = report["validated_level"]
        if got == "rejected" or LEVELS.index(got) < LEVELS.index(args.expect_level):
            print(
                "expected level %s, validated %s" % (args.expect_level, got),
                file=sys.stderr,
            )
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
