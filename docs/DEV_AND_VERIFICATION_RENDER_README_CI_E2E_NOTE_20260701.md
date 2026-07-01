# Render README CI E2E Note Refresh — Dev & Verification (2026-07-01)

## Boundary

This slice refreshes the render regression README's D2/golden-corpus wording.
It does not change render output, compare scoring, golden gates, private
drawing handling, or AutoCAD equivalence claims.

## Problem

The README still described pytest plus the render-to-compare end-to-end path as
future D3 work. That was stale after the golden E2E gate shipped: `ci_render_golden.py`
produces per-pass render_cli PNGs and `ci_e2e_check.py` consumes them in CI to
verify non-blank, dimension-correct, deterministic golden renders.

## Implementation

- Updated the README to state that pytest plus the render_cli E2E are already
  wired into CI.
- Named `ci_e2e_check.py` as the shipped render-to-compare golden-corpus gate.
- Added a README guard test rejecting the old D3-plan wording.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
```

Result:

```text
14 passed in 1.66s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
216 passed in 37.42s
```

## Closeout

The README now matches the shipped CI shape. The semantic-mask limitation and
AutoCAD matched-view input boundary remain unchanged.
