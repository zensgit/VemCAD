# VemCAD G11 AutoCAD Reference Input Runbook (2026-06-28)

## Purpose

This runbook is the executable handoff for the current G11 render-fidelity
blocker.

The renderer comparison tooling is ready, but the current AutoCAD reference PNG
is not in the same view-space as the VemCAD render. The next valid step is not
renderer tuning. It is to provide a trustworthy AutoCAD reference input and run
the matched-view harness.

## Required Inputs

For each comparison case, provide:

| Input | Requirement |
| --- | --- |
| `source_dxf` | The DXF that VemCAD renders. |
| `acad_png` | AutoCAD-generated PNG for the same drawing. |
| `ours` | VemCAD/render_cli PNG for the same drawing. |
| `capture_method` | One of `plot-export`, `exportpng`, `publish`, `plot-raster`. |
| `view_contract` | `model-extents` or `explicit-window`. |

Do not use:

- viewport screenshots;
- window screenshots;
- thumbnails;
- images with toolbars/chrome;
- images post-scaled by Preview/Photoshop/etc.;
- reference-envelope or hand-shrunk VemCAD renders as gate evidence.

## AutoCAD Export Contract

Preferred contract: `model-extents`.

Export from AutoCAD with:

- model space, not a layout viewport screenshot;
- white background;
- monochrome off, so color information is preserved;
- extents / fit-to-drawing view;
- same aspect ratio as the VemCAD render;
- long edge at least `1600px`;
- preferably `2339x1653` for the existing G11/B11 flow, to keep the current
  evidence comparable.

If AutoCAD must use a custom plot window, record the actual world rectangle and
use `view_contract=explicit-window`. The world rectangle, not the screenshot
crop, is the contract.

## Create Manifest And Candidate Files

For a single case, use the helper so JSON is generated consistently:

```bash
CASE_DIR=/tmp/vemcad-g11-case-$(date -u +%Y%m%dT%H%M%SZ)

python3 tools/render_regression/acad_reference_case.py \
  --case-id G11 \
  --drawing-id G11/B11 \
  --source-dxf /tmp/vacadbatchinputs/B11.dxf \
  --acad-png /path/to/autocad_model_extents.png \
  --ours /path/to/G11_ours.png \
  --render-report /path/to/G11_report.json \
  --semantic-mask /path/to/G11_semantic_mask.png \
  --semantic-report /path/to/G11_report.json \
  --render-image ghcr.io/zensgit/vemcad-render:main \
  --diagnostic window_source=model-extents \
  --out-dir "$CASE_DIR"
```

The helper writes:

- `$CASE_DIR/acad_manifest.json`
- `$CASE_DIR/candidate_cases.json`

It also validates the AutoCAD PNG and records the actual PNG size as
`expected_size`. If the PNG is unreadable, missing, or not gate-grade, it returns
non-zero.

For an unattended or multi-drawing run, write a cases JSON list and use the batch
helper:

```json
[
  {
    "id": "G11",
    "drawing_id": "G11/B11",
    "source_dxf": "/tmp/vacadbatchinputs/B11.dxf",
    "acad_png": "/path/to/autocad_model_extents_G11.png",
    "ours": "/path/to/G11_ours.png",
    "render_report": "/path/to/G11_report.json",
    "semantic_mask": "/path/to/G11_semantic_mask.png",
    "semantic_report": "/path/to/G11_report.json",
    "render_image": "ghcr.io/zensgit/vemcad-render:main",
    "diagnostics": {
      "window_source": "model-extents"
    }
  }
]
```

```bash
BATCH_DIR=/tmp/vemcad-autocad-batch-$(date -u +%Y%m%dT%H%M%SZ)

python3 tools/render_regression/acad_reference_batch.py \
  --cases /path/to/cases.json \
  --out-dir "$BATCH_DIR"
```

The batch helper writes the same two harness inputs:

- `$BATCH_DIR/acad_manifest.json`
- `$BATCH_DIR/candidate_cases.json`
- `$BATCH_DIR/artifact_index.json`

Relative paths inside `cases.json` resolve relative to the JSON file. Each
AutoCAD PNG is opened to record `expected_size`; unreadable images or missing
required fields fail closed before the comparison step.

## Fulfill A Recapture Request

When `acad_manifest_compare.py` produces `reference_request.json`, place the
fresh AutoCAD PNGs in one directory using the requested filenames, then generate
the next manifest/candidate files from the request:

```bash
REQUEST_DIR=/private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare
RETURNED_DIR=/path/to/fresh-autocad-model-extents-pngs
NEXT_DIR=/tmp/vemcad-autocad-batch-fulfilled-$(date -u +%Y%m%dT%H%M%SZ)

python3 tools/render_regression/acad_reference_batch.py \
  --from-request "$REQUEST_DIR/reference_request.json" \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir "$RETURNED_DIR" \
  --out-dir "$NEXT_DIR/input"
```

