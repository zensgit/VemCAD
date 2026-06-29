# DEV/V — G11 Render-Fidelity Week (2026-06-28)

## Scope

This ledger tracks the one-week render-fidelity goal:

> Build a repeatable, evidence-backed G11/B11 AutoCAD comparison loop using
> matched view-space contracts, then only reopen renderer work if a matched
> comparison isolates a concrete defect.

## Boundary

- No GUI AutoCAD automation.
- No screenshot-derived equivalence claims.
- No global renderer tuning from aggregate X3 movement.
- No X3 threshold relaxation.
- No AutoCAD-equivalence claim while the view-space contract is `mismatch` or
  `unavailable`.

## Baseline

- VemCAD `origin/main` at plan creation: `295b040`.
- Text-layout diagnostic closeout:
  - G11 all text: no layout flags; note-only rotated bbox caveat.
  - G11 `HC_BTL_BLK`: no layout flags or notes.
- Hard remaining gate:
  - obtain a clean AutoCAD plot/export PNG or an explicit matching render
    window before interpreting X3 as fidelity.

## Slice Log

### Slice 0 — One-Week Plan

Status: merged in PR #167 (`73ad85f`).

Deliverables:

- `docs/VEMCAD_ONE_WEEK_RENDER_FIDELITY_PLAN_20260628.md`
- this DEV/V ledger

Verification:

- Docs-only scope.
- Markdown content reviewed against current boundary docs:
  - `VEMCAD_G11_VIEWSPACE_CONTRACT_20260628.md`
  - `VEMCAD_G11_TEXT_LAYOUT_DIAGNOSTICS_20260628.md`

### Slice 1 — AutoCAD Reference Manifest Gate

Status: merged in PR #168 (`5436247`).

Deliverables:

- `tools/render_regression/acad_reference_manifest.py`
- `tools/render_regression/tests/test_acad_reference_manifest.py`

Behavior:

- Accepts only gate-grade AutoCAD references (`plot-export`, `exportpng`,
  `publish`, `plot-raster`) with a matched-view contract (`model-extents` or
  `explicit-window`).
- Fails closed for screenshot/viewport captures, missing files, invalid schema,
  missing `drawing_id`, invalid/mismatched expected image size, or unmatched
  view contract.
- Emits a validation report plus a gate-trusted case stub for the Day 2 harness.

Verification:

- `python3 -m pytest tools/render_regression/tests/test_acad_reference_manifest.py -q`
  - `8 passed`
- `python3 -m pytest tools/render_regression/tests/test_compare_vs_acad.py tools/render_regression/tests/test_autocad_batch_compare.py -q`
  - `20 passed`
- `python3 -m pytest tools/render_regression/tests -q`
  - `75 passed`

Boundary:

- No private drawing or AutoCAD image committed.
- No rendering, no comparison, no equivalence claim.
- This slice only decides whether supplied AutoCAD references are eligible for
  the matched-view X3 path.

### Slice 2 — Manifest-Driven Matched-View Harness

Status: merged in PR #169 (`989ec77`).

Deliverables:

- `tools/render_regression/acad_manifest_compare.py`
- `tools/render_regression/tests/test_acad_manifest_compare.py`

Behavior:

- Joins a validated AutoCAD reference manifest with already-rendered VemCAD
  candidate PNG artifacts.
- Calls the existing `compare_vs_acad.py --viewspace-report
  --require-viewspace-match` path for each case.
- Writes `summary.json`, `summary.tsv`, per-case view-space reports, and
  overlays when the underlying diff engine considers the pair comparable.
- Carries candidate provenance fields such as render report path, semantic mask
  path, render image digest, and diagnostic metadata.
- Returns non-zero for blocked manifests, missing candidate artifacts, or
  `viewspace_mismatch`.

Verification:

- `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q`
  - `4 passed`
- `python3 -m pytest tools/render_regression/tests/test_acad_reference_manifest.py tools/render_regression/tests/test_compare_vs_acad.py tools/render_regression/tests/test_autocad_batch_compare.py -q`
  - `28 passed`
