# DEV/V — Render Fidelity Reference Input Continuation Closeout (2026-06-29)

## Scope

This closeout records the continuation run after
`docs/DEV_AND_VERIFICATION_RENDER_FIDELITY_TWO_WEEK_20260629.md`.

The goal was to keep developing without crossing the hard AutoCAD ground-truth
boundary:

- no GUI AutoCAD automation;
- no renderer tuning from `viewspace_mismatch`;
- no private drawing or AutoCAD PNG committed;
- no AutoCAD-equivalence claim without a matched-view comparison.

## Delivered

| PR | Commit | Slice | Result |
| --- | --- | --- | --- |
| #192 | `ef22331` | Returned-reference intake preflight | Merged, CI green |
| #193 | `2abc374` | Reference batch artifact index | Merged, CI green |
| #194 | `f52a86d` | One-command reference request runner | Merged, CI green |
| #195 | `544cf2c` | Generated request handoff command | Merged, CI green |

## What Changed

### #192 — Returned Reference Intake Preflight

`acad_reference_batch.py --from-request` now writes:

- `reference_intake.json`
- `reference_intake.md`

It records capture-quality signals for returned AutoCAD PNGs:

- PNG size and long edge;
- alpha/transparency presence;
- sampled corner-white ratio.

Missing or unreadable PNGs still fail closed. Present-but-suspicious PNGs are
`status=review`, not hidden success.

### #193 — Reference Batch Artifact Index

`acad_reference_batch.py` now writes `artifact_index.json` for:

- successful `--cases` runs;
- successful `--from-request` runs;
- missing-reference blocked runs.

This gives unattended input-prep runs a single review entry point.

### #194 — One-Command Reference Request Runner

New command:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request <reference_request.json> \
  --candidate-cases <candidate_cases.json> \
  --reference-dir <returned-png-dir> \
  --case-id G11 \
  --out-dir <run-dir>
```

It runs:

1. `acad_reference_batch.py` into `<run-dir>/input`;
2. `acad_manifest_compare.py` into `<run-dir>/compare`;
3. `run_summary.json` and `run_summary.md` at the run root.

It preserves existing gates: input-blocked stops before compare, and
`viewspace_mismatch` still exits `2`.

### #195 — Generated Request Handoff

Generated `reference_request.md` now includes the next command to run after
AutoCAD PNGs are returned. The command points at
`acad_reference_request_run.py` and carries the current `candidate_cases.json`
path.

## Verification

Each PR passed VemCAD CI:

- `pytest`
- `build-and-smoke`

Local verification during development:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 3 passed

python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 92 passed
```

Private workflow smoke:

- G11 partial returned-reference path using the old existing PNG:
  - input-prep: pass;
  - intake: pass;
  - compare: `viewspace_mismatch`;
  - wrapper exit: `2`.
- Missing-reference smoke:
  - input-prep: blocked;
  - `artifact_index.json` still written with `missing_references_json` and
    `missing_references_markdown`.

These smokes prove the workflow behavior. They do not convert the old G11 PNG
into valid ground truth.

## State At Initial Closeout

- VemCAD `origin/main` at the initial closeout: `544cf2c`.
- Open VemCAD PRs at closeout: pre-existing draft `#1` only.
- The returned-reference loop is now:

```text
reference_request.json
  -> returned AutoCAD PNG directory
  -> acad_reference_request_run.py
  -> input/reference_intake.*
  -> input/artifact_index.json
  -> compare/summary.*
  -> compare/artifact_index.json
  -> run_summary.*
```

## Remaining Hard Gate

Formal render fidelity still requires a fresh matched-view AutoCAD PNG:

- model space;
- drawing extents / fit-to-drawing;
- white background;
- monochrome off;
- no toolbar/chrome/screenshot crop;
- long edge at least `1600px`.

Without that returned PNG, the correct status remains `viewspace_mismatch` or
`recapture-required`, and renderer tuning must not start.

## Next Command When Input Arrives

For the current private request bundle:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir <returned-png-dir> \
  --case-id G11 \
  --out-dir <next-run-dir>
```

Only if the resulting compare reaches `viewspace_status=match` should X3 be
interpreted as a render-fidelity signal.

## Follow-Up Hardening From Review

Status: implemented in this branch.

The post-closeout review correctly noted that the manifest check was partly a
declaration gate: in the `--from-request` path, `expected_size` had been derived
from the returned PNG itself, so the size check could not catch a wrong-sized
return.

Changes:

- Generated `reference_request.json` now carries `requested_expected_size`
  when the current AutoCAD PNG size can be read.
- `acad_reference_batch.py --from-request` uses
  `requested_expected_size`/`expected_size` from the request when present,
  rather than deriving `expected_size` from the returned PNG.
- A wrong-sized returned PNG now produces an `expected_size_mismatch` manifest
  block.
- `acad_reference_batch.py` clears only its known generated files at the start
  of each run, so a successful re-run in the same `out-dir` cannot leave stale
  `missing_references.*` reports behind.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 8 passed

python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 94 passed
```

Boundary:

- Input-chain hardening only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- Still no AutoCAD-equivalence claim without `viewspace_status=match`.