The helper resolves the original candidate artifacts, opens every returned PNG
to record `expected_size`, and fails closed if any requested PNG is missing or
unreadable. It first writes and enforces a request-package validation report,
then writes a returned-reference preflight beside the generated inputs:

- `$NEXT_DIR/input/reference_request_validation.json`
- `$NEXT_DIR/input/reference_request_validation.md`
- `$NEXT_DIR/input/reference_intake.json`
- `$NEXT_DIR/input/reference_intake.md`
- `$NEXT_DIR/input/artifact_index.json`

All generated helper artifacts, including missing-reference reports on blocked
runs, are listed in `artifact_index.json` so unattended runs have one stable
entry point for review.

The batch-level `artifact_index.json` also carries `stage`, `status`,
`case_count`, `error_count`, `warning_count`, and any available
validation/intake/missing-reference status fields. This lets CI or an operator
route blocked/review input-prep runs before opening individual artifact files.

The intake preflight checks obvious capture-quality signals before X3:

- long edge is at least `1600px`;
- PNG has no alpha/transparency channel;
- sampled corners are near white, catching dark-background exports and many
  toolbar/chrome/crop accidents.

`reference_intake` is a review aid only. A `pass` result does not compare
against VemCAD and does not claim AutoCAD equivalence. A `review` result means
the PNG exists and the workflow can continue, but the operator should inspect
the warning before trusting any visual conclusion.

The intake also records `inspection.identity_advisory`, a diagnostic-only
comparison between the returned AutoCAD PNG ink bbox and the candidate VemCAD
PNG ink bbox. A large aspect divergence warns about possible wrong-drawing or
wrong-window input. It is not a semantic mask, not a pass/fail gate, and not
evidence of AutoCAD equivalence.

Then run the matched-view harness with:

To process only the first returned case, repeat `--case-id`:

```bash
python3 tools/render_regression/acad_reference_batch.py \
  --from-request "$REQUEST_DIR/reference_request.json" \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir "$RETURNED_DIR" \
  --case-id G11 \
  --out-dir "$NEXT_DIR/input"
```

Without `--case-id`, all requested PNGs must be present.

For the common case, use the wrapper to fulfill the returned PNGs and run the
matched-view comparison in one command:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request "$REQUEST_DIR/reference_request.json" \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir "$RETURNED_DIR" \
  --case-id G11 \
  --out-dir "$NEXT_DIR"
```

The wrapper writes:

- `$NEXT_DIR/input/` — generated manifest/candidates plus intake/index files;
- `$NEXT_DIR/compare/` — X3 compare outputs;
- `$NEXT_DIR/run_summary.json`;
- `$NEXT_DIR/run_summary.md`.
- `$NEXT_DIR/artifact_index.json` — run-level index for the summary, input
  artifacts, and compare artifacts that were actually produced.

It returns the comparison exit code, so `viewspace_mismatch` still exits `2`.
The wrapper is only an orchestration convenience; it does not render DXFs and
does not replace the X3 gate.

The wrapper summary also surfaces
`reference_request_validation_status/error_count/warning_count`, so a blocked
request package is visible from the run root without opening the input
directory first.

The wrapper also writes `recommended_next_action` into `run_summary.json` and
prints it near the top of `run_summary.md`. Treat that as the first unattended
review cue. The same action code is also printed to stdout and copied to the
run-level `artifact_index.json`, so CI logs and artifact upload indexes can be
routed without opening the summary first:

| Recommended action | Meaning |
| --- | --- |
| `fix-request-package` | Source/candidate provenance or request structure is blocked. Fix the request before exporting AutoCAD PNGs. |
| `provide-returned-autocad-pngs` | Requested AutoCAD PNGs are still missing. Return files with the requested names. |
| `inspect-returned-reference-warnings` | Returned PNGs exist, but intake flagged capture-quality warnings. Inspect before trusting visual conclusions. |
| `recapture-autocad-or-provide-window` | The matched-view gate failed. Recapture AutoCAD at matched extents or provide the real world window; do not tune the renderer. |
| `review-x3-pass` | The matched-view gate passed. Review X3 and artifacts before opening renderer work. |
| `inspect-compare-failure` | Inputs reached compare, but compare failed. Inspect compare artifacts and per-case logs. |

For multi-drawing runs, inspect `case_actions` and `case_action_counts` in
`run_summary.json` or the run-level `artifact_index.json`. `run_summary.md`
also prints a "Case Actions" table, and the wrapper prints case-action counts
to stdout. The case-level priority is intentionally fail-closed: request
validation issues, missing returned PNGs, and intake warnings are listed before
compare triage, so a suspicious input is not routed as a renderer defect.

Generated requests may include source-DXF and candidate-PNG provenance
(`sha256` + byte size). When present, `acad_reference_batch.py --from-request`
checks those files before building the next manifest. A mismatch means the
request/candidate inputs drifted and the run blocks before X3.

Before asking for or fulfilling AutoCAD PNGs, validate the request package
itself:

```bash
python3 tools/render_regression/acad_reference_batch.py \
  --validate-request "$REQUEST_DIR/reference_request.json" \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --out-dir "$NEXT_DIR/request-validation"
