# VemCAD App P2 Workbench Split Taskbook

Date: 2026-06-26
Status: execution taskbook, not an implementation PR
Baseline: VemCAD `origin/main` at `8e09061`; `deps/cadgamefusion` gitlink at `15a80b9`

## 0. Decision

Do P2 groundwork now, but do not start a broad workbench rewrite.

The VemCAD application is still actively developing, so the useful move is to make future
work safer: refresh the live code map, define the first small slices, and pin the gates that
must pass before any module split is called done. Large behavior changes stay out of this line.

In scope now:

- current-code inventory for the product Web workbench boundary
- characterization / contract guardrails before extraction
- small, demand-driven extraction slices
- A-to-C discipline for CADGameFusion submodule changes

Out of scope now:

- full 12k-line "god module" teardown
- fillet/chamfer or break/join geometry extraction without a real product need
- preview desktop bridge reshaping
- Electron shell convergence
- router productization
- Qt role convergence
- CADGameFusion submodule bump mixed with unrelated app work

## 1. Current Code Map

The P2 workbench split is still a cross-repo/submodule line.

The product-layer VemCAD repo now has real `apps/web` facades and solver modules, but the
live editor/preview implementation still runs primarily from CADGameFusion:

| Surface | Live source today | Product-layer facade today |
|---|---|---|
| Command registry | `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js` | `apps/web/workbench/commands/registry.js` |
| Workbench bootstrap | `deps/cadgamefusion/tools/web_viewer/ui/workspace.js` | `apps/web/workbench/bootstrap/workspace_bootstrap.js` |
| Preview runtime | `deps/cadgamefusion/tools/web_viewer/preview_app.js` | `apps/web/preview/runtime/*` |
| Product Web bootstrap | `apps/web/app.js` | already product-side |
| Solver workbench | `apps/web/workbench/solver/*` | already product-side |
| Solve panel | `apps/web/workbench/panels/solve_panel.js` | already product-side |

Current large-file sizes at the baseline:

| File | Lines | Role |
|---|---:|---|
| `command_registry.js` | 5,495 | commands, snapshots, transforms, group commands, solver export, payload helpers |
| `workspace.js` | 2,954 | editor bootstrap, DOM wiring, panels, import/export, solver action state, debug hooks |
| `preview_app.js` | 4,427 | preview bootstrap, manifest/gltf/document fallback, desktop bridge, recent/batch/open |
| Total | 12,876 | still too large for direct feature work without guardrails |

## 2. Stable Contracts

These are migration contracts. A P2 slice may rearrange internals, but must not change these
observable entry points unless a separate contract-change PR is approved first.

Product-layer contract exports:

- `registerCadCommands(commandBus, context)`
- `computeRotatePayload(center, referencePoint, targetPoint)`
- `computeScalePayload(center, referencePoint, targetPoint)`
- `bootstrapCadWorkspace({ params })`
- `createSolveWorkbenchController({ endpoint, fetchImpl })`
- `createSolveWorkbenchPanel({ root, project, controller })`
- `mountSolveWorkbenchDemo({ root, appBridge })`
- `renderCadgfPreviewCanvas({ root, cadgfDocument })`

Global contracts:

- `window.__vemcadApp.switchToEditor(documentJson)`
- `window.__vemcadApp.mountSolvePanel(root, { project, controller })`
- `window.__cadDebug`

CADGameFusion editor contracts:

- command id set registered by `registerCadCommands`
- `commandResult` shape
- undo/redo snapshot granularity
- `entity.applyGeometry`
- `solver.export-project`
- `?debug=1` debug surface
- `?manifest=`, `?gltf=`, document fallback, and preview-to-editor handoff

## 3. Execution Rules

1. Use a fresh worktree off current `origin/main`.
2. Do not edit the dirty canonical VemCAD checkout.
3. One domain per PR.
4. If the slice changes CADGameFusion code, use A-to-C:
   - CADGameFusion PR for the submodule change
   - VemCAD gitlink-only pointer bump
   - `merge-base --is-ancestor` guard before bumping
   - VemCAD `cadgamefusion-editor-light` CI as the consumer gate
5. Never mix a submodule bump with product-layer app edits unless the taskbook explicitly says so.
6. No broad formatting or helper churn while extracting.
7. Keep old imports/facades working until the product-layer replacement has a direct test.
8. Do not call a slice complete when the code merely builds; it needs the contract tests listed below.

## 4. Recommended Order

### S0 - This Taskbook

Status: current slice.

Deliverable:

- add this execution taskbook
- make it discoverable from the root README
- no runtime code change

Verification:

- links and paths resolve
- no tracked runtime file changed

### S1 - Product-Side Contract Guard

Goal: make the VemCAD product-layer facade contract explicit before any extraction.

Repo: VemCAD only.

Suggested work:

- add a small `apps/web/tests/workbench_contracts.test.js`
- import `apps/web/workbench/contracts/index.js`
- assert the expected exported functions are functions
- assert `WORKBENCH_STABLE_EXPORTS` and `WORKBENCH_GLOBAL_CONTRACTS` contain the pinned strings
- assert `apps/web/app.js` still installs `switchToEditor` and `mountSolvePanel` in the existing bootstrap test

Do not:

- change CADGameFusion
- move implementation code
- add browser-only requirements to the core product test job

Verification:

```bash
npm test
npm run test:web
```

CI expectation:

- `product-tests/core` green
- `product-tests/web-integration` green when `CADGAMEFUSION_PAT` is available

### S2 - CADGameFusion Command Guard Refresh

Goal: verify the existing command golden net still covers the extraction seam.

Repo: CADGameFusion first, then VemCAD gitlink bump only if a CADGameFusion PR lands.

