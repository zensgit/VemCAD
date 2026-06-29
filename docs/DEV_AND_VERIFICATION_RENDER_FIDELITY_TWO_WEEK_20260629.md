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

Status: merged in PR #179 (`a0ba846`).

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

Status: merged in PR #180 (`ea535dc`).

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

### Slice 3 — Existing AutoCAD Batch Evidence Re-Run

Status: local/private evidence run complete; ledger update in this branch.

Inputs:

- Manifest:
  `/private/tmp/vemcad-autocad-batch-current/input/acad_manifest.json`
- Candidate cases:
  `/private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json`
- Harness source:
  VemCAD `origin/main=ea535dc`

Command:

```bash
python3 tools/render_regression/acad_manifest_compare.py \
  --manifest /private/tmp/vemcad-autocad-batch-current/input/acad_manifest.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --out-dir /private/tmp/vemcad-autocad-batch-current-rerun-20260629/compare
# AutoCAD manifest compare: viewspace_mismatch (12/12 compared, 0 issues)
# exit code: 2
```

Outputs:

- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629/compare/summary.json`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629/compare/summary.md`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629/compare/summary.tsv`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629/compare/artifact_index.json`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629/compare/contact_sheet.png`
- per-case overlays and view-space reports under the same directory

Result:

- status: `viewspace_mismatch`
- compared: `12/12`
- issues: `0`
- artifact index entries: `52`
- all 12 rows report `page-fill/aspect divergence exceeds tolerance`

Triage table, sorted by lowest Ink IoU first:

| Case | View-space | X3 band | Ink IoU | Color dist | Interpretation |
| --- | --- | --- | ---: | ---: | --- |
| G11 | mismatch | fallback | 0.3393 | 130.2 | Worst diagnostic case; needs fresh matched AutoCAD export before renderer work. |
| G04 | mismatch | fallback | 0.6323 | 90.1 | Diagnostic-only; likely useful after matched recapture because content is dense. |
| G10 | mismatch | fallback | 0.7706 | 88.8 | Recapture before interpreting. |
| G08 | mismatch | fallback | 0.7738 | 131.5 | Recapture before interpreting. |
| G02 | mismatch | fallback | 0.7915 | 126.3 | Recapture before interpreting. |
| G05 | mismatch | fallback | 0.8178 | 164.8 | Recapture before interpreting. |
| G01 | mismatch | fallback | 0.8212 | 125.7 | Recapture before interpreting. |
| G12 | mismatch | fallback | 0.8332 | 111.6 | Recapture before interpreting. |
| G09 | mismatch | fallback | 0.8349 | 121.0 | Recapture before interpreting. |
| G07 | mismatch | fallback | 0.8631 | 124.2 | Recapture before interpreting. |
| G06 | mismatch | fallback | 0.8775 | 94.3 | Recapture before interpreting. |
| G03 | mismatch | fallback | 0.8946 | 91.1 | Best diagnostic case, still not an equivalence result. |

Conclusion:

- The existing AutoCAD batch is usable as a private review and prioritization
  artifact, especially via `contact_sheet.png`.
- It is not usable as an AutoCAD-equivalence gate because every row fails the
  view-space contract.
- No renderer work should be opened from this batch alone.
- The next valid external input remains a fresh AutoCAD model-extents export or
  explicit AutoCAD world plot/window rectangle for at least one drawing.

Boundary:

- Local/private evidence run only.
- No private drawing, AutoCAD PNG, overlay, or contact sheet committed.
- No renderer change.

### Slice 4 — Markdown Triage Priority Table

Status: merged in PR #182 (`b5c0428`).

Deliverables:

- `tools/render_regression/acad_manifest_compare.py`
- `tools/render_regression/tests/test_acad_manifest_compare.py`

Behavior:

- `summary.md` now includes a `Triage Priority` section.
- Rows are bucketed and sorted so unattended batch output points to the right
  next action:
  - `renderer-candidate`: matched view-space but non-pass X3 band; only this
    bucket can justify renderer investigation.
  - `recapture-required`: view-space mismatch; requires a fresh AutoCAD export
    or explicit world window before interpreting fidelity.
  - `input-review`: unavailable or unusual view-space status.
  - `matched-pass`: lowest priority; no renderer work.
- Within a bucket, lower Ink IoU sorts first.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 85 passed
```