```

The validation writes:

- `$NEXT_DIR/request-validation/reference_request_validation.json`
- `$NEXT_DIR/request-validation/reference_request_validation.md`
- `$NEXT_DIR/request-validation/artifact_index.json`

It checks request/candidate identity before any returned AutoCAD PNG exists:
source DXF presence and declared hash/size, candidate PNG presence and declared
hash/size, duplicate case/output names, plain-filename output names, and
positive expected sizes. This is an input-package gate only; it does not compare
renders and does not claim AutoCAD equivalence.

```bash
python3 tools/render_regression/acad_manifest_compare.py \
  --manifest "$NEXT_DIR/input/acad_manifest.json" \
  --candidate-cases "$NEXT_DIR/input/candidate_cases.json" \
  --out-dir "$NEXT_DIR/compare"
```

## Run The Matched-View Harness

```bash
python3 tools/render_regression/acad_manifest_compare.py \
  --manifest "$CASE_DIR/acad_manifest.json" \
  --candidate-cases "$CASE_DIR/candidate_cases.json" \
  --out-dir "$CASE_DIR/compare"
```

Expected outputs:

- `$CASE_DIR/compare/summary.json`
- `$CASE_DIR/compare/summary.tsv`
- `$CASE_DIR/compare/artifact_index.json`
- `$CASE_DIR/compare/contact_sheet.png`
- `$CASE_DIR/compare/viewspace/G11_viewspace.json`
- `$CASE_DIR/compare/overlays/G11_overlay.png` when comparable
- `$CASE_DIR/compare/text/G11_text_provenance.json` when a render report is
  supplied
- `$CASE_DIR/compare/semantic/G11_semantic_classes.json` when semantic mask and
  report are supplied

`contact_sheet.png` is a quick-review artifact: per row it shows AutoCAD
reference, VemCAD candidate, and overlay, with the view-space status and X3 band
printed above the row. It is useful for unattended runs, but the JSON/TSV remain
authoritative.

`compare/artifact_index.json` also carries `status`, `case_count`,
`compared_count`, `issue_count`, `triage_bucket_counts`,
`viewspace_status_counts`, and `x3_band_counts`, so artifact consumers can route
`renderer-candidate` versus `recapture-required` runs before opening
`summary.json`.

To route any batch/run/compare artifact index through one command:

```bash
python3 tools/render_regression/acad_artifact_route.py <artifact_index.json> --text
```

The route helper is read-only. It does not compare renders, does not change
exit semantics, and does not claim AutoCAD equivalence; it only translates the
artifact index into the next safe operator action.

## Interpret The Result

First inspect:

```bash
jq '.status, .rows[0].viewspace_status, .rows[0].viewspace_reason' \
  "$CASE_DIR/compare/summary.json"
```

Decision table:

| Harness status | Meaning | Next action |
| --- | --- | --- |
| `pass` with `viewspace_status=match` | X3 is eligible to interpret. | Review X3, semantic rows, text flags/notes. Open renderer work only if a concrete class/entity defect is isolated. |
| `viewspace_mismatch` | AutoCAD and VemCAD are still not in the same view-space. | Recapture AutoCAD or provide the real world `--window`; do not tune renderer. |
| `blocked` | Manifest/candidate input failed validation. | Fix missing paths, capture method, expected size, or unreadable PNG. |
| `compare_failed` | `compare_vs_acad.py` failed after valid inputs. | Inspect per-case stdout and view-space report. |

Never claim AutoCAD equivalence unless the harness reaches
`viewspace_status=match`.

## Current G11 State

The existing AutoCAD reference:

- `/tmp/vemcadautocadplot/batch/png/G11-1.png`

has already been tested. It remains blocked:

- baseline: `viewspace_mismatch`, `ink_iou=0.8021`;
- `content_bbox` world window: still `viewspace_mismatch`, `ink_iou=0.8081`;
- hand-shrunk window: still `viewspace_mismatch`, `ink_iou=0.2471`;
- diagnostic reference-envelope: removes framing mismatch as a raster
  diagnostic, but is not a world-space contract and remains fallback
  (`ink_iou=0.8277`).

Therefore the next valid input is a fresh AutoCAD model-extents export or the
actual AutoCAD world plot/window rectangle.