Suggested work:

- inspect `tools/web_viewer/tests/editor_commands.test.js`
- keep the frozen command id set as a load-bearing contract
- add or tighten focused tests only if the current net does not pin a planned extraction
- no module move yet unless the guard gap is trivial and fully covered

Required gates:

```bash
cd deps/cadgamefusion
node --test tools/web_viewer/tests/*.test.js
bash tools/ci_editor_light.sh
```

VemCAD consumer gate after a submodule bump:

```bash
npm run test:web
```

### S3 - First Extraction: Snapshot / Shared Selection Helpers

Goal: extract low-risk command infrastructure before any domain command moves.

Repo: CADGameFusion, followed by VemCAD gitlink-only bump.

Candidate source region:

- `command_registry.js` top helper region:
  - `nowMs`
  - `emitPerfProfile`
  - `captureState`
  - `restoreState`
  - `withSnapshot`
  - selection/read-only helpers that every later command uses

Candidate target:

- `tools/web_viewer/commands/shared/snapshot.js`
- `tools/web_viewer/commands/shared/selection.js`

Rules:

- `registerCadCommands` remains exported from `command_registry.js`
- payload helpers stay where they are
- no command id changes
- no behavior edits bundled with the move

Required proof:

- focused tests prove undo/redo snapshot behavior is unchanged
- full `editor_commands.test.js` still passes
- editor roundtrip smoke still passes via `ci_editor_light`

### S4 - Demand-Driven Solver Command Extraction

Goal: extract the solver-facing command seam next, because current product development already uses
solver workbench and native solve paths.

Repo: CADGameFusion, followed by VemCAD gitlink-only bump.

Candidate source region:

- `entity.applyGeometry`
- `solver.export-project`
- any minimal helpers needed by those commands

Candidate target:

- `tools/web_viewer/commands/solver/bridge.js`

Why this before transform/fillet:

- it is tied to the active VemCAD app path
- it has product-layer tests in `apps/web/tests/*`
- it is smaller than the geometry-heavy command domains

Required proof:

```bash
cd deps/cadgamefusion
node --test tools/web_viewer/tests/solve_writeback.test.js \
  tools/web_viewer/tests/editor_commands.test.js \
  tools/web_viewer/tests/solve_run.test.js \
  tools/web_viewer/tests/solve_transport.test.js
bash tools/ci_editor_light.sh
```

VemCAD consumer proof:

```bash
npm test
npm run test:web
```

### S5 - Workspace Solver Action State Seam

Goal: reduce `workspace.js` only where it directly supports active solver UX.

Repo: CADGameFusion first, then VemCAD gitlink-only bump.

Candidate target:

- `tools/web_viewer/ui/solver_action_runtime.js`

Allowed move:

- solver action state normalization
- request/event/flow state helpers
- debug-hook adapters for solver action state

Do not move yet:

- toolbar/panel wiring broadly
- layer/session wiring
- source/insert group UI
- generic keyboard shortcuts
- preview/desktop code

Required proof:

- `solver_action_panel_smoke.js`
- existing solver action panel tests
- `editor_ui_smoke.sh` where Playwright is available, otherwise documented skip
- `ci_editor_light` remains green

### S6 - Reassess Before Bigger Geometry Domains

Stop after S5 and reassess.

Only proceed to transform/source-group/insert-group/trim/fillet slices if one of these is true:

- a real VemCAD feature needs that domain
- a bug fix already touches that domain and the extraction lowers risk
- the current file size or review burden blocks a planned product PR

Default parking lot:

- fillet/chamfer
- break/join
- broad preview desktop split
- Electron shell convergence
- router rewrite
- Qt role convergence

## 5. Verification Matrix

| Slice | VemCAD product tests | CADGameFusion tests | Browser / smoke |
|---|---|---|---|
| S1 | `npm test`, `npm run test:web` | none | none |
| S2 | `npm run test:web` after bump | `node --test tools/web_viewer/tests/*.test.js`, `ci_editor_light` | optional |
| S3 | `npm run test:web` after bump | `editor_commands.test.js`, `ci_editor_light` | editor roundtrip from light gate |
| S4 | `npm test`, `npm run test:web` | solver/editor command tests, `ci_editor_light` | editor roundtrip from light gate |
| S5 | `npm run test:web` after bump | solver action tests, `ci_editor_light` | UI smoke where Playwright exists |

Definition of done for any code slice:

- the slice has one owner repo PR
- VemCAD gitlink bump is separate if CADGameFusion changed
- no unrelated files staged
- local tests run and listed in the PR body
- CI is green or a skip is explicitly designed and documented
- the PR body states whether it is behavior-preserving or behavior-changing

## 6. Risks

| Risk | Mitigation |
|---|---|
| Existing docs overstate old progress | This taskbook is current-main anchored and should be the execution entry for P2. |
| Submodule edits get mixed with product app work | Use A-to-C and gitlink-only bump PRs. |
| A helper move silently changes undo/redo | S3 must pin snapshot and command result behavior before and after extraction. |
| Product solve UX regresses while moving CADGF commands | S4 requires both CADGF solver/editor command tests and VemCAD `test:web`. |
| Browser-only checks become fake green | Playwright smokes must be either actually run or explicitly marked skipped by design. |
| Dirty canonical checkout contaminates the slice | All work starts from fresh worktrees off current `origin/main`. |

## 7. Next Concrete Move

Recommended next PR: **S1 product-side contract guard**.

It is the smallest useful code slice:

- VemCAD only
- no submodule bump
- no behavior change
- directly protects the facade contracts that later P2 slices rely on

After S1 lands, start S2/S3 in CADGameFusion with the normal A-to-C flow.
