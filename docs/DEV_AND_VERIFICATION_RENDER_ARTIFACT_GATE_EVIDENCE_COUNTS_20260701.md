# Render artifact gate-evidence counts (2026-07-01)

## Why

`acad_manifest_compare.py` rows now carry `viewspace_gate_evidence`, and triage
uses it before routing a matched view-space row to renderer investigation or
pass review.

The top-level compare artifact index still exposed `viewspace_status_counts`
only. That made it easy to see `match=1`, but not whether the match was also
backed by the enforced X3 view-space gate.

## Change

The compare artifact index now includes:

- `viewspace_gate_evidence_counts`: lowercase `true` / `false` counts for rows
  that carry `viewspace_gate_evidence`

This is an additive reporting field. It does not change artifact routing,
triage, scoring, or renderer behavior.

## Verification

- Focused:
  - `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

This field proves only whether the X3 matched-view gate was enforced for the
compare row. It does not prove the AutoCAD PNG's origin; that remains the role
of the reference request and manifest intake contract.
