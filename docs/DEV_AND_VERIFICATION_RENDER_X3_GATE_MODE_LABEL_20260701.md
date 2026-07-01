# Render X3 gate-mode label (2026-07-01)

## Why

`compare_vs_acad.py` is useful both as a manual diagnostic and as a guarded X3
comparison entrypoint. Before this slice, stdout always printed the score band
and final verdict, but did not make the gate mode visible. A clean pair could
print `EXCELLENT` even when the operator had not enabled
`--require-viewspace-match`.

That was behaviorally correct but easy to overread. The numeric score is only
gate evidence when the matched-view check is also enforced.

## Change

- `compare_vs_acad.py` now prints:
  - `gate mode    : diagnostic-only (add --require-viewspace-match before gating)`
    by default.
  - `gate mode    : require-viewspace-match` when the gate flag is active.
- README X3 guidance now says the default CLI mode is diagnostic-only and only
  the explicit `--require-viewspace-match` mode should be used as gate evidence.

No score, band, overlay, JSON payload, or exit-code behavior changed.

## Verification

- Focused tests:
  - `python3 -m pytest tools/render_regression/tests/test_compare_vs_acad.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

This still does not prove AutoCAD equivalence by itself. It only makes the
operator-facing CLI output honest about whether the view-space gate is enabled.