- `python3 -m pytest tools/render_regression/tests -q`
  - `79 passed`

Boundary:

- No DXF rendering; candidate PNGs are inputs.
- No private drawing or AutoCAD image committed.
- No AutoCAD-equivalence claim; even matched view-space only means X3 is
  eligible to be interpreted.

### Slice 3 — Triage Summary and Artifact Index

Status: merged in PR #170 (`f2afea3`).

Deliverables:

- Extend `tools/render_regression/acad_manifest_compare.py`.
- Extend `tools/render_regression/tests/test_acad_manifest_compare.py`.

Behavior:

- Adds `text_flags` and `text_notes` columns to the harness TSV.
- If a candidate case includes `render_report`, reuses
  `text_provenance_diagnostics.analyze_report()` to surface text-placement
  flag/note counts in the per-case JSON row.
- Writes `artifact_index.json`, listing stable artifact paths for AutoCAD
  reference PNGs, VemCAD candidate PNGs, overlays, view-space reports, render
  reports, semantic masks/reports, and text-provenance summaries.

Verification:

- `python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q`
  - `5 passed`
- `python3 -m pytest tools/render_regression/tests -q`
  - `80 passed`

Boundary:

- Diagnostic enrichment only; no renderer change.
- Text provenance is not a gate; unreadable text diagnostics are recorded as
  diagnostic errors without turning the X3 view-space gate into a text gate.

### Slice 4 — First Real G11 Run

Status: merged in PR #171 (`1c88801`).

Inputs:

- AutoCAD reference PNG:
  `/tmp/vemcadautocadplot/batch/png/G11-1.png`
  - `2339x1653`, RGB, from the prior local AutoCAD plot/export batch.
- Source DXF:
  `/tmp/vacadbatchinputs/B11.dxf`
- VemCAD render image:
  `ghcr.io/zensgit/vemcad-render:main`

Commands:

```bash
OUT=/tmp/vemcad-fidelity-out/g11_week_real_20260628T133732Z

docker run --rm \
  -v /tmp/vacadbatchinputs:/in:ro \
  -v "$OUT":/out \
  --entrypoint render_cli ghcr.io/zensgit/vemcad-render:main \
  --input /in/B11.dxf \
  --out /out/G11_ours.png \
  --bg white \
  --width 2339 --height 1653 \
  --report /out/G11_report.json \
  --class-mask-out /out/G11_semantic_mask.png

python3 tools/render_regression/acad_manifest_compare.py \
  --manifest "$OUT/acad_manifest.json" \
  --candidate-cases "$OUT/candidate_cases.json" \
  --out-dir "$OUT/compare"
```

Harness result:

- Exit code: `2`
- Status: `viewspace_mismatch`
- View-space reason: `page-fill/aspect divergence exceeds tolerance`
- Recommended action: recapture AutoCAD at model EXTENTS with matching aspect,
  or render the candidate with an explicit matching `--window` before
  interpreting X3.

X3 summary (recorded but **not** treated as fidelity because view-space is
`mismatch`):

- `ink_iou`: `0.8021`
- `ssim`: `0.4959`
- `color_dist`: `134.1`
- `aspect_delta`: `0.0035`
- `band`: `fallback`

Text provenance from `G11_report.json`:

- `text_placement_schema`: `vemcad.render_text_placement`
- `text_placement_schema_version`: `0.4`
- `all_text_records`: `39`
- `flag_counts`: `{}`
- `note_counts`: `{"rotated_bbox_is_approximate": 7}`

Semantic diagnostic rows (candidate-side semantics, AutoCAD semantics unknown):

| Class | Candidate precision | Reference coverage | Candidate pixels | Band |
| --- | ---: | ---: | ---: | --- |
| geometry | 0.9360 | 0.6094 | 25269 | review |
| text | 0.0000 | 0.0000 | 332 | fallback |
| dimension | 0.5035 | 0.1205 | 11816 | fallback |
| hatch | 1.0000 | 0.0229 | 662 | pass |
| insert_text | 0.6093 | 0.0849 | 5941 | fallback |
| other | 1.0000 | 0.0013 | 11 | pass |

