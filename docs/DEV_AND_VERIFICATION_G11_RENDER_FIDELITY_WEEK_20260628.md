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

Status: in progress in this PR.

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

## Verification Matrix

| Slice | Local tests | CI | Runtime / artifact proof | Result |
| --- | --- | --- | --- | --- |
| Slice 0 plan | docs-only | docs-only PR #167, no checks | n/a | merged |
| Slice 1 AutoCAD reference manifest | `test_acad_reference_manifest.py`; adjacent compare tests; full `tools/render_regression/tests` | pending | synthetic PNG/DXF fixtures only | local green |

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
