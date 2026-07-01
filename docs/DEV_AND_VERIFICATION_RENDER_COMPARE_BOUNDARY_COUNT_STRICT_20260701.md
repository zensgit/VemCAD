# Render Compare Boundary Count Strict — Dev & Verification (2026-07-01)

## Scope

This slice tightens the AutoCAD manifest compare artifact-index boundary. It
does not change renderer output, compare scoring, X3 thresholds, CADGameFusion,
request generation, or private drawing fixtures.

## Problem

`acad_manifest_compare.py` writes an artifact index with a boundary flag:

```json
"compares_renders": true
```

That flag is derived from `compared_count`. The code used `int(...)` directly,
so malformed report values could be coerced into a positive comparison count:

- `true` became `1`;
- `1.5` became `1`;
- non-digit strings could crash artifact-index generation.

That makes the boundary less honest: a malformed report can claim that compare
work happened even when the count is not a real non-negative integer.

## Changes

- `tools/render_regression/acad_manifest_compare.py`
  - adds strict non-negative integer parsing for `compared_count`;
  - accepts JSON integers and digit-only strings;
  - treats booleans, fractions, negatives, and non-digit strings as invalid.
- `tools/render_regression/tests/test_acad_manifest_compare.py`
  - adds boundary coverage for malformed `compared_count` values;
  - confirms a digit-only string still preserves the positive boundary case.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
```

Result:

```text
17 passed in 1.64s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
231 passed in 35.63s
```

## Boundary

This is artifact-index boundary hardening. Invalid `compared_count` values no
longer satisfy the `compares_renders` declaration or crash artifact generation.
The harness still does not render DXFs and does not claim AutoCAD equivalence.
