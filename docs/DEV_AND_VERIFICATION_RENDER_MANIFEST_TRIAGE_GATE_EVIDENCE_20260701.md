# Render manifest triage uses X3 gate evidence (2026-07-01)

## Why

`compare_vs_acad.py --viewspace-report` now records both `gate_mode` and
`gate_evidence`. The manifest comparison harness already invokes the comparator
with `--require-viewspace-match`, so current rows were safe in practice.

However, row triage still keyed only on `viewspace_status=match`. If an older or
diagnostic report shape ever reached the same row model, `status=match` could be
misread as renderer-gate evidence even when the matched-view gate was not
actually enforced.

## Change

- `acad_manifest_compare.py` now persists:
  - `viewspace_gate_mode`
  - `viewspace_gate_evidence`
- Triage buckets that can route to renderer work or pass review now require
  `viewspace_gate_evidence=true`, not just `viewspace_status=match`.
- A diagnostic-only `match` row falls back to `input-review`.

## Verification

- Focused:
  - `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

This is an evidence-chain hardening change only. It does not alter X3 scoring,
rendering, or the external requirement for a fresh matched-view AutoCAD
reference PNG.
