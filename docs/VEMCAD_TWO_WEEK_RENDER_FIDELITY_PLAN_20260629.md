# VemCAD Two-Week Render-Fidelity Development Plan (2026-06-29)

## Goal

Over the next two development weeks, move the VemCAD render-fidelity line from
one-off AutoCAD comparisons to a repeatable, reviewable evidence loop:

- trusted AutoCAD reference inputs are validated before comparison;
- VemCAD render artifacts are packaged into stable evidence bundles;
- comparison output is easy to review without reading raw JSON first;
- renderer fixes are opened only after a matched-view comparison isolates a
  concrete defect.

This goal continues the completed one-week G11 plan. It does not reopen the
renderer from aggregate pixel scores alone.

## Current State

- VemCAD `origin/main` at plan creation: `34211bf`.
- CADGameFusion gitlink at plan creation: `5871fce`.
- Open VemCAD PRs at plan creation: only the pre-existing `#1` WIP.
- The current AutoCAD reference batch is useful for diagnostics, but not a
  formal equivalence gate: the known batch still contains view-space mismatch
  cases.
- The correct hard gate remains: no AutoCAD equivalence claim unless
  `compare_vs_acad.py --require-viewspace-match` reaches
  `viewspace_status=match`.

## Non-Goals

- No GUI AutoCAD automation.
- No screenshot-derived equivalence claims.
- No X3 threshold relaxation.
- No production/deploy action.
- No CADGameFusion renderer change unless a matched-view comparison identifies
  a specific class/entity defect.
- No use of private drawings in public CI or public repos.

## Week 1 — Evidence Loop And Batch Review

### Slice 1 — Markdown Evidence Report

Deliverable:

- Extend `tools/render_regression/acad_manifest_compare.py` so every comparison
  run writes a human-readable `summary.md` beside `summary.json`,
  `summary.tsv`, `artifact_index.json`, and `contact_sheet.png`.

Acceptance:

- The Markdown report includes status, compared count, issue count, boundary
  statements, per-case view-space status, X3 summary, text flags/notes, and
  artifact links.
- It clearly says that `viewspace_mismatch` is not an AutoCAD-equivalence
  result.
- Unit tests cover pass and mismatch reports.

### Slice 2 — Artifact Bundle Index

Deliverable:

- Add a helper or CLI flag that writes a compact evidence bundle manifest for
  unattended runs: `summary.md`, `summary.json`, `summary.tsv`,
  `artifact_index.json`, `contact_sheet.png`, overlays, view-space reports,
  and optional text/semantic diagnostics.

Acceptance:

- The bundle is deterministic and path-stable.
- Missing optional artifacts are recorded, not hidden.
- Tests prove the bundle can be generated from synthetic pass and mismatch
  cases.

### Slice 3 — Existing Batch Re-Run And Prioritization

Gate:

- Uses only already-authorized local/private artifacts. No public commit of
  drawings or AutoCAD PNGs.

Deliverable:

- Re-run the current local AutoCAD batch through the improved evidence report.
- Produce a private artifact directory plus a short triage table: which cases
  are blocked by view-space mismatch, which are candidate renderer issues, and
  which need new AutoCAD exports.

Acceptance:

- No renderer changes are made from mismatched cases.
- The DEV/V ledger records command lines, output directory, and the top
  priority cases.

## Week 2 — Matched Cases And Targeted Fixes

### Slice 4 — Fresh Reference Intake, If Inputs Exist

Gate:

- Requires at least one fresh AutoCAD model-extents PNG or an explicit AutoCAD
  world plot/window rectangle.

Deliverable:

- Add the reference to a private/local run, generate the evidence bundle, and
  classify it as `matched_pass`, `matched_fail`, or `viewspace_mismatch`.

Acceptance:

- `matched_pass`: record closeout, no renderer work.
- `matched_fail`: name the smallest renderer target before coding.
- `viewspace_mismatch`: stop and request corrected input; no renderer tuning.

### Slice 5 — Targeted Renderer Fix, If Isolated

Gate:

- Only starts from a matched-view fail with an isolated defect.

Deliverable:

- CADGameFusion fix through A to C discipline when needed:
  CADGameFusion PR -> green CI -> VemCAD gitlink-only bump -> VemCAD tests.

Acceptance:

- The failing matched case improves without regressing the golden suite.
- Any new render report/provenance fields are tested.

### Slice 6 — Final Development And Verification Closeout

Deliverable:

- Update `docs/DEV_AND_VERIFICATION_RENDER_FIDELITY_TWO_WEEK_20260629.md` with
  every slice, PR, SHA, test command, CI result, artifact directory, and the
  remaining gate list.

Acceptance:

- The final MD states one of:
  - matched-view pass achieved for supplied cases;
  - matched-view fail isolated with next CADGameFusion target;
  - blocked on missing or invalid AutoCAD reference input.
- No equivalence claim is made without matched view-space proof.

## Definition Of Done

The two-week goal is complete when:

1. All autonomous engineering slices that do not require a new AutoCAD export
   have landed with tests.
2. Any user-supplied AutoCAD references have been processed through the
   matched-view harness.
3. The final DEV/V ledger is merged and contains enough commands and artifacts
   for another engineer to reproduce the result.
4. Remaining work is expressed as explicit gates, not open-ended "continue."
