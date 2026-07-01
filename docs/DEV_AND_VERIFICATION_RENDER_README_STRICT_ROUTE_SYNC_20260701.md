# Render README strict-route sync test (2026-07-01)

## Why

The generated `reference_request.md` strict post-return route command is the
operator copy/paste path. The README carries the same command as the runbook
example. After adding gate-evidence guards, both commands were manually aligned,
but there was no test proving they stay aligned.

## Change

`test_acad_manifest_compare.py` now generates a one-case reference request and
compares the generated strict route command flags with the README strict route
example flags. The executable line may differ (`<run-dir>` vs `<next-run-dir>`),
but every guard flag must match exactly and in order.

## Verification

- Focused:
  - `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

This is a regression-test hardening slice only. It does not change route logic,
renderer behavior, X3 scoring, or the requirement for a fresh matched-view
AutoCAD PNG / explicit world-window before any AutoCAD-equivalence claim.
