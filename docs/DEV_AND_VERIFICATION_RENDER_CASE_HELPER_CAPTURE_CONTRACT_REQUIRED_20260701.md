# Render Case Helper Capture Contract Required — Dev & Verification (2026-07-01)

## Scope

This slice tightens the single-case AutoCAD reference helper
`acad_reference_case.py`. It does not change renderer output, compare scoring,
X3 thresholds, CADGameFusion, batch generation, request-package validation, or
private drawing fixtures.

## Problem

The batch and request paths now require explicit capture/view contract fields,
but the single-case helper still defaulted CLI inputs:

- missing `--capture-method` became `plot-export`;
- missing `--view-contract` became `model-extents`.

That let a quick single-case manifest claim a trusted capture contract even when
the operator did not explicitly provide one.

## Changes

- `tools/render_regression/acad_reference_case.py`
  - makes `--capture-method` and `--view-contract` required CLI arguments.
- `tools/render_regression/tests/test_acad_reference_case.py`
  - updates positive/error fixtures to pass the explicit contract;
  - adds missing-contract argparse coverage.
- `docs/VEMCAD_G11_AUTOCAD_REFERENCE_INPUT_RUNBOOK_20260628.md`
  - updates the single-case example command.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_case.py -q
```

Result:

```text
3 passed in 0.81s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
234 passed in 35.91s
```

## Boundary

This is single-case input-contract hardening. The helper no longer invents a
capture/view contract when creating a manifest. It still does not render DXFs or
claim AutoCAD equivalence.
