# Render route gate-evidence counts (2026-07-01)

## Why

The compare artifact index now exposes `viewspace_gate_evidence_counts`, but the
route layer still surfaced only `viewspace_status_counts`. A top-level route
report could show `match=1` without making it equally obvious whether the match
came from an enforced `--require-viewspace-match` run.

## Change

- Compare routes now carry `viewspace_gate_evidence_counts`.
- Request-run routes now propagate `route_viewspace_gate_evidence_counts`.
- Batch route aggregation now sums the gate-evidence counts.
- Text and Markdown route summaries print the new counts.

This is additive reporting only. Route priority, recommended actions, scoring,
and renderer behavior are unchanged.

## Verification

- Focused:
  - `python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

`viewspace_gate_evidence_counts=true=N` means the X3 matched-view gate was
enforced for N compare rows. It does not prove the AutoCAD PNG was produced by
AutoCAD; the reference request and manifest intake contract remain the source
of that provenance.
