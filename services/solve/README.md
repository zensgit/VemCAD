# VemCAD `/solve` service (Tier 3 prototype)

Headless HTTP front for the v1 constraint solver. A thin `node:http` adapter that
shells out to `apps/runtime/tools/solve_cli.mjs` (the host-agnostic solve unit) and
maps its exit code + JSON envelope onto HTTP. No solver logic lives here — any host
(this service, the python Router, the Electron shell) maps the **same** contract.

Deliberately **separate** from `services/router/` (the DWG/DXF conversion pipeline
slated to split into its own repo for GPL/LibreDWG isolation): `/solve` is pure
runtime, carries no GPL code, and belongs with the runtime — not the converter repo.

## Contract

| Method / Path | Body | Success |
|---|---|---|
| `POST /solve` | VEMCAD-PROJECT JSON | the `solve_cli` result envelope (JSON) |
| `GET /health` | — | `{"ok":true}` |

HTTP status (the response body is **always** the JSON envelope):

| Outcome | Status |
|---|---|
| solved | `200` |
| bad input (malformed JSON / invalid or unsupported PROJECT) | `400` |
| `SOLVE_UNSATISFIED` — the sketch has no solution | `422` |
| `SOLVE_FAILED` — solver binary missing / runner threw (server-side) | `500` |
| CLI emitted non-JSON / could not spawn | `500` |

`SOLVE_UNSATISFIED` (422) and `SOLVE_FAILED` (500) share `solve_cli` exit code `1`;
the service splits them on the envelope's `error_code` so a client can tell "your
sketch is unsolvable" (422, fixable client-side) from "the server failed" (500).

## Run

```sh
# point at the real solver binary + libcore (passed straight through to solve_cli)
export VEMCAD_SOLVE_BIN=…/deps/cadgamefusion/build/tools/solve_from_project
export VEMCAD_SOLVE_LIBPATH=…/deps/cadgamefusion/build/core
PORT=8787 node services/solve/main.mjs

curl -s -XPOST localhost:8787/solve -H 'content-type: application/json' --data-binary @project.json
```

## Test

```sh
node --test services/solve/tests/*.test.js              # pure node, fake CLI (no binary)
bash services/solve/tools/run_solve_http_acceptance.sh  # real solver, end-to-end over HTTP
```

> The acceptance auto-resolves the solver from `deps/cadgamefusion/build/…`. If the
> submodule isn't built in your checkout, set `VEMCAD_SOLVE_BIN` / `VEMCAD_SOLVE_LIBPATH`
> to any built copy first (otherwise the solve cases return `500` from a missing binary).

## Prototype scope (chosen, not forgotten)

No request-size limit, no per-request timeout, no concurrency cap, no auth — a
hardened/exposed deployment must add these first. The solve unit is spawned per
request (`solve_cli.mjs`); moving to an in-process or C-ABI solve is the deferred
Tier-3 performance decision.