## Follow-Up Provenance Hardening

Status: implemented in this branch.

Purpose:

- Make generated request packages reproducible enough to detect source or
  candidate drift between request generation and returned-reference fulfilment.
- Record returned AutoCAD PNG hashes for evidence review without pretending a
  hash proves the PNG depicts the right drawing.

Changes:

- Generated `reference_request.json` now carries:
  - `source_dxf_sha256`
  - `source_dxf_size_bytes`
  - `candidate_png_sha256`
  - `candidate_png_size_bytes`
- `acad_reference_batch.py --from-request` fail-closes when a request declares
  a source DXF or candidate PNG sha256 and the current file does not match.
- `reference_intake.json` now records the returned AutoCAD PNG sha256 and file
  size in `inspection`.
- Older request files without these provenance fields remain supported.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 10 passed

python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 96 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/run
# AutoCAD reference request run: viewspace_mismatch
# exit code: 2
```

Smoke result:

- old request without provenance fields remains compatible;
- input-prep passed;
- compare remained `viewspace_mismatch`;
- returned PNG sha256 was recorded in `reference_intake.json`.

Boundary:

- Provenance hardening only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- Does not attempt to infer whether the returned PNG depicts the same drawing;
  the matched-view X3 gate remains the only fidelity gate.

## Follow-Up Run Summary Hardening

Status: implemented in this branch.

Purpose:

- Make the one-command runner's top-level summary show returned-reference
  intake quality without requiring the operator to open `input/reference_intake`.

Changes:

- `acad_reference_request_run.py` now copies these fields from
  `input/reference_intake.json` into `run_summary.json`:
  - `reference_intake_status`
  - `reference_intake_error_count`
  - `reference_intake_warning_count`
- `run_summary.md` prints the intake status and warning count in the result
  block.
- Missing-reference blocked runs, which never produce `reference_intake`, keep
  those fields empty/null.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 4 passed

python3 -m pytest tools/render_regression/tests -q
# 97 passed
```

Boundary:

- Summary/reporting only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- Does not change X3 semantics or AutoCAD-equivalence wording.

## Follow-Up Identity Advisory Diagnostics

Status: implemented in this branch.

Purpose:

- Add a cheap content-shape sanity check for returned AutoCAD PNGs without
  pretending the tool can prove the PNG depicts the right drawing.
- Surface likely "wrong drawing" or "wrong capture window" cases earlier than
  the full X3 comparison.

Changes:

- `reference_intake.json` now records
  `inspection.identity_advisory`.
- The advisory compares the returned AutoCAD PNG ink bounding box with the
  candidate VemCAD PNG ink bounding box.
- If both ink profiles are available and their bbox aspect differs by more than
  `0.25`, the intake adds a warning:
  `ink_bbox_aspect_divergence`.

Boundary:

- Diagnostic only.
- Not a pass/fail gate.
- Not a semantic mask.
- Not a proof of drawing identity.
- Not a renderer change.
- Does not replace `viewspace_status=match` before interpreting X3.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py \
  tools/render_regression/tests/test_acad_manifest_compare.py -q
# 10 passed

python3 -m pytest tools/render_regression/tests -q
# 98 passed
```

## Follow-Up Request Package Validation

Status: implemented in this branch.

Purpose:

- Validate `reference_request.json` and its matching `candidate_cases.json`
  before AutoCAD PNG fulfilment.
- Catch request-package drift and ambiguity before the operator spends time
  exporting or returning PNGs.

New command:

```bash
python3 tools/render_regression/acad_reference_batch.py \
  --validate-request <reference_request.json> \
  --candidate-cases <candidate_cases.json> \
  --out-dir <validation-dir>
```

Outputs:

- `reference_request_validation.json`
- `reference_request_validation.md`
- `artifact_index.json`

Checks:

- source DXF exists;
- declared source DXF sha256 and byte size still match;
- matching candidate case exists;
- candidate PNG exists;
- declared candidate PNG sha256 and byte size still match;
- requested output PNG names are unique plain filenames;
- request case ids and candidate ids are not ambiguous;
- requested expected sizes are positive.

Boundary:

- Input-package validation only.
- Does not require returned AutoCAD PNGs.
- Does not compare renders.
- Does not claim AutoCAD equivalence.
- Does not change X3 semantics.
- Does not change renderer code.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 13 passed

python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py \
  tools/render_regression/tests/test_acad_manifest_compare.py -q
# 10 passed

python3 -m pytest tools/render_regression/tests -q
# 100 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_batch.py \
  --validate-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-request-validation-smoke-20260629
# AutoCAD reference request validation: pass (1 cases)
```

## Follow-Up Generated Handoff Validation Command

Status: implemented in this branch.

Purpose:

- Make newly generated `reference_request.md` files self-contained for the
  request-package validation step.
- Keep operators from jumping directly from recapture request to AutoCAD export
  without first checking source/candidate drift.

Changes:

- `reference_request.md` now includes a "Before Capture Or Fulfilment" section.
- The section prints the exact validation command:
  `acad_reference_batch.py --validate-request ... --candidate-cases ...`.
