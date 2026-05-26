#!/usr/bin/env bash
# Real /solve HTTP acceptance. Resolves the built solver binary + libcore from the
# cadgamefusion submodule build dir unless VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH
# are already set, then drives the running server over the wire. NOT part of node --test.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
: "${VEMCAD_SOLVE_BIN:=$ROOT/deps/cadgamefusion/build/tools/solve_from_project}"
: "${VEMCAD_SOLVE_LIBPATH:=$ROOT/deps/cadgamefusion/build/core}"
export VEMCAD_SOLVE_BIN VEMCAD_SOLVE_LIBPATH
echo "VEMCAD_SOLVE_BIN=$VEMCAD_SOLVE_BIN"
echo "VEMCAD_SOLVE_LIBPATH=$VEMCAD_SOLVE_LIBPATH"
exec node "$HERE/solve_http_acceptance.mjs"
