# Render Cases Capture Contract Required — Dev & Verification (2026-07-01)

## Scope

This slice tightens the direct `--cases` batch-manifest generation path for
AutoCAD reference comparisons. It does not change renderer output, compare
scoring, X3 thresholds, CADGameFusion, request-package validation, or private
drawing fixtures.

## Problem

The request-validation path already requires capture contract fields, but the
direct `--cases` generator still filled missing values with defaults:

- missing `capture_method` became `plot-export`;
- missing `view_contract` became `model-extents`.

That silently converted an incomplete hand-written case file into a trusted
manifest declaration. For reference inputs, missing capture/view provenance
should fail closed rather than be guessed.

## Changes

- `tools/render_regression/acad_reference_batch.py`
  - requires `capture_method` and `view_contract` in direct `--cases` input;
  - removes the direct-path defaulting to `plot-export` / `model-extents`.
- `tools/render_regression/tests/test_acad_reference_batch.py`
  - updates the positive direct `--cases` fixture to declare the contract;
  - adds a missing-contract fail-closed regression test.
- `tools/render_regression/README.md` and
  `docs/VEMCAD_G11_AUTOCAD_REFERENCE_INPUT_RUNBOOK_20260628.md`
  - document that direct `--cases` follows the same explicit capture-contract
    discipline.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
```

Result:

```text
36 passed in 9.35s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
233 passed in 38.26s
```

## Boundary

This is direct batch-manifest input hardening. The generator no longer invents a
capture/view contract for hand-written cases. The harness still does not compare
renders in this step and does not claim AutoCAD equivalence.
