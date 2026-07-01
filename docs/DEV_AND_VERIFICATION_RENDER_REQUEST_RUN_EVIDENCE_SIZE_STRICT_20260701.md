# Render Request Run Evidence Size Strict — Dev & Verification (2026-07-01)

## Scope

This slice tightens evidence formatting inside
`acad_reference_request_run.py`. It does not change renderer output, compare
scoring, X3 thresholds, CADGameFusion, request validation, intake validation, or
private drawing fixtures.

## Problem

Request-run case actions copy provenance and returned-reference inspection
fields into operator-facing evidence strings. The code used
`isinstance(value, int)` checks, which accept Python booleans:

- `size_bytes=true` could appear as size `True`;
- `width=true` plus an integer height could produce a malformed returned size;
- negative or fractional size fields could leak into evidence text.

These fields are normally produced by the harness, but evidence formatting
should still fail closed if an upstream artifact is stale or hand-edited.

## Changes

- `tools/render_regression/acad_reference_request_run.py`
  - adds strict integer parsing helpers for evidence sizes;
  - rejects booleans, fractions, negatives, and non-digit strings for
    `*_size_bytes`;
  - requires positive integer returned PNG dimensions before printing
    `returned_png_size`.
- `tools/render_regression/tests/test_acad_reference_request_run.py`
  - adds direct coverage that malformed size fields are omitted from evidence
    while a valid digit-only size is preserved.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
```

Result:

```text
14 passed in 14.81s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
235 passed in 37.10s
```

## Boundary

This is evidence/report hardening only. It does not compare renders, change
routing decisions, or claim AutoCAD equivalence.
