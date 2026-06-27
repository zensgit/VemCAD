# P2 Workbench Split — S4 Landing + S5 Decision (Closeout)

Date: 2026-06-27
Scope: closes out the P2 workbench-split execution line. Continues
`DEV_AND_VERIFICATION_P2_WORKBENCH_SPLIT_S1_S3_20260627.md` (#118), which covers
S0–S3; this records S4 landing and the S5 decision, and supersedes that doc's
"gated remainder" section.

## Final line status

| Slice | What | PRs | State |
|---|---|---|---|
| S0 | P2 taskbook + README link | VemCAD #113 | MERGED |
| S1 | Product-side facade contract guard | VemCAD #116 | MERGED |
| S2 | CADGameFusion command guard refresh | — | VERIFIED, no change needed |
| S3 | Extract snapshot + selection helpers | CADGameFusion #419 + VemCAD #120 | LANDED |
| S4 | Extract solver command bridge | CADGameFusion #421 + VemCAD #121 | LANDED |
| S5 | Workspace solver-action state seam | — | DEFERRED to reassess gate (owner decision) |

VemCAD `main` now pins `deps/cadgamefusion` at `4327230` (S4). Every landed slice
was proven behavior-preserving and consumer-verified; nothing is mid-flight.

## S4 — solver command bridge (CADGameFusion #421 + VemCAD #121) — LANDED

Moved out of `command_registry.js` into `commands/solver/bridge.js`, behavior-
preserving:
- `runApplyGeometry` (behind `entity.applyGeometry`) — moved verbatim.
- `buildSolverProject` (the CADGF-PROJ builder behind `solver.export-project`) —
  extracted from the inline `execute`; the `commandResult` wrapping and
  no-constraints guard stay with the command registration.

Verification:
- CADGameFusion `node --test tools/web_viewer/tests/editor_commands.test.js`
  → 307 pass (golden net unchanged, incl. `solver.export-project` ×3 +
  `entity.applyGeometry` ×2); full web_viewer suite → 757 pass;
  `tools/ci_editor_light.sh` node + roundtrip 2/2 green. CADGameFusion #421 CI
  → 16/16 green.
- VemCAD consumer gate (gitlink `1a148f9 → 4327230`, forward-bump guarded):
  `npm run test:web` → 123 pass (S1 facade contract guard green against the
  extracted submodule); `npm test` → 140 pass; `npm run smoke:solve-demo` → PASS.
  VemCAD #121 CI (`editor-light` + `build-and-smoke`) → green.

## S5 — workspace solver-action state seam — DEFERRED (owner decision)

Sub-scoping `tools/web_viewer/ui/workspace.js` showed S5 is **not** the clean
verbatim extraction that S3/S4 were. The solver-action surface is **mutable
closure state** — `solverActionState`, `solverActionRequestState`,
`solverActionEventState` declared inside `bootstrapCadWorkspace` — captured by
closures across five regions (state definition, the `window.__cadDebug` getters,
the event/update logic, and the panel/banner/console wiring). There is no
cohesive movable subset: completing S5 means converting closure state into an
injected `SolverActionRuntime` and rewiring every read/write site, which carries
real behavior-preservation risk (mutation timing, reference identity).

Per the taskbook's S6 reassess gate ("Stop after S5 and reassess") and an
explicit owner decision, S5 is **deferred**: the `workspace.js` solver-action
split waits until a real product feature or bugfix needs that domain, at which
point it should be done as a designed state-manager refactor with golden-net +
`solver_action_panel` test coverage — not a mechanical move.

## Parking lot (unchanged, taskbook S6)

fillet/chamfer, break/join, full workbench teardown, desktop shell convergence,
router rewrite/productization, Qt role convergence — none to be started without a
real product need.
