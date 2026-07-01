# Render Artifact Route Count Integer Strict — Dev & Verification (2026-07-01)

## Scope

This slice tightens read-only AutoCAD artifact routing guards. It does not
change renderer output, compare scoring, X3 thresholds, CADGameFusion, request
generation, or private drawing fixtures.

## Problem

`acad_artifact_route.py` aggregates count fields from artifact indexes so CI and
operators can assert route distributions, action counts, issue-code counts,
view-space buckets, and compare totals. Several aggregation paths used
`int(...)` directly, so malformed JSON values could be coerced into valid counts:

- `true` became `1`;
- `1.5` became `1`;
- negative counts could flow into count maps.

That weakens strict route guards because a malformed artifact index can satisfy
`--require-*-count` checks by accident.

## Changes

- `tools/render_regression/acad_artifact_route.py`
  - adds strict non-negative integer parsing for routed counts;
  - accepts JSON integers and digit-only strings;
  - ignores booleans, fractions, negatives, and non-digit strings when
    aggregating artifact-index counts.
- `tools/render_regression/tests/test_acad_artifact_route.py`
  - adds coverage for malformed action-count maps;
  - adds coverage for malformed scalar compare counts.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
```

Result:

```text
81 passed in 0.21s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
230 passed in 36.98s
```

## Boundary

This is route/report guard hardening. Invalid count fields now fail to satisfy
required-count gates instead of being coerced into valid values. The router still
does not compare renders and does not claim AutoCAD equivalence.
