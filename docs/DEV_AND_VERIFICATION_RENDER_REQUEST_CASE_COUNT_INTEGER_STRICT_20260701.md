# Render Reference Request Case Count Integer Strict — Dev & Verification (2026-07-01)

## Scope

This slice tightens AutoCAD reference request metadata validation. It does not
change renderer output, compare scoring, X3 thresholds, CADGameFusion, or
private drawing fixtures.

## Problem

`reference_request.json` may declare `case_count` so generated handoff packages
can detect stale or hand-edited request metadata. The validator checked that
value with `int(...)`, which could silently coerce JSON values that are not real
integer declarations:

- `true` became `1`;
- `1.5` became `1`.

For a one-case request, either value could pass as if the request explicitly
declared `case_count: 1`.

## Changes

- `tools/render_regression/acad_reference_batch.py`
  - `_request_case_count_issues(...)` now uses the same strict integer helper as
    byte-size provenance checks;
  - booleans, fractional numbers, negative numbers, and non-digit strings emit
    `request_case_count_invalid`.
- `tools/render_regression/tests/test_acad_reference_batch.py`
  - keeps the existing invalid string case;
  - adds a regression for boolean and fractional `case_count`.
- `tools/render_regression/README.md`
  - documents that declared `case_count` must be a non-negative integer.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
```

Result:

```text
34 passed in 9.13s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
228 passed in 37.82s
```

## Boundary

This is a request-package validation gate. Missing `case_count` remains allowed
for older or manual request packages; when present, it must be an explicit
non-negative integer and must match the full unfiltered request case list.