- The existing "After The PNGs Are Returned" runner handoff remains unchanged.

Boundary:

- Handoff/documentation only.
- No renderer change.
- No AutoCAD PNG required.
- No X3 semantics change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 100 passed
```

## Follow-Up Enforced Fulfilment Validation

Status: implemented in this branch.

Purpose:

- Make request-package validation part of the normal `--from-request` fulfilment
  path, not merely an optional preflight command.
- Surface validation blocks in the one-command runner summary.

Changes:

- `acad_reference_batch.py --from-request` now writes
  `reference_request_validation.json/md` before checking returned PNGs.
- If request validation is `blocked`, fulfilment stops before
  `missing_references`, `reference_intake`, manifest generation, or X3.
- `acad_reference_request_run.py` now copies
  `reference_request_validation_status/error_count/warning_count` into
  `run_summary.json/md`.

Boundary:

- Input-package gate only.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- No X3 semantics change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 13 passed

python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 5 passed

python3 -m pytest tools/render_regression/tests -q
# 101 passed
```

## Follow-Up Standalone Compare Route Reports

Status: implemented in this branch.

Purpose:

- Give standalone `acad_manifest_compare.py` runs the same stable route report
  artifacts that request-run already emits.
- Let CI upload compare-level `route_summary.json/md` without a second
  post-processing command.

Changes:

- `acad_manifest_compare.py` now writes:
  - `<compare-dir>/route_summary.json`
  - `<compare-dir>/route_summary.md`
- `compare/artifact_index.json` includes both route report files.
- Route reports are generated from the shared `acad_artifact_route.py` logic,
  so compare and request-run routing cannot drift.

Boundary:

- Reporting/indexing only.
- No routing-rule change.
- No renderer change.
- No X3 scoring change.
- No AutoCAD PNG equivalence claim.
- `viewspace_mismatch` remains recapture/window input work.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 11 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_manifest_compare.py \
  --manifest /private/tmp/vemcad-autocad-batch-current/input/acad_manifest.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --out-dir /private/tmp/vemcad-compare-route-report-smoke-20260629
# AutoCAD manifest compare: viewspace_mismatch (12/12 compared, 0 issues)
# route_summary.json.recommended_next_action.code=recapture-autocad-or-provide-window
# route_summary.md includes the read-only/no-equivalence boundary statement
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-run-next-action-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# recommended_next_action.code=recapture-autocad-or-provide-window
```

## Follow-Up Recommended Action Surfacing

Status: implemented in this branch.

Purpose:

- Make the recommended action visible from CI logs and the run-level artifact
  index without opening `run_summary.json` first.
- Keep artifact consumers and humans aligned on the same operator cue.

Changes:

- `acad_reference_request_run.py` prints
  `recommended next action: <code>` after the run status.
- `<run-dir>/artifact_index.json` now carries top-level `status` and
  `recommended_next_action` fields in addition to the artifact list.

Boundary:

- Reporting/indexing only.
- No recommendation-rule change.
- No renderer change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 5 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-run-action-surface-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# recommended next action: recapture-autocad-or-provide-window
# artifact_index.status=viewspace_mismatch
# artifact_index.recommended_next_action.code=recapture-autocad-or-provide-window
```

## Follow-Up Per-Case Action Summary

Status: implemented in this branch.

Purpose:

- Make multi-drawing unattended runs reviewable without opening each per-case
  compare row first.
- Separate cases that need recapture, request-package repair, intake review,
  matched-view renderer investigation, or no immediate renderer work.

Changes:

- `run_summary.json` now includes:
  - `case_actions`
  - `case_action_counts`
- The run-level `artifact_index.json` also includes `case_action_counts`.
- `run_summary.md` prints a "Case Actions" table when case-level actions are
  available.
- Case-action priority is fail-closed:
  request validation issues > missing returned PNGs > intake warnings >
  compare triage.

Boundary:

- Summary/reporting only.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- Does not turn `viewspace_mismatch` into renderer work.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 6 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-run-case-actions-index-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# case action counts: recapture-autocad-or-provide-window=1
# artifact_index.case_actions[0].code=recapture-autocad-or-provide-window
# artifact_index.case_actions[0].triage_bucket=recapture-required
```

## Follow-Up Artifact Route Helper

Status: implemented in this branch.

Purpose:

- Provide one read-only command that can route any AutoCAD reference artifact
  index: batch input-prep, request run, or compare output.
- Let CI or an operator ask "what next?" without hand-writing different `jq`
  expressions for each artifact index schema.

New command:

```bash
python3 tools/render_regression/acad_artifact_route.py <artifact_index.json>
python3 tools/render_regression/acad_artifact_route.py <artifact_index.json> --text
```

Behavior:

- Batch indexes route missing PNGs, request validation blocks, intake review,
  and pass/continue states.
- Request-run indexes preserve `recommended_next_action`, `case_actions`, and
  `case_action_counts`.
- Compare indexes route `renderer-candidate` before `recapture-required`,
  because a matched-view renderer candidate is actionable whereas
  `viewspace_mismatch` remains an input issue.

Boundary:

- Read-only artifact routing only.
- No renderer change.
- No X3 scoring change.
- No AutoCAD PNG equivalence claim.
- Unknown schemas fail closed with exit code `2`.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 4 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-artifact-route-smoke-20260629

python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-smoke-20260629/artifact_index.json --text
# recommended_next_action: recapture-autocad-or-provide-window
# case_action_counts: recapture-autocad-or-provide-window=1

python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-smoke-20260629/compare/artifact_index.json --text
# recommended_next_action: recapture-autocad-or-provide-window
# triage_bucket_counts: recapture-required=1
```

