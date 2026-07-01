# Render Provenance Size Bytes Strictness — Dev & Verification (2026-07-01)

## Boundary

This slice tightens request provenance validation for declared file byte sizes.
It does not change render output, X3 scoring, view-space thresholds, expected
PNG dimensions, private drawing handling, or AutoCAD equivalence claims.

## Problem

`source_dxf_size_bytes`, `current_acad_png_size_bytes`, and
`candidate_png_size_bytes` are provenance checks used to detect stale or
hand-edited recapture requests. They previously used `int(...)`, so fractional
or boolean values could be silently coerced before comparison.

## Implementation

- `acad_reference_batch.py`
  - adds strict non-negative-integer parsing for declared byte-size fields;
  - accepts JSON integers and digit-only strings;
  - rejects floats, booleans, negative values, and non-numeric strings with
    `<label>_size_invalid`.
- Tests
  - cover fractional source DXF byte size and boolean candidate PNG byte size;
  - preserve the existing size-mismatch behavior for valid integer declarations.

## Verification

Focused:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_batch.py::test_batch_generator_rejects_non_integer_size_byte_declarations \
  tools/render_regression/tests/test_acad_reference_batch.py::test_batch_generator_validates_current_acad_png_provenance_when_available -q
```

Result:

```text
2 passed in 0.30s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
226 passed in 35.34s
```

## Closeout

Request provenance byte-size fields now fail closed when they are not explicit
non-negative integers, instead of being coerced by Python's `int(...)`.
