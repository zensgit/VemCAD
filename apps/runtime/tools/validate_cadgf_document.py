#!/usr/bin/env python3
"""Validate CADGF Document JSON files against the real CADGF schema.

Schema: deps/cadgamefusion/schemas/document.schema.json

Usage:
    validate_cadgf_document.py <doc.json> [<doc2.json> ...]

Exit codes:
    0  all documents valid
    1  at least one document failed validation
    2  bad usage (no files given)
    3  the `jsonschema` package is not installed
    4  the CADGF schema file was not found

This is an INDEPENDENT acceptance step, deliberately kept out of `node --test`
so that a missing Python dependency only fails this step, never the pure-Node
runtime test suite.
"""
import json
import sys
from pathlib import Path


def main(argv):
    if len(argv) < 2:
        print("usage: validate_cadgf_document.py <doc.json> [more.json ...]", file=sys.stderr)
        return 2

    try:
        import jsonschema
    except ImportError:
        print("ERROR: the Python 'jsonschema' package is required for the CADGF schema", file=sys.stderr)
        print("acceptance step. Install it (e.g. `pip install jsonschema`) and re-run.", file=sys.stderr)
        print("This does not affect `node --test` (the pure-Node runtime suite).", file=sys.stderr)
        return 3

    # This file lives at apps/runtime/tools/ ; the repo root is three levels up.
    repo_root = Path(__file__).resolve().parents[3]
    schema_path = repo_root / "deps/cadgamefusion/schemas/document.schema.json"
    if not schema_path.is_file():
        print(f"ERROR: CADGF schema not found at {schema_path}", file=sys.stderr)
        return 4

    schema = json.loads(schema_path.read_text())
    failures = 0
    for arg in argv[1:]:
        doc_path = Path(arg)
        try:
            doc = json.loads(doc_path.read_text())
            jsonschema.validate(doc, schema)
            print(f"OK   {doc_path.name}")
        except jsonschema.ValidationError as exc:
            failures += 1
            where = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            print(f"FAIL {doc_path.name}: {exc.message} [at {where}]", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - surface any read/parse error per file
            failures += 1
            print(f"FAIL {doc_path.name}: {exc}", file=sys.stderr)

    print(f"validated {len(argv) - 1} document(s); {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