## Follow-Up Artifact Route Directory Input

Status: implemented in this branch.

Purpose:

- Make the artifact route helper easier to use after CI artifact extraction.
- Allow operators to pass the batch/run/compare directory directly instead of
  manually appending `artifact_index.json`.

Changes:

- `acad_artifact_route.py` now accepts either:
  - an `artifact_index.json` file; or
  - a directory containing `artifact_index.json`.
- Directories without `artifact_index.json` fail closed with exit code `2`.

Boundary:

- Read-only CLI ergonomics only.
- No routing-rule change.
- No renderer change.
- No AutoCAD PNG equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 6 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-artifact-route-dir-smoke-20260629

python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-dir-smoke-20260629 --text
# kind: request_run
# recommended_next_action: recapture-autocad-or-provide-window

python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-dir-smoke-20260629/compare --text
# kind: compare
# recommended_next_action: recapture-autocad-or-provide-window
```

## Follow-Up Artifact Route Multiple Inputs

Status: implemented in this branch.

Purpose:

- Let unattended runs route the input-prep, run-root, and compare artifact
  indexes in one command after CI artifact extraction.
- Reduce manual `jq`/path handling while preserving the fail-closed routing
  discipline.

Changes:

- `acad_artifact_route.py` now accepts one or more artifact index files or
  directories.
- Single-input JSON remains the original `vemcad.acad_artifact_route/v1`
  object for backward compatibility.
- Multi-input JSON returns `vemcad.acad_artifact_route_batch/v1` with one
  `routes[]` entry per supplied path.
- Multi-input `--text` prints one section per route.

Boundary:

- Read-only CLI ergonomics only.
- No routing-rule change.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- `viewspace_mismatch` still routes to recapture/window input, not renderer
  tuning.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 8 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-artifact-route-multi-smoke-20260629

python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-multi-smoke-20260629/input \
  /private/tmp/vemcad-artifact-route-multi-smoke-20260629 \
  /private/tmp/vemcad-artifact-route-multi-smoke-20260629/compare --text
# route: 1
# recommended_next_action: continue-to-request-run
# route: 2
# recommended_next_action: recapture-autocad-or-provide-window
# route: 3
# recommended_next_action: recapture-autocad-or-provide-window
```

## Follow-Up Artifact Route Recursive Discovery

Status: implemented in this branch.

Purpose:

- Let operators point `acad_artifact_route.py` at one unpacked CI artifact root
  and discover every nested `artifact_index.json` automatically.
- Keep the default directory behavior strict, so a misspelled or too-high
  directory still fails closed unless `--recursive` is explicit.

Changes:

- Added `--recursive` to discover `artifact_index.json` files below directory
  inputs.
- Discovered indexes are sorted and de-duplicated.
- Recursive runs reuse the existing single-route or batch-route output shapes:
  one discovered index returns the original route object; multiple discovered
  indexes return `vemcad.acad_artifact_route_batch/v1`.
- Empty recursive discovery fails closed with exit code `2`.

Boundary:

- Read-only CLI ergonomics only.
- No routing-rule change.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- `viewspace_mismatch` still routes to recapture/window input, not renderer
  tuning.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 10 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-artifact-route-recursive-smoke-20260629

python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-recursive-smoke-20260629 --recursive --text
# route: 1
# kind: request_run
# recommended_next_action: recapture-autocad-or-provide-window
# route: 2
# kind: compare
# recommended_next_action: recapture-autocad-or-provide-window
# route: 3
# kind: batch
# recommended_next_action: continue-to-request-run
```

## Follow-Up Artifact Route Batch Summary

Status: implemented in this branch.

Purpose:

- Make multi-route and recursive artifact routing useful in CI logs without
  reading every route section first.
- Surface the distribution of route kinds, statuses, and recommended actions at
  the top of the route payload.

Changes:

- Multi-route JSON now includes:
  - `kind_counts`
  - `status_counts`
  - `recommended_action_counts`
- Multi-route `--text` now starts with `route_count` and the three aggregate
  count lines before the per-route sections.
- Single-route JSON/text output remains unchanged.

Boundary:

- Read-only reporting ergonomics only.
- No routing-rule change.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- `viewspace_mismatch` remains an input/recapture action unless a matched-view
  route explicitly reports a renderer candidate.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 10 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-recursive-smoke-20260629 --recursive --text
# route_count: 3
# kind_counts: batch=1, compare=1, request_run=1
# status_counts: pass=1, viewspace_mismatch=2
# recommended_action_counts: continue-to-request-run=1, recapture-autocad-or-provide-window=2
```

