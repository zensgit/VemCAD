# Render Cases Expected Size Strict — Dev & Verification (2026-07-01)

## Scope

This slice tightens the local `--cases` batch-manifest generation path for
AutoCAD reference comparisons. It does not change renderer output, compare
scoring, X3 thresholds, CADGameFusion, request-package validation, or private
drawing fixtures.

## Problem

The request-validation path already rejects non-integer expected sizes, but the
direct `--cases` path generated `acad_manifest.json` with `int(...)`:

- `true` could become `1`;
- `1600.5` could become `1600`;
- bad explicit dimensions could be rewritten into a plausible manifest before
  validation ever saw the original input.

That made the generator less fail-closed than the later validation stage.

## Changes

- `tools/render_regression/acad_reference_batch.py`
  - reuses the strict positive-integer expected-size parser in `_manifest_case`;
  - only falls back to reading the AutoCAD PNG size when `expected_size` is
    omitted;
  - blocks malformed explicit `expected_size` declarations instead of
    truncating/coercing them.
- `tools/render_regression/tests/test_acad_reference_batch.py`
  - adds coverage for a malformed direct `--cases` expected size;
  - confirms the generator blocks and does not emit a forged manifest or
    candidate-case file.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
```

Result:

```text
35 passed in 9.16s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
232 passed in 38.05s
```

## Boundary

This is direct batch-manifest input hardening. Invalid explicit `expected_size`
values no longer enter generated manifests. The harness still does not compare
renders in this step and does not claim AutoCAD equivalence.
