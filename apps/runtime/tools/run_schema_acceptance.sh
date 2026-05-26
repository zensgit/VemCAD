#!/usr/bin/env bash
# Independent CADGF schema acceptance (Project Runtime v0 / S6).
#
# Derives representative CADGF Documents from VEMCAD-PROJECTs (pure Node, fixed
# clock) and validates them against the real document.schema.json with Python
# `jsonschema`. Deliberately NOT part of `node --test`: a missing Python
# dependency fails only this step, never the pure-Node runtime suite.
#
# Usage: bash apps/runtime/tools/run_schema_acceptance.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "== emitting CADGF fixtures (Node) =="
node "$HERE/emit_cadgf_fixtures.mjs" "$OUT"

echo "== validating against document.schema.json (Python jsonschema) =="
python3 "$HERE/validate_cadgf_document.py" "$OUT"/*.cadgf.json

echo "S6 schema acceptance: PASS"