Artifacts (local only, not committed):

- `$OUT/G11_ours.png`
- `$OUT/G11_report.json`
- `$OUT/G11_semantic_mask.png`
- `$OUT/compare/summary.json`
- `$OUT/compare/summary.tsv`
- `$OUT/compare/artifact_index.json`
- `$OUT/compare/overlays/G11_overlay.png`
- `$OUT/compare/viewspace/G11_viewspace.json`
- `$OUT/compare/semantic/G11_semantic_classes.json`
- `$OUT/compare/text/G11_text_provenance.json`

Conclusion:

- This is a valid real G11 run, but it is **not** an AutoCAD-equivalence result.
- The hard blocker is now precise: the available AutoCAD reference and the
  VemCAD render are still not in a matched view-space.
- Renderer work should stay closed until either:
  - AutoCAD is recaptured at model EXTENTS with matching aspect; or
  - an explicit world `--window` matching the AutoCAD plot is supplied.

### Post-Closeout Slice — AutoCAD Reference Input Kit

Status: in progress in this PR.

Deliverables:

- `tools/render_regression/acad_reference_case.py`
- `tools/render_regression/tests/test_acad_reference_case.py`
- `docs/VEMCAD_G11_AUTOCAD_REFERENCE_INPUT_RUNBOOK_20260628.md`

Behavior:

- Creates `acad_manifest.json` and `candidate_cases.json` from explicit paths.
- Reads the AutoCAD PNG dimensions and writes them into `expected_size`.
- Reuses the existing AutoCAD manifest validator immediately after writing the
  files.
- Leaves rendering and comparison to the existing `render_cli` and
  `acad_manifest_compare.py` paths.

Verification:

- `python3 -m pytest tools/render_regression/tests/test_acad_reference_case.py -q`
  - `2 passed`
- `python3 -m pytest tools/render_regression/tests/test_acad_reference_case.py tools/render_regression/tests/test_acad_reference_manifest.py tools/render_regression/tests/test_acad_manifest_compare.py -q`
  - `15 passed`
- `python3 -m pytest tools/render_regression/tests -q`
  - `82 passed`

Boundary:

- No AutoCAD image or drawing committed.
- No renderer changes.
- The helper does not claim equivalence; it only removes hand-written JSON from
  the next reference-input handoff.

## Verification Matrix

| Slice | Local tests | CI | Runtime / artifact proof | Result |
| --- | --- | --- | --- | --- |
| Slice 0 plan | docs-only | docs-only PR #167, no checks | n/a | merged |
| Slice 1 AutoCAD reference manifest | `test_acad_reference_manifest.py`; adjacent compare tests; full `tools/render_regression/tests` | PR #168: `pytest`, `build-and-smoke` | synthetic PNG/DXF fixtures only | merged |
| Slice 2 manifest compare harness | `test_acad_manifest_compare.py`; adjacent manifest/compare tests; full `tools/render_regression/tests` | PR #169: `pytest`, `build-and-smoke` | synthetic PNG pairs only; no renderer | merged |
| Slice 3 triage summary / artifact index | `test_acad_manifest_compare.py`; full `tools/render_regression/tests` | PR #170: `pytest`, `build-and-smoke` | synthetic PNG + synthetic render report only; no renderer | merged |
| Slice 4 first real G11 run | docs-only evidence | pending | local Docker render + manifest harness; artifacts under `/tmp/vemcad-fidelity-out/g11_week_real_20260628T133732Z` | viewspace_mismatch |
| Post-closeout AutoCAD input kit | `test_acad_reference_case.py`; manifest/harness tests; full `tools/render_regression/tests` | pending | synthetic PNG/DXF only; no renderer | local green |

## Evidence To Fill During The Week

For each future slice, append:

