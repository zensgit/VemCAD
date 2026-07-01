# Render request route gate-evidence command (2026-07-01)

## Why

The route CLI can now assert `viewspace_gate_evidence_counts`, but the generated
`reference_request.md` strict post-return command still only required
`viewspace_status_counts=match`. That left a usability gap: operators could run
the copied command and prove `match/pass` while not proving that the match came
from enforced X3 view-space gate evidence.

## Change

The generated route command now includes:

- `--require-viewspace-gate-evidence true=<selected-case-count>`
- `--forbid-viewspace-gate-evidence false`

The count follows the same dynamic selected-case count as `matched-pass`,
`match`, and `pass`, so full and partial AutoCAD reference returns stay aligned.

## Verification

- Focused:
  - `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py`
- Full render-regression suite:
  - `python3 -m pytest tools/render_regression/tests`

## Boundary

This is an operator-command hardening slice. It does not change renderer output,
X3 scoring, triage priority, or the requirement for a fresh matched-view AutoCAD
PNG / explicit world-window before any AutoCAD-equivalence claim.