## Follow-Up Artifact Route Report Files

Status: implemented in this branch.

Purpose:

- Let CI upload stable route artifacts instead of relying only on stdout.
- Give reviewers both a machine-readable route payload and a compact Markdown
  route report.

Changes:

- `acad_artifact_route.py` now supports:
  - `--out-json <path>` to write the route payload JSON;
  - `--out-md <path>` to write a Markdown route report.
- Stdout behavior remains unchanged.
- Parent output directories are created automatically.
- The Markdown report includes an explicit boundary statement that it is
  read-only routing guidance and does not claim AutoCAD equivalence.

Boundary:

- Read-only route reporting only.
- No routing-rule change.
- No renderer change.
- No X3 scoring change.
- No AutoCAD PNG equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 11 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_artifact_route.py \
  /private/tmp/vemcad-artifact-route-recursive-smoke-20260629 --recursive \
  --out-json /private/tmp/vemcad-artifact-route-report-smoke-20260629/route_summary.json \
  --out-md /private/tmp/vemcad-artifact-route-report-smoke-20260629/route_summary.md
# route_summary.json.recommended_action_counts={'continue-to-request-run': 1, 'recapture-autocad-or-provide-window': 2}
# route_summary.md includes the read-only/no-equivalence boundary statement
```

## Follow-Up Request-Run Route Reports

Status: implemented in this branch.

Purpose:

- Make `acad_reference_request_run.py` produce the route reports directly, so
  CI artifact consumers do not need a second post-processing command.
- Keep the run root as the single review entry point: run summary, artifact
  index, and route reports live together.

Changes:

- Each request run now writes:
  - `<run-dir>/route_summary.json`
  - `<run-dir>/route_summary.md`
- The run-level `artifact_index.json` includes both route report files.
- The route reports are generated from the same `acad_artifact_route.py` logic
  used by the standalone CLI.
- The route report covers whatever indexes exist for the run:
  input + run root + compare when compare ran, or input + run root when the
  run stops before compare.

Boundary:

- Reporting/indexing only.
- No routing-rule change.
- No renderer change.
- No X3 scoring change.
- No AutoCAD PNG equivalence claim.
- `viewspace_mismatch` remains recapture/window input work.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 11 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-request-run-route-report-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# route_summary.json.recommended_action_counts={'continue-to-request-run': 1, 'recapture-autocad-or-provide-window': 2}
# route_summary.md includes the read-only/no-equivalence boundary statement
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-run-case-actions-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# case_action_counts={'recapture-autocad-or-provide-window': 1}
# case_actions[0].source=compare
# case_actions[0].triage_bucket=recapture-required
```

## Follow-Up Batch Artifact Index Status

Status: implemented in this branch.

Purpose:

- Make input-level `acad_reference_batch.py` artifact indexes self-describing,
  not just file lists.
- Let unattended validation/intake/missing-reference jobs be routed before the
  wrapper creates a run summary.

Changes:

- `acad_reference_batch.py` now writes status metadata to
  `<out-dir>/artifact_index.json`:
  - `stage`
  - `status`
  - `case_count`
  - `error_count`
  - `warning_count`
  - `reference_request_validation_status`
  - `reference_intake_status`
  - `missing_count`
  - `batch_validation_status`
- The index preserves intake `review` status when returned PNGs have warnings,
  even if the generated manifest itself validates as `pass`.
- Manifest-level validation can still override the index to `blocked` when the
  generated manifest is not usable.

Boundary:

- Artifact-index metadata only.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- No exit-code change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 13 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_batch.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-batch-index-status-smoke-20260629
# AutoCAD reference batch: pass (1 cases)
# artifact_index.stage=reference_intake
# artifact_index.status=pass
# artifact_index.reference_request_validation_status=pass
# artifact_index.reference_intake_status=pass
# artifact_index.batch_validation_status=pass
```

## Follow-Up Compare Artifact Index Status

Status: implemented in this branch.

Purpose:

- Make `acad_manifest_compare.py` artifact indexes routeable without opening
  `summary.json` first.
- Surface compare status and triage distribution at the same level as uploaded
  artifacts.

Changes:

- `<compare-dir>/artifact_index.json` now includes:
  - `status`
  - `case_count`
  - `compared_count`
  - `issue_count`
  - `triage_bucket_counts`
  - `viewspace_status_counts`
  - `x3_band_counts`

Boundary:

- Artifact-index metadata only.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- No X3 scoring change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-compare-index-status-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# compare/artifact_index.status=viewspace_mismatch
# compare/artifact_index.triage_bucket_counts={'recapture-required': 1}
# compare/artifact_index.viewspace_status_counts={'mismatch': 1}
# compare/artifact_index.x3_band_counts={'fallback': 1}
```

## Follow-Up Run Artifact Case Actions

Status: implemented in this branch.

Purpose:

- Make the run-level `artifact_index.json` a complete machine-routing entry
  point for batch request runs.
- Avoid requiring artifact consumers to open `run_summary.json` just to know
  which case needs recapture, returned PNG fulfilment, intake review, or X3
  review.