Boundary:

- Evidence/reporting only.
- No scoring threshold change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.

## Current Closeout (2026-06-29)

Landed in this goal so far:

| Slice | PR | Result |
| --- | --- | --- |
| 0-1 | #179 (`a0ba846`) | Two-week plan + DEV/V ledger + `summary.md` evidence report. |
| 2 | #180 (`ea535dc`) | Complete `artifact_index.json` for all harness runs, including blocked/dry-run cases. |
| 3 | #181 (`38182cb`) | Private 12-case AutoCAD batch rerun recorded; all rows remain view-space mismatch. |
| 4 | #182 (`b5c0428`) | Markdown triage priority table added to unattended comparison reports. |

Latest known VemCAD main after these slices: `b5c0428`.

Autonomous engineering status:

- The comparison harness now leaves a self-contained evidence bundle:
  `summary.json`, `summary.md`, optional `summary.tsv`, `artifact_index.json`,
  `contact_sheet.png`, overlays, and per-case view-space reports.
- The report now tells a reviewer which cases are `renderer-candidate` versus
  `recapture-required`, so mismatched AutoCAD captures do not accidentally
  become renderer work.
- The existing local AutoCAD batch has been rerun with the new tooling:
  `12/12` compared, `0` input issues, all `viewspace_mismatch`.

Remaining gate:

- A formal AutoCAD parity claim still requires at least one fresh AutoCAD
  model-extents export PNG or an explicit AutoCAD world plot/window rectangle.
- Until that input exists, the next valid state is `blocked_on_reference_input`;
  renderer tuning remains out of scope.

### Slice 5 — Machine-Readable Triage Fields

Status: merged in PR #184 (`6737448`).

Deliverables:

- `tools/render_regression/acad_manifest_compare.py`
- `tools/render_regression/tests/test_acad_manifest_compare.py`

Behavior:

- Each comparison row in `summary.json` now carries:
  - `triage_rank`
  - `triage_bucket`
- `summary.tsv` includes the same two fields so downstream scripts can consume
  the triage ordering without parsing Markdown.
- The Markdown `Triage Priority` section now displays the persisted rank/bucket
  values.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 85 passed
```

Boundary:

- Evidence/reporting only.
- No scoring threshold change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.

### Slice 6 — Machine Triage Batch Re-Run

Status: local/private evidence run complete; ledger update in this branch.

Inputs:

- Manifest:
  `/private/tmp/vemcad-autocad-batch-current/input/acad_manifest.json`
- Candidate cases:
  `/private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json`
- Harness source:
  VemCAD `origin/main=6737448`

Command:

```bash
python3 tools/render_regression/acad_manifest_compare.py \
  --manifest /private/tmp/vemcad-autocad-batch-current/input/acad_manifest.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --out-dir /private/tmp/vemcad-autocad-batch-current-rerun-20260629-machine/compare
