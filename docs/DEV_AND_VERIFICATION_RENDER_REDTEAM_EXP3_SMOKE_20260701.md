# Render Redteam Exp3 Smoke — Dev & Verification (2026-07-01)

## Boundary

This slice keeps an existing render-regression diagnostic script executable and
keeps its output shape current. It does not change render output, compare
scoring, gate semantics, AutoCAD reference intake, private drawing handling, or
AutoCAD equivalence claims.

## Problem

`redteam_exp3.py` exercises the full `regress.run(...)` path for a wrong-color
candidate against a black baseline, but it was not covered by the redteam script
smoke test. That made the script easier to drift as the report row shape
evolved.

Its module docstring also described the probe as proving an older gate weakness.
The current purpose is narrower: keep the diagnostic path runnable and explicit
about the fields it reports.

## Implementation

- `test_redteam_scripts.py`
  - includes `redteam_exp3.py` in the executable-script smoke;
  - checks script-specific output markers for exp1/exp2/exp3 instead of assuming
    every redteam script prints the same `iou=` line.
- `redteam_exp3.py`
  - updates the docstring to describe the script as a diagnostic probe, not a
    fidelity pass/fail gate.

## Verification

Focused:

```bash
python3 -m pytest tools/render_regression/tests/test_redteam_scripts.py -q
```

Result:

```text
1 passed
```

Full render regression suite:

```bash
python3 -m pytest tools/render_regression/tests -q
```

Result:

```text
219 passed in 39.63s
```

## Closeout

All three redteam diagnostic scripts are now smoke-tested. If their output shape
changes, the drift is caught in the normal render-regression test suite instead
of being discovered manually during an investigation.