Changes:

- `<run-dir>/artifact_index.json` now carries the full `case_actions` array,
  in addition to `case_action_counts`.
- `acad_reference_request_run.py` prints
  `case action counts: <code>=<count>, ...` to stdout after the recommended
  next action.

Boundary:

- Reporting/indexing only.
- No recommendation-rule change.
- No renderer change.
- No AutoCAD PNG equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 6 passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-validate-on-fulfill-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# run_summary: reference_request_validation_status=pass, reference_intake_status=pass
```

## Follow-Up Run Artifact Index

Status: implemented in this branch.

Purpose:

- Give each one-command request run a stable artifact index at the run root.
- Make unattended artifact uploads reviewable from one top-level JSON, even
  when the run stops before compare.

Changes:

- `acad_reference_request_run.py` now writes `<run-dir>/artifact_index.json`.
- The index lists:
  - `run_summary.json/md`;
  - input artifact index;
  - request validation artifacts;
  - intake or missing-reference artifacts when present;
  - compare summary/index artifacts when compare ran.
- `run_summary.json/md` now point back to the run-level artifact index.

Boundary:

- Reporting/indexing only.
- No renderer change.
- No AutoCAD PNG equivalence claim.
- No X3 semantics change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 5 passed

python3 -m pytest tools/render_regression/tests -q
# 101 passed
```

## Follow-Up Request Capture Contract Validation

Status: implemented in this branch.

Purpose:

- Move capture-contract errors from the later manifest gate to the earlier
  request-package validation gate.
- Stop an operator from spending time exporting/returning PNGs from a request
  that already declares a diagnostic capture method or unmatched view contract.

Changes:

- `acad_reference_batch.py --validate-request` now validates:
  - `requested_capture_method` against the same gate/diagnostic method sets as
    `acad_reference_manifest.py`;
  - `requested_view_contract` against the same matched-view contract set.
- Invalid requests fail closed with:
  - `diagnostic_requested_capture_method`;
  - `unknown_requested_capture_method`;
  - `unmatched_requested_view_contract`.
- `reference_request_validation.json/md` now records the normalized requested
  capture method and view contract per case, so the validation report explains
  exactly which declared contract blocked the request.

Boundary:

- Request-package validation only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.
- Missing fields remain backward compatible: absent values normalize to the
  existing defaults `plot-export` and `model-extents`.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 14 passed

python3 -m pytest tools/render_regression/tests -q
# 114 passed
```

## Follow-Up Batch Route Reports

Status: implemented in this branch.

Purpose:

- Make batch/input-prep outputs self-routing, just like standalone compare and
  request-run outputs.
- Let CI or an unattended operator upload one `route_summary.json/md` from a
  batch run without invoking `acad_artifact_route.py` as a second command.

Changes:

- `acad_reference_batch.py` now writes:
  - `<out-dir>/route_summary.json`;
  - `<out-dir>/route_summary.md`.
- The batch `artifact_index.json` lists both route summary files.
- The route payload is produced by the shared `acad_artifact_route.py`
  implementation, so batch/request-run/compare routing cannot drift.
- The route summary covers all batch stages: manifest generation, request
  validation, missing returned references, and returned-reference intake.

Boundary:

- Reporting/indexing only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 14 passed

python3 -m pytest tools/render_regression/tests -q
# 114 passed
```

## Follow-Up Batch Route Stdout

Status: implemented in this branch.

Purpose:

- Make `acad_reference_batch.py` logs self-directing in CI and unattended
  shells.
- Avoid requiring an operator to open `route_summary.json` just to see the next
  safe action after input-prep.

Changes:

- After writing the batch route report, `acad_reference_batch.py` now prints:
  - `route summary  : <out-dir>/route_summary.md`;
  - `recommended next action: <code>`.
- Successful manifest/request-validation/reference-intake paths print the
  route on stdout.
- Blocked input-prep paths print the route on stderr alongside the blocking
  message and artifact index.

Boundary:

- CLI/log surfacing only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 14 passed

python3 -m pytest tools/render_regression/tests -q
# 114 passed
```

## Follow-Up Standalone Compare Route Stdout

Status: implemented in this branch.

Purpose:

- Make standalone `acad_manifest_compare.py` logs self-directing, matching the
  request-run and batch/input-prep CLIs.
- Let CI logs show the next safe action without requiring the reviewer to open
  `route_summary.json`.

Changes:

- After writing `route_summary.json/md`, `acad_manifest_compare.py` now prints:
  - `route summary  : <compare-dir>/route_summary.md`;
  - `recommended next action: <code>`.
- Covered routes:
  - matched-view pass -> `review-x3-pass`;
  - `viewspace_mismatch` -> `recapture-autocad-or-provide-window`;
  - blocked manifest/dry-run -> `inspect-compare-input-block`.

Boundary:

- CLI/log surfacing only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 6 passed

python3 -m pytest tools/render_regression/tests -q
# 114 passed
```

## Follow-Up Multi-Route Top-Level Recommendation

Status: implemented in this branch.

Purpose:

- Make recursive/multi-index route reports directly actionable from their top
  summary.
