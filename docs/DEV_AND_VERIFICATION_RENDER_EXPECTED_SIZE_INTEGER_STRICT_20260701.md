# Render Expected Size Integer Strictness — Dev & Verification (2026-07-01)

## Boundary

This slice tightens AutoCAD reference size-contract parsing. It does not change
render output, X3 scoring, view-space thresholds, private drawing handling, or
AutoCAD equivalence claims.

## Problem

`expected_size` / `requested_expected_size` represent PNG pixel dimensions.
Those dimensions must be positive integers. The manifest and request-validation
paths previously used `int(...)`, so values such as `800.9` could be silently
truncated to `800` and pass the size-contract gate.

## Implementation

- `acad_reference_manifest.py`
  - parses manifest `expected_size` with a strict positive-integer helper;
  - accepts JSON integers and digit-only strings;
  - rejects floats, booleans, empty values, and non-positive numbers as
    `invalid_expected_size`.
- `acad_reference_batch.py`
  - applies the same strict parsing to request-declared
    `requested_expected_size` / legacy `expected_size`;
  - reports `invalid_requested_expected_size` for non-integer dimensions.
- Docs/tests
  - README and the G11 runbook now state that expected sizes must be positive
    integers;
  - tests cover manifest and request-validation rejection of fractional/bool
    dimensions.

## Verification

Focused:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_manifest.py \
  tools/render_regression/tests/test_acad_reference_batch.py::test_batch_generator_validation_rejects_non_integer_requested_expected_size \
  tools/render_regression/tests/test_acad_manifest_compare.py::test_readme_documents_manifest_expected_size_as_required \
  tools/render_regression/tests/test_reference_input_runbook_docs.py -q
```

Result:

```text
13 passed in 0.65s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
225 passed in 38.46s
```

## Closeout

The size contract now rejects fractional or boolean dimensions before any
returned-reference or matched-view comparison is trusted.
