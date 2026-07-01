# Render Diff Common-Window Doc Refresh — Dev & Verification (2026-06-30)

## Boundary

This slice refreshes stale version-diff documentation. It does not change diff
classification, render service behavior, renderer code, X3 scoring, or any
AutoCAD equivalence claim.

## Problem

`tools/render_regression/diff.py` still said the common-window follow-up was
deferred and that extents-changing revision pairs would be flagged until then.
That was stale: the service-level `/diff` common-window path already renders
both revisions in a shared world window and calls the engine with
`shared_view=True`.

## Implementation

- `tools/render_regression/diff.py`
  - updates the module docstring to describe the two current paths:
    - legacy per-extents image inputs still fail closed on view-space mismatch;
    - common-window service inputs use `shared_view=True` and preserve the common
      pixel grid for extents-changing revisions.
- `tools/render_regression/tests/test_diff.py`
  - adds a regression that rejects the old deferred wording and requires the
    shipped `shared_view=True` description.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_diff.py -q
```

Result:

```text
16 passed in 1.24s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
213 passed in 34.73s
```

## Closeout

The version-diff module comments now match the shipped common-window behavior:
legacy image-only inputs remain fail-closed, while the service-owned shared-view
path handles extents-changing revisions without misleading re-centering.
