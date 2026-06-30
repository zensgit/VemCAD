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
