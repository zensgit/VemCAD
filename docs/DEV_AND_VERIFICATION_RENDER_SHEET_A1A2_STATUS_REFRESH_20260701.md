# Render Sheet A1a/A1a-2 Status Refresh — Dev & Verification (2026-07-01)

## Boundary

This slice refreshes workflow comments and DEV/V status text for the
sheet-readiness audit line. It does not change render output, audit thresholds,
workflow behavior, private drawing handling, or `view=sheet` defaulting.

## Problem

The render-image workflow comment and A1a DEV/V doc still described the curated
sheet corpus as a future A1a-2 follow-up. That was stale: A1a-2 now exists as a
synthetic fast-gate corpus for verdict logic.

The important boundary remains: synthetic A1a-2 coverage is not enough to make
`view=sheet` the default. That still needs a real operator/training drawing
corpus with human-confirmed expectations.

## Implementation

- Updated the render-image workflow comment:
  - A1a-2 synthetic verdict corpus exists.
  - real default-readiness still needs operator/training drawing evidence.
- Updated the A1a DEV/V doc:
  - CI step is now blocking.
  - A1a-2 is complete as a fast-gate regression check.
  - real corpus remains the gated default-readiness input.
- Added text guard tests for the workflow comment and A1a doc status.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_sheet_a1a2_status_docs.py -q
```

Result:

```text
2 passed in 0.00s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
218 passed in 35.56s
```

Workflow YAML parse:

```bash
python3 - <<'PY'
import yaml
with open('.github/workflows/render-image.yml', 'r', encoding='utf-8') as f:
    yaml.safe_load(f)
print('yaml ok')
PY
```

Result:

```text
yaml ok
```

## Closeout

The sheet-readiness status text now separates three facts:

- A1a CI plumbing is blocking.
- A1a-2 synthetic verdict logic coverage is complete.
- `view=sheet` default-readiness still needs real operator/training drawing
  evidence.
