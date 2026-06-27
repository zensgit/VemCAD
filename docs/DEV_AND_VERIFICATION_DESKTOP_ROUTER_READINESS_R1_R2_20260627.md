# Desktop / Router Readiness R1-R2 Development And Verification

Date: 2026-06-27

Branch: `codex/vemcad-next-line-taskbook`

Baseline:

- VemCAD `origin/main`: `9e783a4`
- CADGameFusion gitlink: `4327230`

## Scope

This slice completes the product-side Desktop / Router local-readiness first cuts:

- R0: taskbook and README index entry.
- R1: product Router launcher / contract guards.
- R2: opt-in real reference Router smoke.

It deliberately does not change desktop shell code, Router business logic, cloud orchestration, converter selection, or the CADGameFusion submodule pointer.

## Changes

### R0 taskbook correction

The taskbook now records the current `origin/main` baseline and aligns the Router route inventory with the actual product contract:

- `GET /health`
- `POST /convert`
- `GET /status/{task_id}`
- `GET /manifest/{task_id}`
- `GET /history`
- `GET /projects`
- `GET /projects/{project_id}/documents`
- `GET /documents/{document_id}/versions`

The earlier `/jobs/{job_id}` / generic `/artifacts/{artifact_id}` wording was stale for this product-layer contract and would have made the R1 guard test protect the wrong surface.

### R1 product Router guard tests

Added:

- launcher handle-shape test: `{ url, pid, ready, stop }` is available before readiness resolves;
- spawn-failure test: an unavailable command rejects `ready()` with `ROUTER_START_FAILED`;
- contract inventory test: `services/router/CONTRACT.md` must list the stable routes and must not drift to stale `/jobs` or generic `/artifacts` route names.

Existing tests already covered:

- missing command -> `ROUTER_START_NOT_CONFIGURED`;
- ready success and idempotent `ready()`;
- delayed readiness polling;
- child exits before readiness -> `ROUTER_START_FAILED`;
- readiness timeout -> `ROUTER_START_TIMEOUT` and no orphan;
- ignore-SIGTERM timeout/stop escalation;
- idempotent `stop()`.

### R2 opt-in real Router smoke

Added `services/router/tools/router_reference_smoke.mjs`.

Behavior:

- starts the actual CADGameFusion `deps/cadgamefusion/tools/plm_router_service.py`;
- uses a free loopback port and temporary output root;
- waits for `/health`;
- prints a structured PASS payload;
- stops the child and removes the temp output directory;
- prints `SKIP: ...` and exits 0 when Python or submodule prerequisites are missing.

This is intentionally not part of default `npm test`.

## Verification

Commands run:

```bash
npm test
npm run test:web
git diff --check
git submodule update --init --recursive deps/cadgamefusion
node services/router/tools/router_reference_smoke.mjs
```

Observed evidence:

- `npm test`: 144 passed, 0 failed. This includes the new R1 tests:
  - stable launcher handle shape before readiness;
  - spawn failure -> `ROUTER_START_FAILED`;
  - router contract inventory and stale-route rejection.
- `npm run test:web`: 123 passed, 0 failed.
- `git diff --check`: clean.
- `node services/router/tools/router_reference_smoke.mjs`: structured `PASS`, `health.status == "ok"`, router commit `4327230`, temporary loopback URL `http://127.0.0.1:54556`.

## Boundaries

No CADGameFusion code changes. No VemCAD gitlink bump. No Electron shell edit. No cloud or multi-user Router work. The local developer smoke is evidence for this workstation, not a required CI gate.

## Remaining Router Readiness Work

R3/R4 stay decision/scoping work:

- inspect the CADGameFusion Electron shell only when a desktop packaging need appears;
- decide launcher dedup ownership only after R1/R2 evidence and real shell needs are known.

Cloud/multi-user Router work remains deferred.
