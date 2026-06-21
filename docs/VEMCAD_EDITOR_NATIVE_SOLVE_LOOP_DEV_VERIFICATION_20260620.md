# Editor Native Solve Loop — Development & Verification (2026-06-20)

Goal: make the editor's own constraint solve loop work natively in the **CADGameFusion web_viewer**
(the editor the desktop loads directly) — **点 Solve → 跑真 solver → 面板显示真实结果 → 几何写回(可撤销) → 冲突 UX**,
sliced into small PRs. Direction: desktop / local single-user.

Baselines: cadgf `d53a677` → final `41daaeb`; VemCAD `7771a22`.

## 0. Slice 0 — audit (and a correction)

The first audit wrongly concluded the loop was already shipped and that re-building was redundant. That
was **wrong for the desktop**: the desktop loads the cadgf submodule's web_viewer
(`web_viewer_desktop/main.js` → `tools/web_viewer/index.html` → cadgf `app.js`), where the product-layer
solve loop (`apps/web/workbench/solver/`) is **explicitly disabled** (`app.js`: "desktop package ships
only `tools/web_viewer/**`"). So the desktop had only manual export/import-solver buttons — **no
one-click Solve**. The product loop serves the integrated/browser deploy; the cadgf-native loop is the
genuine gap for the desktop. Lesson: "exists in the product app" ≠ "exists where the user is."

## 1. Architecture decisions

- **Platform / product split.** The run+show logic lives in the cadgf web_viewer (platform), composed
  from existing commands (`solver.export-project`, `entity.applyGeometry`, `setSolverDiagnostics`).
- **Transport = router `/solve-cadgf`, not desktop IPC.** The desktop already runs a local python router
  (for convert) and the web_viewer is naturally an HTTP/loopback consumer; a router endpoint reuses that
  lifecycle and is reachable from desktop *and* browser/dev, whereas an Electron IPC spawn would bind
  solve into the desktop shell and fork from non-desktop entries. (An initial lean toward IPC was
  reversed after reading the router; the async-task convert router cleanly hosts a *synchronous*
  `/solve-cadgf` alongside.)
- **`solve_from_project` is Qt-free** (`tools/CMakeLists.txt`: links `core` only), so the transport is
  locally buildable and testable — not CI-only.
- **No writeback until Slice 2; writeback is undoable** via the existing `entity.applyGeometry`
  (`withSnapshot` → one Ctrl-Z step). A blocked/failed solve never mutates geometry.

## 2. Slices & PRs (CADGameFusion)

| Slice | What | PR | cadgf commit |
|---|---|---|---|
| 1 pt1 | run+show core: `runSolveAndShow` + `solveEnvelopeToDiagnostics` (transport-injected, no writeback) | #393 | `31e4d3d` |
| 1 pt2 | router `POST /solve-cadgf` (shells real `solve_from_project`) + `createRouterSolveTransport` + `solveVerdict` + the **Solve button** | #394 | `c43fa25` |
| 2 | geometry writeback + undo/redo: `parseSolvedVarsToUpdates` + `applySolvedGeometry` (via `entity.applyGeometry`); button writes back on solved | #395 | `4604324` |
| 3 | conflict UX by **reuse** (native loop feeds the verified `solver_action_panel` via `analysis.action_panels`); locking test; no new highlight (redundant/under-constrained deferred) | #396 | `41daaeb` |
| 4 | **A→C release**: VemCAD gitlink-only bump `d53a677` → `41daaeb` (guarded: ancestor of cadgf main); editor-light + product tests green | VemCAD A→C | gitlink-only |

End state: clicking **Solve** in the cadgf web_viewer exports the editor's CADGF-PROJ, POSTs it to the
router's `/solve-cadgf`, runs the real solver, shows solved/blocked/failed + conflicts in the existing
panels, and on a clean solve writes the geometry back undoably.

## 3. Verification

- **Router `/solve-cadgf` smoke vs the REAL `solve_from_project`** (`plm_solve_cadgf_smoke.py`):
  satisfiable → ok + vars; unsatisfiable → ok:false + analysis; invalid body → 400; `/health` advertises
  the solver. (Built locally: `cmake --build … --target solve_from_project`.)
- **web_viewer solve unit suite (node --test), locally green:**
  `solve_run` (run+show, verdict on both envelope shapes, no-writeback invariant),
  `solve_transport` (POST shape, error envelopes, URL precedence, status mapping),
  `solve_writeback` (var mapping + a **GOLDEN** vs a real `DocumentState`: slanted line flattened →
  `history.undo` restores in one step → `history.redo` re-applies),
  `solve_conflict` (conflict envelope keeps `analysis.action_panels`, classifies blocked).
- **Real export→binary** (`editor_commands.test.js`): `solver.export-project` output is consumed by
  `solve_from_project`.
- **VemCAD baseline (pre-bump):** product web tests 26/26, services/solve 12/12.
- **A→C (Slice 4), post gitlink bump `d53a677` → `41daaeb` (gitlink-only, ancestor-guarded):**
  product (apps/web) solve tests **31/31**; services solve+router+runtime **140/140**; editor-light
  (the bumped submodule's native solve loop tests: `solve_run`/`solve_transport`/`solve_writeback`/
  `solve_conflict`) **20/20**. The real editor entry consumes the native solve loop on the final cadgf main.

### Honest caveats

- **CI gating gap:** cadgf CI does **not** run the web_viewer node tests (`ci_editor_light.sh` is wired
  to no workflow) nor the router smoke; these are **locally verified**, while CI gates the build. Wiring
  `ci_editor_light.sh` + the solve smoke into CI is a recommended small follow-up.
- The **Solve button click path** itself is browser-only (not in node unit tests); all its components are
  unit-tested and the endpoint is smoke-tested.

## 4. Deployment follow-up (beyond the plan's slices)

For the loop to fire **out-of-the-box in the shipped desktop**, the desktop must (a) bundle
`solve_from_project` per platform (electron-builder `extraResources` via
`stage_bundled_cad_resources.mjs`, built in CI) and (b) launch the router with `--default-solve-cli`
(`web_viewer_desktop/main.js`, mirroring `--default-convert-cli`; `resolveSolveRouterUrl` and the
endpoint are already inert-safe if unset). This is packaging/deployment (not locally verifiable, not a
named slice) and is the recommended next deployment cut. Until then the loop works wherever the router is
launched with the solver configured (dev / a configured deploy).

---
*Generated alongside the implementation; web_viewer/router solve tests are locally verified, build is CI-gated.*
