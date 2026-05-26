#!/usr/bin/env bash
# Independent solver acceptance (Project Runtime v1 / Tier 1 / C3).
#
# Runs the REAL solve_from_project on known fixtures through the full local loop
# (adapter -> CADGF-PROJ -> CLI -> writeback) and asserts each solution satisfies
# its constraint within tolerance and is reproducible. Deliberately NOT part of
# `node --test`: it needs the built binary + libcore (a missing binary fails only
# this step, never the pure-Node runtime suite).
#
# Usage: bash apps/runtime/tools/run_solver_acceptance.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

: "${VEMCAD_SOLVE_BIN:=$REPO/deps/cadgamefusion/build/tools/solve_from_project}"
: "${VEMCAD_SOLVE_LIBPATH:=$REPO/deps/cadgamefusion/build/core}"
export VEMCAD_SOLVE_BIN VEMCAD_SOLVE_LIBPATH

if [ ! -x "$VEMCAD_SOLVE_BIN" ]; then
  echo "ERROR: solver binary not found/executable at $VEMCAD_SOLVE_BIN" >&2
  echo "Build CADGameFusion (or set VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH). This step needs the binary; node --test does not." >&2
  exit 3
fi

OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

echo "== solver: $VEMCAD_SOLVE_BIN =="
echo "== libpath: $VEMCAD_SOLVE_LIBPATH =="
node "$HERE/solve_acceptance.mjs" "$OUT"

echo "== validating solve->derive CADGF Documents vs document.schema.json =="
python3 "$HERE/validate_cadgf_document.py" "$OUT"/*.cadgf.json

echo "C3 solver acceptance: PASS"
