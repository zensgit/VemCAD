# Render Redteam Script Field Refresh — Dev & Verification (2026-07-01)

## Boundary

This slice keeps render-regression diagnostic scripts executable after the
compare result field rename. It does not change compare scoring, renderer
behavior, golden gates, or AutoCAD equivalence claims.

## Problem

`CompareResult` exposes the combined gate metric as `ink_iou`. The redteam
diagnostic scripts still read the old `geometry_ink_iou` attribute, so running
`redteam_exp.py` or `redteam_exp2.py` failed with:

```text
AttributeError: 'CompareResult' object has no attribute 'geometry_ink_iou'
```

That made the offline redteam probes unusable exactly when they are needed to
explain evidence limits such as scale normalization, color blindness, and
text-heavy false failures.

## Implementation

- `tools/render_regression/redteam_exp.py`
  - uses `CompareResult.ink_iou`.
- `tools/render_regression/redteam_exp2.py`
  - uses `CompareResult.ink_iou`.
  - keeps the current combined-ink wording from the semantic-note refresh.
- `tools/render_regression/tests/test_redteam_scripts.py`
  - runs both scripts as subprocesses and asserts they complete and print IoU
    output plus their temporary artifact directory.

## Verification

Focused:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_redteam_scripts.py \
  tools/render_regression/tests/test_compare.py -q
```

Result:

```text
20 passed in 5.31s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
214 passed in 42.27s
```

## Closeout

The redteam scripts now run against the current `CompareResult` shape. They
remain diagnostic-only tools; no gate, renderer, or X3 behavior changed.
