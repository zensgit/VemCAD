# Render route gate-evidence guards (2026-07-01)

## Why

Route summaries now expose `viewspace_gate_evidence_counts`, but unattended
flows still needed a way to assert the counts fail-closed from the command line.
Without a guard, scripts could assert `viewspace_status_counts=match=1` while
forgetting to assert that the match came from an enforced X3 view-space gate.

## Change

`acad_artifact_route.py` now supports:

- `--require-viewspace-gate-evidence true=N`
- `--require-viewspace-gate-evidence false=N`
- `--forbid-viewspace-gate-evidence true`
- `--forbid-viewspace-gate-evidence false`

The flags work for both compare artifact indexes and request-run route fields
via the existing routed-count fallback mechanism.

## Verification

- Focused:
  - `python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

This is an operator guard only. It does not change renderer behavior, X3 scoring,
or route priority. It only lets automation explicitly require that matched-view
status has gate evidence behind it.
