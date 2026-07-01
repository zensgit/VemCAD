# Render X3 view-space report gate mode (2026-07-01)

## Why

The previous slice made `compare_vs_acad.py` stdout label whether a run is
diagnostic-only or using `--require-viewspace-match`. That protects humans who
read terminal output.

The machine-readable `--viewspace-report` JSON still lacked the same distinction.
A downstream script could read `status=match` and an X3 summary without knowing
whether the run actually enforced the matched-view gate.

## Change

`compare_vs_acad.py --viewspace-report` now writes:

- `gate_mode`: `diagnostic-only` or `require-viewspace-match`
- `gate_evidence`: `true` only when `--require-viewspace-match` was enabled and
  the view-space status is `match`

This is additive. It does not change image scoring, view-space detection,
stdout verdicts, overlays, or exit codes.

## Verification

- Focused:
  - `python3 -m pytest tools/render_regression/tests/test_compare_vs_acad.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

`gate_evidence=true` means the X3 CLI enforced matched-view framing for that
pair. It still does not prove the AutoCAD PNG itself was freshly exported by
AutoCAD; that remains covered by the reference request/manifest intake contract.