- branch / PR / merge SHA;
- exact commands;
- local test output;
- CI check names and result;
- render image digest or workflow run, if relevant;
- AutoCAD input provenance, if used;
- comparison verdict and why it is or is not an equivalence claim.

## Final Closeout

Final VemCAD `origin/main`:

- `1c88801ac47ab76b62c6c147f51382f9267e770e`

Final CADGameFusion gitlink:

- `deps/cadgamefusion` -> `5871fced88507c87f6ac03578c45a4072e51ee42`

Merged slices:

| Slice | PR | Merge | Result |
| --- | --- | --- | --- |
| Slice 0 — one-week plan | #167 | `73ad85f` | plan + DEV/V ledger |
| Slice 1 — AutoCAD reference manifest gate | #168 | `5436247` | fail-closed reference validator |
| Slice 2 — manifest-driven matched-view harness | #169 | `989ec77` | manifest + candidate PNG -> X3 view-space gate |
| Slice 3 — triage summary / artifact index | #170 | `f2afea3` | text flags/notes + artifact index |
| Slice 4 — first real G11 run evidence | #171 | `1c88801` | real run recorded; view-space mismatch |

Render image / workflow evidence:

- Local Docker render used `ghcr.io/zensgit/vemcad-render:main`.
- PR CI evidence:
  - #168: `pytest`, `build-and-smoke`
  - #169: `pytest`, `build-and-smoke`
  - #170: `pytest`, `build-and-smoke`
  - #171: docs-only, no checks reported
- Local real-run artifact root:
  `/tmp/vemcad-fidelity-out/g11_week_real_20260628T133732Z`

AutoCAD reference:

- `/tmp/vemcadautocadplot/batch/png/G11-1.png`
- `2339x1653`, RGB, prior local AutoCAD plot/export batch.

View-space status:

- `viewspace_mismatch`
- Reason: `page-fill/aspect divergence exceeds tolerance`
- Recommended action from the harness: recapture AutoCAD at model EXTENTS with
  matching aspect, or render the candidate with an explicit matching `--window`
  before interpreting X3.

X3 result:

- Recorded but not interpretable as renderer fidelity while view-space is
  mismatched.
- `ink_iou`: `0.8021`
- `ssim`: `0.4959`
- `color_dist`: `134.1`
- `aspect_delta`: `0.0035`
- `band`: `fallback`

Semantic/text diagnostics:

- Text provenance:
  - `text_placement_schema`: `vemcad.render_text_placement`
  - `text_placement_schema_version`: `0.4`
  - `all_text_records`: `39`
  - `flag_counts`: `{}`
  - `note_counts`: `{"rotated_bbox_is_approximate": 7}`
- Candidate-side semantic diagnostics were produced, but AutoCAD semantics are
  unknown and the view-space mismatch makes class scores diagnostic only.

Conclusion:

- The week's development goal is complete: the comparison loop now has a
  versioned input gate, a manifest-driven view-space harness, triage summaries,
  artifact indexing, and a recorded real G11 run.
- G11 is **not** closed as AutoCAD-equivalent.
- The next blocker is no longer tooling. It is input/view contract:
  the available AutoCAD plot/export is not matched to the VemCAD render
  view-space.

Next action:

- Get a clean AutoCAD export at model EXTENTS with matching aspect, or provide
  the explicit world `--window` for the AutoCAD plot.
- Post-closeout follow-up `VEMCAD_G11_MATCHED_WINDOW_DERIVATION_20260628.md`
  attempted to derive that window from the existing PNG/report pair. It did not
  find a trustworthy world window; the input/view contract remains the blocker.
- Use `VEMCAD_G11_AUTOCAD_REFERENCE_INPUT_RUNBOOK_20260628.md` and
  `tools/render_regression/acad_reference_case.py` to create the manifest and
  candidate files for the next AutoCAD reference, rather than hand-writing JSON.
- Then rerun:
  `tools/render_regression/acad_manifest_compare.py --manifest ... --candidate-cases ... --out-dir ...`
- Only if that rerun reports `viewspace_status=match` should X3 and semantic
  rows be used to open renderer work.