- Avoid requiring CI or an unattended operator to derive one safe next action
  from `recommended_action_counts`.
- Preserve the existing input-first discipline: request-package or returned-PNG
  repairs are routed before renderer-candidate work.

Changes:

- Multi-route `acad_artifact_route.py` payloads now include
  `recommended_next_action`.
- Multi-route `--text` and Markdown reports print that top-level action in the
  summary section.
- The selected action points at the source route artifact when the child route
  does not already name a more specific artifact.
- Single-route behavior is unchanged.

Priority:

1. `fix-request-package`
2. `provide-returned-autocad-pngs`
3. `inspect-returned-reference-warnings`
4. `inspect-renderer-candidate`
5. `recapture-autocad-or-provide-window`
6. inspect/failure actions
7. `review-x3-pass`
8. `continue-to-request-run`

Boundary:

- Route aggregation only.
- No routing-rule change for individual artifact indexes.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 12 passed

python3 -m pytest tools/render_regression/tests -q
# 114 passed
```

## Follow-Up Machine-Readable Route Boundary

Status: implemented in this branch.

Purpose:

- Put the existing route-report boundary into JSON, not only Markdown prose.
- Let CI/artifact consumers assert that an AutoCAD route report is read-only
  routing guidance and not an AutoCAD-equivalence or renderer-change result.

Changes:

- Single-route and multi-route `acad_artifact_route.py` JSON payloads now
  include:
  - `read_only_routing: true`
  - `renders_dxf: false`
  - `compares_renders: false`
  - `changes_x3_scoring: false`
  - `changes_renderer: false`
  - `autocad_equivalence_claim: false`
- Multi-route `--text` output prints
  `autocad_equivalence_claim: false` in the top summary.
- Route Markdown prints `read_only_routing` and
  `autocad_equivalence_claim` beside the action summary.

Boundary:

- Route metadata only.
- No routing-rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 12 passed

python3 -m pytest tools/render_regression/tests -q
# 115 passed
```

## Follow-Up Artifact Index Boundary

Status: implemented in this branch.

Purpose:

- Make the primary `artifact_index.json` files self-describing before a route
  report is opened.
- Let CI/artifact consumers distinguish input-prep indexes, compare indexes,
  and one-command run indexes without inferring whether they rendered DXFs,
  compared images, changed scoring, or claimed AutoCAD equivalence.

Changes:

- Batch artifact indexes now include a `boundary` object with:
  `renders_dxf=false`, `compares_renders=false`, `changes_x3_scoring=false`,
  `changes_renderer=false`, `requires_viewspace_match=false`, and
  `autocad_equivalence_claim=false`.
- Compare artifact indexes now include a `boundary` object with:
  `renders_dxf=false`, `changes_x3_scoring=false`,
  `changes_renderer=false`, `requires_viewspace_match=true`, and
  `autocad_equivalence_claim=false`.
- Compare `compares_renders` is true only when `compared_count > 0`; blocked
  manifest/input runs do not pretend a comparison occurred.
- Request-run artifact indexes now include a `boundary` object and set
  `compares_renders` only when a compare artifact index exists.

Boundary:

- Artifact metadata only.
- No routing-rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Required-Action Gate

Status: implemented in this branch.

Purpose:

- Let CI or unattended scripts assert that a route payload reached the expected
  next action.
- Fail closed when an artifact tree routes somewhere unexpected, without making
  downstream scripts parse JSON manually.

Changes:

- `acad_artifact_route.py` now accepts:
  `--require-action <recommended_next_action.code>`.
- The option works for both single artifact indexes and multi-route/recursive
  payloads because it checks the top-level `recommended_next_action`.
- On mismatch the command exits `2` and prints the actual action plus the
  action artifact when available.

Boundary:

- Route assertion only.
- No routing-rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Operator README Route Handoff

Status: implemented in this branch.

Purpose:

- Move the reference-request / route-artifact operating path into the public
  render regression README.
- Keep future operators from needing to reverse-engineer the flow from this
  long closeout ledger.

Changes:

- `tools/render_regression/README.md` now documents:
  - `acad_manifest_compare.py`
  - `acad_reference_request_run.py`
  - `acad_artifact_route.py <run-dir> --recursive --text`
  - `acad_artifact_route.py --require-action <code>`
- The README names the artifact-index `boundary` fields and the route
  `recommended_next_action` codes.
- The README keeps the same hard boundary: route assertions do not compare
  renders, render DXFs, tune X3, or claim AutoCAD equivalence.

Boundary:

- Documentation only.
- No CLI behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Source Boundary Passthrough

Status: implemented in this branch.

Purpose:

- Preserve the source `artifact_index.json` boundary inside route payloads.
- Let CI and reviewers inspect both boundaries from one route report:
  - the route report's own read-only/no-equivalence boundary;
  - the underlying artifact index boundary, such as whether that artifact
    actually compared renders.

Changes:

- `acad_artifact_route.py` single-route JSON now includes
  `artifact_index_boundary` copied from the source artifact index when present.
- Multi-route payloads preserve `artifact_index_boundary` on each child route.
- Text output prints `source_artifact_boundary` when the source index has a
  boundary object.
