# P2 Workbench Split — Dev & Verification (S0–S3)

Date: 2026-06-27
Scope: execution + verification record for the first slices of
`docs/VEMCAD_APP_P2_WORKBENCH_SPLIT_TASKBOOK_20260626.md` (the P2 taskbook, #113).
This document records what landed, the evidence each slice rests on, and the
gated remainder. It authorizes nothing beyond what is already merged.

Baseline note: the taskbook baselined VemCAD `origin/main` at `8e09061` with
`deps/cadgamefusion` gitlink `15a80b9`. During this execution `main` advanced via
two CADGameFusion consume PRs — `#114` (Zhuque font, gitlink → `4b5f4bb`) and
`#115` (CJK text weight, gitlink → `e750926`) — so the current baseline is
VemCAD `main` `39e8d50` / gitlink `e750926`. The slices below are anchored to
current `main`, not the stale taskbook SHAs.

## Status

| Slice | What | PR | State | Evidence |
|---|---|---|---|---|
| S0 | P2 execution taskbook + README link | VemCAD #113 | MERGED `f98948d` | doc-only; current-main anchored |
| S1 | Product-side facade contract guard | VemCAD #116 | MERGED `39e8d50` | CI core + web-integration green |
| S2 | CADGameFusion command guard refresh | — | VERIFIED, no change needed | existing golden net already pins all 5 aspects |
| S3 | Extract snapshot + selection helpers | CADGameFusion #419 | OPEN `de5eaac` | golden 307 / suite 757 / roundtrip 2 |
| S3-bump | VemCAD gitlink-only pointer bump | — | GATED on #419 merge | A→C `merge-base --is-ancestor` guard |

## S1 — product-side contract guard (VemCAD-only) — DONE

New `apps/web/tests/workbench_contracts.test.js` pins the facade declared in
`apps/web/workbench/contracts/index.js`: `WORKBENCH_STABLE_EXPORTS` (8) and
`WORKBENCH_GLOBAL_CONTRACTS` (3) are frozen and exactly the documented surface,
and every documented stable export resolves to a callable on the barrel — the
load-bearing anti-drift guard for S3+ extraction. `web_bootstrap_entry.test.js`
gained one case tying the documented `window.__vemcadApp.*` globals to the bridge
`installVemcadAppBridge` actually installs (`switchToEditor`, `mountSolvePanel`);
`__cadDebug` is installed by the CADGameFusion editor bootstrap, so it stays
pinned at the documented-list level only.

The barrel transitively re-exports from `deps/cadgamefusion`, so the guard runs
in the submodule-aware `test:web` (web-integration) job, not the no-submodule
core `npm test` glob. Confirmed picked up by the `apps/web/tests/*.test.js` glob:
`test:web` count 119 → 123.

Verification (local + CI on the merge base):
- `npm test` → 140 passed
- `npm run test:web` → 123 passed (was 119; +3 contract + 1 bootstrap tie)
- `npm run smoke:solve-demo` → PASS
- CI `product-tests` core + web-integration → green (#116)

## S2 — CADGameFusion command guard refresh — VERIFIED, NO CHANGE

The existing golden net `tools/web_viewer/tests/editor_commands.test.js` already
pins every aspect S2 calls for, so no new test was added (the taskbook's "不急着
搬代码"):
- command id set — a frozen `GOLDEN_COMMAND_IDS` array under a dedicated
  "command_registry.js compatibility surface" characterization block, authored
  explicitly before the planned workbench-split decomposition.
- `commandResult` envelope — asserted via `result.ok` / `result.changed`.
- undo/redo snapshot — `history.undo` / `history.redo` round-trip cases.
- `entity.applyGeometry` — dedicated apply + guarded-no-op cases.
- `solver.export-project` — CADGF-PROJ shape + no-constraints + solve-consume.

This file is wired into the CI gates (`tools/ci_editor_light.sh`), so the net is
load-bearing, not advisory.

## S3 — extract snapshot + selection helpers (CADGameFusion #419) — PROVEN, PR OPEN

Moved out of the 5,495-line `tools/web_viewer/commands/command_registry.js`,
bodies unchanged:
- `commands/shared/snapshot.js` — `nowMs`, `emitPerfProfile`, `captureState`,
  `restoreState`, `withSnapshot` (the snapshot/undo-redo seam; `withSnapshot` has
  33 call sites). Imports `commandResult` from `../command_bus.js`.
- `commands/shared/selection.js` — `hasSelection`, `selectedEntities`,
  `isReadOnlyEntity`, `hasSameEntityIds` (pure read-only helpers).

`command_registry.js` imports the seam; `registerCadCommands` and the command id
set are untouched. The source-group transform helpers stay in the registry and
import `isReadOnlyEntity` back from `shared/selection.js` (the deliberate boundary
that avoids dragging in `isSourceGroupEntity` / `summarizeSourceGroupMembers`).

Verification (behavior-preserving, local on CADGF `e750926`):
- `node --test tools/web_viewer/tests/editor_commands.test.js` → 307 pass
  (golden net unchanged)
- `node --test tools/web_viewer/tests/*.test.js` → 757 pass
- `tools/ci_editor_light.sh` → node tests + editor roundtrip smoke 2/2 green
- CI `solve unit tests (web_viewer, node)` on #419 → pass

Known non-issue: `ci_editor_light.sh` step 3b ("product offline import-graph")
resolves the VemCAD consumer's `apps/web/app.js`, which does not exist in a
standalone CADGameFusion checkout. It fails identically on the pristine baseline
(confirmed via a stash control) and is exercised by VemCAD `npm run test:web`
after the gitlink bump — it is not a regression from this slice.

## Gated remainder

- S3 VemCAD gitlink bump: a pointer-only bump consuming CADGameFusion #419, gated
  on #419 merging to CADGameFusion `main` first (the A→C `merge-base
  --is-ancestor` guard requires the target commit to be on `main`). Consumer gate:
  VemCAD `cadgamefusion-editor-light` / `test:web`.
- S4 — solver command seam: extract `entity.applyGeometry` + `solver.export-project`
  command logic to `tools/web_viewer/commands/solver/bridge.js`, then a VemCAD
  gitlink bump. Sequential after S3 lands (same `command_registry.js`).
- S5 — workspace solver action state seam: extract solver-action state /
  normalization / debug-hook adapters from `tools/web_viewer/ui/workspace.js`
  to `tools/web_viewer/ui/solver_action_runtime.js`, then a VemCAD gitlink bump.
- Parking lot (taskbook S6 — do not start without a real product need):
  fillet/chamfer, break/join, full workbench teardown, desktop shell convergence,
  router rewrite/productization, Qt role convergence.
