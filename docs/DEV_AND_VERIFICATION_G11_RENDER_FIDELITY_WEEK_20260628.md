# DEV/V — G11 Render-Fidelity Week (2026-06-28)

## Scope

This ledger tracks the one-week render-fidelity goal:

> Build a repeatable, evidence-backed G11/B11 AutoCAD comparison loop using
> matched view-space contracts, then only reopen renderer work if a matched
> comparison isolates a concrete defect.

## Boundary

- No GUI AutoCAD automation.
- No screenshot-derived equivalence claims.
- No global renderer tuning from aggregate X3 movement.
- No X3 threshold relaxation.
- No AutoCAD-equivalence claim while the view-space contract is `mismatch` or
  `unavailable`.

## Baseline

- VemCAD `origin/main` at plan creation: `295b040`.
- Text-layout diagnostic closeout:
  - G11 all text: no layout flags; note-only rotated bbox caveat.
  - G11 `HC_BTL_BLK`: no layout flags or notes.
- Hard remaining gate:
  - obtain a clean AutoCAD plot/export PNG or an explicit matching render
    window before interpreting X3 as fidelity.

## Slice Log

### Slice 0 — One-Week Plan

Status: merged in PR #167 (`73ad85f`).

Deliverables:

- `docs/VEMCAD_ONE_WEEK_RENDER_FIDELITY_PLAN_20260628.md`
- this DEV/V ledger

Verification:

- Docs-only scope.
- Markdown content reviewed against current boundary docs:
  - `VEMCAD_G11_VIEWSPACE_CONTRACT_20260628.md`
  - `VEMCAD_G11_TEXT_LAYOUT_DIAGNOSTICS_20260628.md`

### Slice 1 — AutoCAD Reference Manifest Gate

Status: merged in PR #168 (`5436247`).

Deliverables:

- `tools/render_regression/acad_reference_manifest.py`
- `tools/render_regression/tests/test_acad_reference_manifest.py`

Behavior:

- Accepts only gate-grade AutoCAD references (`plot-export`, `exportpng`,
  `publish`, `plot-raster`) with a matched-view contract (`model-extents` or
  `explicit-window`).
- Fails closed for screenshot/viewport captures, missing files, invalid schema,
  missing `drawing_id`, invalid/mismatched expected image size, or unmatched
  view contract.
- Emits a validation report plus a gate-trusted case stub for the Day 2 harness.

Verification:

- `python3 -m pytest tools/render_regression/tests/test_acad_reference_manifest.py -q`
  - `8 passed`
- `python3 -m pytest tools/render_regression/tests/test_compare_vs_acad.py tools/render_regression/tests/test_autocad_batch_compare.py -q`
  - `20 passed`
- `python3 -m pytest tools/render_regression/tests -q`
  - `75 passed`

Boundary:

- No private drawing or AutoCAD image committed.
- No rendering, no comparison, no equivalence claim.
- This slice only decides whether supplied AutoCAD references are eligible for
  the matched-view X3 path.

### Slice 2 — Manifest-Driven Matched-View Harness

Status: merged in PR #169 (`989ec77`).

Deliverables:

- `tools/render_regression/acad_manifest_compare.py`
- `tools/render_regression/tests/test_acad_manifest_compare.py`

Behavior:

- Joins a validated AutoCAD reference manifest with already-rendered VemCAD
  candidate PNG artifacts.
- Calls the existing `compare_vs_acad.py --viewspace-report
  --require-viewspace-match` path for each case.
- Writes `summary.json`, `summary.tsv`, per-case view-space reports, and
  overlays when the underlying diff engine considers the pair comparable.
- Carries candidate provenance fields such as render report path, semantic mask
  path, render image digest, and diagnostic metadata.
- Returns non-zero for blocked manifests, missing candidate artifacts, or
  `viewspace_mismatch`.

Verification:

- `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q`
  - `4 passed`
- `python3 -m pytest tools/render_regression/tests/test_acad_reference_manifest.py tools/render_regression/tests/test_compare_vs_acad.py tools/render_regression/tests/test_autocad_batch_compare.py -q`
  - `28 passed`
- `python3 -m pytest tools/render_regression/tests -q`
  - `79 passed`

Boundary:

- No DXF rendering; candidate PNGs are inputs.
- No private drawing or AutoCAD image committed.
- No AutoCAD-equivalence claim; even matched view-space only means X3 is
  eligible to be interpreted.

### Slice 3 — Triage Summary and Artifact Index

Status: in progress in this PR.

Deliverables:

- Extend `tools/render_regression/acad_manifest_compare.py`.
- Extend `tools/render_regression/tests/test_acad_manifest_compare.py`.

Behavior:

- Adds `text_flags` and `text_notes` columns to the harness TSV.
- If a candidate case includes `render_report`, reuses
  `text_provenance_diagnostics.analyze_report()` to surface text-placement
  flag/note counts in the per-case JSON row.
- Writes `artifact_index.json`, listing stable artifact paths for AutoCAD
  reference PNGs, VemCAD candidate PNGs, overlays, view-space reports, render
  reports, semantic masks/reports, and text-provenance summaries.

Verification:

- `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q`
  - `5 passed`
- `python3 -m pytest tools/render_regression/tests -q`
  - `80 passed`

Boundary:

- Diagnostic enrichment only; no renderer change.
- Text provenance is not a gate; unreadable text diagnostics are recorded as
  diagnostic errors without turning the X3 view-space gate into a text gate.

## Verification Matrix

| Slice | Local tests | CI | Runtime / artifact proof | Result |
| --- | --- | --- | --- | --- |
| Slice 0 plan | docs-only | docs-only PR #167, no checks | n/a | merged |
| Slice 1 AutoCAD reference manifest | `test_acad_reference_manifest.py`; adjacent compare tests; full `tools/render_regression/tests` | PR #168: `pytest`, `build-and-smoke` | synthetic PNG/DXF fixtures only | merged |
| Slice 2 manifest compare harness | `test_acad_manifest_compare.py`; adjacent manifest/compare tests; full `tools/render_regression/tests` | PR #169: `pytest`, `build-and-smoke` | synthetic PNG pairs only; no renderer | merged |
| Slice 3 triage summary / artifact index | `test_acad_manifest_compare.py`; full `tools/render_regression/tests` | pending | synthetic PNG + synthetic render report only; no renderer | local green |

## Evidence To Fill During The Week

For each future slice, append:

- branch / PR / merge SHA;
- exact commands;
- local test output;
- CI check names and result;
- render image digest or workflow run, if relevant;
- AutoCAD input provenance, if used;
- comparison verdict and why it is or is not an equivalence claim.

## Final Closeout Template

At the end of the week, record:

```text
Final VemCAD origin/main:
Final CADGameFusion gitlink:
Render image / workflow evidence:
AutoCAD reference:
View-space status:
X3 result:
Semantic/text diagnostics:
Conclusion:
Next action:
```
