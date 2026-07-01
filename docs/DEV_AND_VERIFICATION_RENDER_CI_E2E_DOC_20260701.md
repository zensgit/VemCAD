# Render CI E2E Gate Note Refresh — Dev & Verification (2026-07-01)

## Boundary

This slice refreshes one stale operator-facing docstring for the render
regression CI entrypoint. It does not change render output, compare scoring,
golden gates, private drawing handling, or AutoCAD equivalence claims.

## Problem

`tools/render_regression/ci_e2e_check.py` still described the render-to-compare
end-to-end check as something the D2 PR had deferred to D3.

That was stale: the script is now the shipped CI gate that consumes the
per-pass PNGs produced by `ci_render_golden.py` and verifies the golden corpus
is non-blank, dimension-correct, and deterministic on real Linux renders.

## Implementation

- Reworded the module docstring to call it the shipped render-to-compare CI
  gate for the golden corpus.
- Added `test_ci_e2e_check_doc.py` so the old "D2 deferred to D3" wording
  cannot drift back into this entrypoint.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_ci_e2e_check_doc.py -q
```

Result:

```text
1 passed in 0.00s
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
215 passed in 38.42s
```

## Closeout

The CI E2E entrypoint now matches current shipped behavior. This remains
evidence/operator hardening only; fresh matched-view AutoCAD references or an
explicit world window are still required before making AutoCAD-parity claims.