# AutoCAD manifest compare: viewspace_mismatch (12/12 compared, 0 issues)
# exit code: 2
```

Result:

- status: `viewspace_mismatch`
- compared: `12/12`
- issues: `0`
- `summary.json` rows now include `triage_rank` and `triage_bucket`
- `summary.tsv` now includes `triage_rank` and `triage_bucket`
- all 12 rows are `recapture-required`

Machine-readable triage order:

| Rank | Case | Bucket | View-space | X3 band | Ink IoU | Color dist |
| ---: | --- | --- | --- | --- | ---: | ---: |
| 1 | G11 | recapture-required | mismatch | fallback | 0.3393 | 130.2 |
| 2 | G04 | recapture-required | mismatch | fallback | 0.6323 | 90.1 |
| 3 | G10 | recapture-required | mismatch | fallback | 0.7706 | 88.8 |
| 4 | G08 | recapture-required | mismatch | fallback | 0.7738 | 131.5 |
| 5 | G02 | recapture-required | mismatch | fallback | 0.7915 | 126.3 |
| 6 | G05 | recapture-required | mismatch | fallback | 0.8178 | 164.8 |
| 7 | G01 | recapture-required | mismatch | fallback | 0.8212 | 125.7 |
| 8 | G12 | recapture-required | mismatch | fallback | 0.8332 | 111.6 |
| 9 | G09 | recapture-required | mismatch | fallback | 0.8349 | 121.0 |
| 10 | G07 | recapture-required | mismatch | fallback | 0.8631 | 124.2 |
| 11 | G06 | recapture-required | mismatch | fallback | 0.8775 | 94.3 |
| 12 | G03 | recapture-required | mismatch | fallback | 0.8946 | 91.1 |

Artifacts:

- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629-machine/compare/summary.json`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629-machine/compare/summary.tsv`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629-machine/compare/summary.md`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629-machine/compare/contact_sheet.png`

Conclusion:

- The triage fields work and are available to downstream automation.
- The current batch still cannot justify renderer tuning: every row remains a
  view-space mismatch and therefore `recapture-required`.
- The highest-priority fresh AutoCAD recaptures remain G11 first, then G04.

Boundary:

- Local/private evidence run only.
- No private drawing, AutoCAD PNG, overlay, or contact sheet committed.
- No renderer change.

### Slice 7 — AutoCAD Recapture Request Artifacts

Status: merged in PR #186 (`4cdfeb2`).

Deliverables:

- `tools/render_regression/acad_manifest_compare.py`
- `tools/render_regression/tests/test_acad_manifest_compare.py`

Behavior:

- When a comparison run contains `recapture-required` rows, the harness writes:
  - `reference_request.json`
  - `reference_request.md`
- The request lists each case in triage order, with source DXF path, current
  AutoCAD reference path, requested capture method, requested view contract,
  recommended output filename, and capture instructions.
- The request artifacts are included in `artifact_index.json`.
- Matched/pass-only runs do not create a recapture request.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 85 passed
```

Boundary:

- Evidence/request generation only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.

### Slice 8 — AutoCAD Recapture Request Batch Re-Run

Status: local/private evidence run complete; ledger update in this branch.

Inputs:

- Manifest:
  `/private/tmp/vemcad-autocad-batch-current/input/acad_manifest.json`
- Candidate cases:
  `/private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json`
- Harness source:
  VemCAD `origin/main=4cdfeb2`

Command:

```bash
python3 tools/render_regression/acad_manifest_compare.py \
  --manifest /private/tmp/vemcad-autocad-batch-current/input/acad_manifest.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --out-dir /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare
# AutoCAD manifest compare: viewspace_mismatch (12/12 compared, 0 issues)
# exit code: 2
```

Result:

- `reference_request.json` schema:
  `vemcad.acad_reference_request/v1`
- reason: `recapture-required`
- case count: `12`
- artifact index entries: `54`
- artifact index includes `reference_request_json` and
  `reference_request_markdown`

Request artifact paths:

- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json`
- `/private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.md`

Top recapture requests:

| Rank | Case | Requested PNG | Source DXF |
| ---: | --- | --- | --- |
| 1 | G11 | `G11_autocad_model_extents.png` | `/private/tmp/vacadbatchinputs/B11.dxf` |
| 2 | G04 | `G04_autocad_model_extents.png` | `/private/tmp/vacadbatchinputs/B04.dxf` |
| 3 | G10 | `G10_autocad_model_extents.png` | `/private/tmp/vacadbatchinputs/B10.dxf` |

Conclusion:

- The harness now produces a direct handoff packet for the human/AutoCAD side.
- The formal parity path remains blocked until at least one requested PNG is
  produced or an explicit AutoCAD world window is supplied.

Boundary:

- Local/private evidence run only.
- No private drawing, AutoCAD PNG, overlay, or contact sheet committed.
- No renderer change.