- Markdown route sections print:
  - `source_compares_renders`
  - `source_autocad_equivalence_claim`

Boundary:

- Route/report metadata only.
- No routing-rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Source Boundary Gate

Status: implemented in this branch.

Purpose:

- Let CI assert source artifact-index boundaries directly from
  `acad_artifact_route.py`.
- Fail closed when an artifact index is missing the expected boundary or carries
  an unexpected value.

Changes:

- `acad_artifact_route.py` now accepts repeatable
  `--require-source-boundary key=value`.
- The check applies to the routed source artifact boundary:
  - single route: the one source `artifact_index.json`;
  - multi-route/recursive: every child route.
- Missing boundary keys fail with exit code `2`; mismatched values also fail
  with exit code `2`.
- `tools/render_regression/README.md` documents the CI guard pattern.

Example:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-source-boundary autocad_equivalence_claim=false
```

Boundary:

- Route assertion only.
- No routing-rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

Private compatibility smoke:

```bash
python3 tools/render_regression/acad_reference_request_run.py \
  --from-request /private/tmp/vemcad-autocad-batch-current-rerun-20260629-request/compare/reference_request.json \
  --candidate-cases /private/tmp/vemcad-autocad-batch-current/input/candidate_cases.json \
  --reference-dir /private/tmp/vemcad-provenance-compat-smoke-20260629/returned \
  --case-id G11 \
  --out-dir /private/tmp/vemcad-run-artifact-index-smoke-20260629
# AutoCAD reference request run: viewspace_mismatch
# artifact_index.schema=vemcad.acad_reference_request_run_artifact_index/v1
# artifact_index.count=10
```

## Follow-Up Route Action Domains

Status: implemented in this branch.

Purpose:

- Make route outputs classify the recommended action by machine-readable domain.
- Let unattended scripts distinguish input/recapture work from renderer-candidate
  work without parsing action-code strings.
- Keep the "no guessing" boundary explicit: a `viewspace_mismatch` route is an
  `input` domain, not a renderer domain.

Changes:

- `recommended_next_action` now includes `domain` on single-route and
  multi-route payloads.
- Multi-route payloads include `recommended_action_domain_counts`.
- Text and Markdown reports print `recommended_action_domain` and, for batches,
  `recommended_action_domain_counts`.
- `acad_artifact_route.py` now accepts `--require-action-domain <domain>` and
  exits `2` when the top-level action domain differs from the expected domain.

Boundary:

- Route/report metadata and assertion only.
- No routing-rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Request-Run Action Domains

Status: implemented in this branch.

Purpose:

- Carry the same machine-readable action domain metadata at the request-run
  source, not only in the route wrapper.
- Let `run_summary.json`, `run_summary.md`, and the run-level
  `artifact_index.json` distinguish input/recapture gates from renderer work
  without re-routing or parsing action-code strings.

Changes:

- `acad_reference_request_run.py` now includes `domain` on
  `recommended_next_action`.
- Each `case_actions[]` row now includes `domain`.
- `run_summary.json` and `artifact_index.json` include
  `case_action_domain_counts`.
- `run_summary.md` and stdout print the recommended action domain and case
  action domain counts.

Boundary:

- Run-summary/reporting metadata only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up CLI Action Domain Logs

Status: implemented in this branch.

Purpose:

- Surface the route action domain in CLI logs, not only JSON/Markdown artifacts.
- Let CI logs and operator transcripts show whether the next action is an
  `input`, `renderer-candidate`, `pass-review`, or `continue` domain without
  opening artifact files.

Changes:

- `acad_reference_batch.py` prints `recommended next action domain` beside the
  route action code.
- `acad_manifest_compare.py` prints the same field beside the route action code.
- Existing stdout/stderr tests now assert the expected domains:
  `continue`, `input`, and `pass-review`.

Boundary:

- CLI log visibility only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_batch.py \
  tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Recommended Next Action

Status: implemented in this branch.

Purpose:

- Make unattended `acad_reference_request_run.py` outputs self-directing.
- Prevent operators from treating suspicious input or `viewspace_mismatch` as a
  renderer bug by default.

Changes:

- `run_summary.json` now includes `recommended_next_action`.
- `run_summary.md` prints the recommended action code and message near the top.
- The recommendation is derived only from already-recorded gate states:
  request validation, missing returned PNGs, returned-reference intake,
  matched-view compare status, and pass/fail status.

Decision order:

1. `fix-request-package` when request validation is blocked or unreadable.
2. `provide-returned-autocad-pngs` when returned PNGs are missing.
3. `inspect-returned-reference-warnings` when intake is `review`.
4. `recapture-autocad-or-provide-window` on `viewspace_mismatch`.
5. `review-x3-pass` on matched-view pass.
6. `inspect-compare-failure` on compare failures.

Boundary:

- Run-summary/reporting only.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- Does not change X3 semantics or AutoCAD-equivalence wording.
- Does not turn `viewspace_mismatch` into renderer work.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 5 passed

python3 -m pytest tools/render_regression/tests -q
# 101 passed
```
