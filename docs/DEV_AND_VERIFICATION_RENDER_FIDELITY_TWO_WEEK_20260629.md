# DEV/V — Render-Fidelity Two-Week Goal (2026-06-29)

## Scope

This ledger tracks the two-week VemCAD render-fidelity goal:

> Build and execute a repeatable AutoCAD comparison evidence loop, then only
> open renderer work from matched-view, defect-specific evidence.

## Boundary

- No GUI AutoCAD automation.
- No screenshot-derived equivalence claims.
- No X3 threshold relaxation.
- No public commit of private drawings or AutoCAD reference images.
- No CADGameFusion change unless a matched-view comparison isolates a concrete
  renderer defect.

## Baseline

- VemCAD `origin/main` at goal creation: `34211bf`.
- CADGameFusion gitlink at goal creation: `5871fce`.
- Open VemCAD PRs at goal creation: pre-existing `#1` WIP only.
- Previous one-week plan closed with the comparison machinery in place, but
  with known view-space mismatches in the available AutoCAD batch.

## Slice Log

### Slice 0 — Two-Week Plan And Ledger

Status: in progress in this branch.

Deliverables:

- `docs/VEMCAD_TWO_WEEK_RENDER_FIDELITY_PLAN_20260629.md`
- this DEV/V ledger

Verification:

- Docs are based on current `origin/main=34211bf`.
- Current CADGameFusion gitlink verified as `5871fce`.
- Current open VemCAD PR list verified as only pre-existing `#1` WIP.

Boundary:

- Docs-only.
- No renderer changes.
- No private artifacts committed.

### Slice 1 — Markdown Evidence Report

Status: merged in PR #179 (`a0ba846`).

Deliverables:

- `tools/render_regression/acad_manifest_compare.py`
- `tools/render_regression/tests/test_acad_manifest_compare.py`

Behavior:

- Every `acad_manifest_compare.py` run now writes a human-readable
  `summary.md` beside `summary.json`.
- For comparison runs, the report includes:
  - overall status, case counts, issue counts, and dry-run state;
  - boundary flags, including `autocad_equivalence_claim=False`;
  - the explicit warning that `viewspace_mismatch` is not an AutoCAD-equivalence
    result and must not trigger renderer tuning by itself;
  - contact-sheet path when available;
  - per-case view-space status, X3 band, ink IoU, color distance, text
    flags/notes, recommended action, and artifact paths.
- For blocked or dry-run cases, the report still writes issues and boundary
  statements so an unattended run leaves a readable artifact.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 5 passed

python3 -m pytest tools/render_regression/tests -q
# 84 passed
```

Boundary:

- Evidence/reporting only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- JSON/TSV remain the authoritative machine-readable outputs; `summary.md` is
  the human-review layer.

### Slice 2 — Complete Evidence Bundle Index

Status: in progress in this branch.

Deliverables:

- `tools/render_regression/acad_manifest_compare.py`
- `tools/render_regression/tests/test_acad_manifest_compare.py`

Behavior:

- `artifact_index.json` is now written for every harness run, including blocked
  manifests and dry runs.
- The index includes run-level entry artifacts:
  - `summary_json`
  - `summary_markdown`
  - `summary_tsv` when a comparison table exists
  - `contact_sheet` when comparison rows exist
- Per-case artifacts remain listed as before: AutoCAD reference, VemCAD
  candidate, overlay, view-space report, render report, semantic mask/report,
  and text provenance summary.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 5 passed

python3 -m pytest tools/render_regression/tests -q
# 84 passed
```

Boundary:

- Evidence/reporting only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
