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
- A wrong-sized returned PNG is now caught by returned-reference intake as
  `returned_png_size_mismatch`; the run stops before producing compare inputs.
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

## Follow-Up Returned PNG Expected Size Intake Gate

Status: implemented in this branch.

Purpose:

- Make returned-reference intake itself fail closed when a returned AutoCAD PNG
  does not match the request-declared expected size.
- Put actual returned PNG size and requested expected size in the same intake
  row, so operators do not need to infer the mismatch from manifest validation
  artifacts.

Changes:

- `acad_reference_batch.py` now carries `requested_expected_size` into
  `reference_intake.json` inspection rows.
- `reference_intake.md` now prints both actual `Size` and `Expected size`.
- A returned PNG whose actual size differs from the request-declared size now
  adds `error:returned_png_size_mismatch` and sets returned-reference intake to
  `status=blocked`.
- The `--from-request` run stops at returned-reference intake in that case,
  before writing `acad_manifest.json` / `candidate_cases.json`.

Boundary:

- Returned-reference input-chain preflight only.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Returned Reference Input Action

Status: implemented in this branch.

Purpose:

- Give returned-reference intake errors a specific operator action instead of
  falling through to generic run-summary inspection.
- Keep intake warnings (`review`) separate from intake errors (`blocked`): a
  warning asks for review, while an error asks the operator to fix the returned
  AutoCAD PNG input before matched-view comparison.

Changes:

- `acad_artifact_route.py` now maps batch `stage=reference_intake` /
  `status=blocked` to `fix-returned-reference-input`.
- `acad_reference_request_run.py` now maps `reference_intake_status=blocked`
  to the same top-level action.
- Per-case `case_actions[]` now use `fix-returned-reference-input` when an
  intake row has an error; warning-only rows still use
  `inspect-returned-reference-warnings`.
- The new action is in the `input` domain; warning review remains
  `input-review`.

Boundary:

- Operator routing/reporting only.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_artifact_route.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Returned Reference Action Priority

Status: implemented in this branch.

Purpose:

- Make multi-route top-level recommendations prioritize blocked returned
  AutoCAD PNG input before renderer-candidate work.
- Close the gap introduced by the new `fix-returned-reference-input` action:
  single-route and request-run actions were correct, but recursive/multi-index
  routing still used the default low priority for the new action code.

Changes:

- `_ACTION_PRIORITY` now includes `fix-returned-reference-input` between
  missing returned PNGs and returned-reference warning review.
- Existing relative order is preserved after that insertion:
  request package fix > missing PNGs > returned PNG input error > intake review
  > renderer candidate > recapture.
- Added a regression where a renderer-candidate compare route appears before a
  blocked reference-intake route; the top-level recommendation still selects
  `fix-returned-reference-input` and points to `reference_intake.md`.

Boundary:

- Operator route-priority fix only.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

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

## Follow-Up Blank Returned Reference Advisory

Status: implemented in this branch.

Purpose:

- Prevent a white, correctly sized, but blank returned AutoCAD PNG from passing
  intake quietly.
- Keep the finding as input-quality review, not renderer evidence.

Changes:

- `inspection.identity_advisory.returned_ink.status=blank` now adds a warning:
  `returned_reference_blank`.
- The warning moves returned-reference intake to `status=review`, which routes
  the one-command run to `inspect-returned-reference-warnings` before trusting
  any X3 conclusion.
- The candidate ink profile remains recorded for context, but this warning is
  specifically about the returned AutoCAD reference being unusable as
  ground-truth evidence.

Boundary:

- Returned-reference intake preflight only.
- Diagnostic warning, not an AutoCAD-equivalence gate.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 18 passed

python3 -m pytest tools/render_regression/tests -q
# 174 passed
```

## Follow-Up Route Kind Guards

Status: implemented in this branch.

Purpose:

- Let unattended route steps assert artifact topology directly.
- Catch incomplete recursive route inputs where a workflow accidentally uploads
  only input artifacts but omits compare or request-run artifact indexes.

Changes:

- `acad_artifact_route.py` adds repeatable `--require-kind <kind>`.
- `acad_artifact_route.py` adds repeatable `--forbid-kind <kind>`.
- Single-route payloads derive counts from their own `kind`.
- Batch-route payloads use aggregated `kind_counts`.
- Failure messages print current kind counts for operator diagnosis.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Route topology assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 62 passed

python3 -m pytest tools/render_regression/tests -q
# 174 passed
```

## Follow-Up Intake Identity Advisory Markdown

Status: implemented in this branch.

Purpose:

- Let operators see the returned-vs-candidate identity advisory directly in
  `reference_intake.md`.
- Avoid forcing a JSON lookup when a returned AutoCAD PNG is blank, the
  candidate render is blank, or the ink bbox aspect strongly diverges.

Changes:

- `acad_reference_batch.py` adds a compact Markdown field for
  `inspection.identity_advisory`:
  - advisory status;
  - returned ink status;
  - candidate ink status;
  - optional `aspect_delta`;
  - explicit `diagnostic-only` marker.
- The intake Markdown table gets a new `Identity advisory` column.
- `tools/render_regression/README.md` documents that the Markdown report now
  surfaces this diagnostic-only identity hint.

Boundary:

- Report visibility only.
- Diagnostic-only; not a pass/fail gate.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 18 passed

python3 -m pytest tools/render_regression/tests -q
# 174 passed
```

## Follow-Up Route Count Guard

Status: implemented in this branch.

Purpose:

- Let unattended route steps assert how many artifact indexes were actually
  routed.
- Catch incomplete or polluted recursive route inputs where the expected kinds
  may be present, but a shard is missing or an old artifact index was included.

Changes:

- `acad_artifact_route.py` adds `--require-route-count <n>`.
- Single-route payloads count as `1`.
- Batch-route payloads use their top-level `count`.
- Failure messages print the actual count plus current kind counts for
  operator diagnosis.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Route topology assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Action Count Guard

Status: implemented in this branch.

Purpose:

- Let unattended route steps assert the exact routed action distribution.
- Catch mixed batches where the top-level recommendation is correct, but a
  nested route or request-run case still contains an unexpected operator action.

Changes:

- `acad_artifact_route.py` adds repeatable
  `--require-action-count <code=count>`.
- Multi-route payloads use top-level `recommended_action_counts`.
- Request-run payloads use `case_action_counts`.
- Single-route payloads derive a count of `1` from the top-level action.
- Invalid count expectations fail closed with an actionable parse error.
- Failure messages print current action counts for operator diagnosis.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Route action-distribution assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Request-Run Route Distribution Summary

Status: implemented in this branch.

Purpose:

- Make `run_summary.json/md` a complete operator summary for request-run route
  topology and action distribution.
- Avoid requiring operators to open `route_summary.json` just to see whether
  the run routed the expected input, request-run, and compare artifact indexes.

Changes:

- `acad_reference_request_run.py` now copies route-level distribution fields
  into `run_summary.json` after generating the route summary:
  - `route_count`
  - `route_kind_counts`
  - `route_status_counts`
  - `route_recommended_action_counts`
  - `route_recommended_action_domain_counts`
- `run_summary.md` prints the same fields near the top-level recommendation.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Request-run report surfacing only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Reference Request Route Check

Status: implemented in this branch.

Purpose:

- Make generated `reference_request.md` handoffs include the next machine-route
  inspection command after returned AutoCAD PNGs are processed.
- Keep the handoff explicit that route inspection is still a boundary/evidence
  check, not an AutoCAD-equivalence claim.

Changes:

- `acad_manifest_compare.py` now appends an `acad_artifact_route.py` command to
  generated `reference_request.md` files.
- The command uses:
  - `<next-run-dir>` as the wrapper output directory;
  - `--recursive` to discover nested route artifacts;
  - `--text` for operator-readable logs;
  - `--require-source-boundary autocad_equivalence_claim=false` so stale or
    overclaiming artifacts fail closed.

Boundary:

- Generated handoff Markdown only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Status Guards

Status: implemented in this branch.

Purpose:

- Let unattended route steps assert status distribution directly, not only
  recommended actions or action domains.
- Make CI fail closed when a required status is absent or a forbidden status
  appears inside recursive/multi-index route output.

Changes:

- `acad_artifact_route.py` adds repeatable `--require-status <status>`.
- `acad_artifact_route.py` adds repeatable `--forbid-status <status>`.
- Single-route payloads derive counts from their own `status`.
- Batch-route payloads use aggregated `status_counts`.
- Failure messages print current status counts for operator diagnosis.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Route assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Issue Code Guards

Status: implemented in this branch.

Purpose:

- Let unattended route steps assert exact request/intake issue classes, not only
  action domains.
- Make CI fail closed when an expected input issue is absent or a forbidden
  input issue appears.

Changes:

- `acad_artifact_route.py` adds repeatable `--require-issue-code <code>`.
- `acad_artifact_route.py` adds repeatable `--forbid-issue-code <code>`.
- The guards inspect only routed request/intake issue-code counts:
  `reference_request_validation_issue_code_counts` and
  `reference_intake_issue_code_counts`.
- Failure messages print the current issue-code counts for operator diagnosis.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Route assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Blank Candidate Render Advisory

Status: implemented in this branch.

Purpose:

- Prevent a blank VemCAD candidate PNG from entering X3 as if it were a usable
  comparison input.
- Keep the finding as artifact/evidence review, not an automatic renderer
  defect claim.

Changes:

- `inspection.identity_advisory.candidate_ink.status=blank` now adds a warning:
  `candidate_render_blank`.
- The warning moves returned-reference intake to `status=review`, so the
  operator inspects the candidate render artifact before trusting any X3
  conclusion.
- This is symmetric with `returned_reference_blank`, but explicitly describes
  the candidate render artifact rather than the AutoCAD ground truth.

Boundary:

- Returned-reference intake preflight only.
- Diagnostic warning, not an AutoCAD-equivalence gate.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
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

## Follow-Up Compare Harness Stale Artifact Cleanup

Status: implemented in this branch.

Purpose:

- Prevent repeated `acad_manifest_compare.py` executions against the same
  `--out-dir` from carrying stale compare artifacts into a later dry-run or
  input-blocked run.
- Keep compare `artifact_index.json` and route evidence aligned with the
  current invocation rather than a previous matched-view comparison.

Bug reproduced:

- First run performs a real compare and writes `summary.tsv`, `contact_sheet`,
  overlays, and viewspace reports.
- Second run reuses the same `--out-dir` with `--dry-run`.
- Before this fix, stale compare artifacts remained on disk and `summary.tsv`
  could be reported in the new dry-run artifact index.

Changes:

- `acad_manifest_compare.py` now clears its own summary, route, request, contact
  sheet, overlay, viewspace, semantic, and text artifacts before each run.
- A regression test now proves a pass-to-dry-run rerun leaves only current
  dry-run/manifest artifacts and no stale case-level compare outputs.

Boundary:

- Compare harness artifact hygiene only.
- No renderer change.
- No X3 scoring change.
- No compare metric behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up Request-Run Action Artifact Resolution

Status: implemented in this branch.

Purpose:

- Make the one-command `acad_reference_request_run.py` wrapper match the
  batch/compare CLIs for handoff artifacts.
- Let CI logs, `run_summary.json/md`, and the run-level `artifact_index.json`
  point directly at the resolved recommended-action file and state whether it
  exists.
- Avoid the operator having to open `route_summary.json` just to resolve
  `compare/reference_request.md` or `input/missing_references.md`.

Changes:

- `acad_reference_request_run.py` now copies route-derived action artifact
  resolution into:
  - `recommended_next_action_artifact_resolved`;
  - `recommended_next_action_artifact_exists`.
- Those fields are printed in stdout when a recommended action has a handoff
  artifact.
- `run_summary.md` prints the resolved artifact path and existence flag.
- The run-level `artifact_index.json` carries the same fields for automation.
- Regression coverage pins both important paths:
  - `viewspace_mismatch` resolves to `compare/reference_request.md`;
  - missing returned AutoCAD PNGs resolve to `input/missing_references.md`.
- `tools/render_regression/README.md` documents that batch, compare, and
  request-run CLIs all print the artifact path, resolved path, and existence.

Boundary:

- Evidence/reporting only.
- No route priority change.
- No renderer change.
- No compare metric change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 10 passed
```

## Follow-Up Missing Reference Markdown Source SHA

Status: implemented in this branch.

Purpose:

- Keep the human-readable missing-reference handoff as self-contained as the
  JSON/TSV artifacts.
- Let an operator verify the source DXF identity directly from
  `missing_references.md` before exporting the requested AutoCAD PNG.
- Avoid forcing a Markdown-only handoff reader to open TSV/JSON just to inspect
  `source_dxf_sha256`.

Changes:

- `missing_references.md` now includes a `Source SHA256` table column.
- The value is sourced from the existing `source_dxf_sha256` already carried in
  `missing_references.json` and `missing_references.tsv`.
- Regression coverage asserts:
  - the Markdown header includes `Source SHA256`;
  - the expected hash appears in the normal missing-reference handoff;
  - table escaping still preserves shape after the new column.
- `tools/render_regression/README.md` now documents that Markdown also surfaces
  the source SHA column.

Boundary:

- Missing-input handoff evidence only.
- No JSON/TSV schema change.
- No route priority change.
- No renderer change.
- No compare metric change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 21 passed
```

## Follow-Up Request-Run Route Summary Stdout

Status: implemented in this branch.

Purpose:

- Align the one-command `acad_reference_request_run.py` wrapper with the batch
  and compare CLIs, which already print their route report path.
- Give CI logs a direct pointer to `<run-dir>/route_summary.md`, not only
  `<run-dir>/run_summary.md`.
- Make the route report discoverable even when uploaded artifacts are browsed
  from stdout alone.

Changes:

- `acad_reference_request_run.py` now prints
  `route summary  : <run-dir>/route_summary.md` after route counts and before
  the run summary path.
- Regression coverage asserts the stdout route-summary path for:
  - pass;
  - `viewspace_mismatch`;
  - missing returned AutoCAD PNG input-blocked runs.
- `tools/render_regression/README.md` documents the request-run route summary
  stdout behavior.

Boundary:

- Operator stdout/report discovery only.
- No JSON schema change.
- No route priority change.
- No renderer change.
- No compare metric change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 10 passed
```

## Follow-Up Request-Run Input-Review Fail Flag

Status: implemented in this branch.

Purpose:

- Let unattended request-run workflows fail closed on returned-reference intake
  warnings without changing the default soft-review behavior.
- Keep the existing semantics intact: returned-reference warnings still route
  to `inspect-returned-reference-warnings` / `input-review`, and operators can
  choose whether that review lane should be a hard process gate.
- Cover the subtle case where the matched-view compare itself passes, but the
  returned AutoCAD PNG still has intake warnings such as low resolution.

Changes:

- `acad_reference_request_run.py` now accepts `--fail-on-input-review`.
- Default behavior is unchanged: if the compare exits `0`, the wrapper exits
  `0` even when the recommended action is `input-review`.
- With `--fail-on-input-review`, the wrapper exits `2` when the final
  recommended action domain is `input-review` and the compare would otherwise
  have exited `0`.
- Regression coverage creates an intentionally low-resolution but otherwise
  matched returned/candidate pair:
  - the default run exits `0`, with `reference_intake_status=review`;
  - the flagged run exits `2`, with the same run summary and
    `recommended_next_action.domain=input-review`.
- `tools/render_regression/README.md` documents the flag as an opt-in
  unattended-job gate.

Boundary:

- Operator/CI fail-closed control only.
- No default behavior change.
- No renderer change.
- No compare metric change.
- No route priority change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Missing Reference Case Action Current AutoCAD Evidence

Status: implemented in this branch.

Purpose:

- Pin the one-command request-run `case_actions` output for the
  missing-returned-reference path.
- Ensure the top-level JSON/TSV/Markdown action rows preserve the
  current/rejected AutoCAD PNG SHA/size evidence while telling the operator to
  provide a fresh returned PNG.
- Keep the pre-export handoff and the run-level operator action table aligned:
  both surfaces identify the stale/rejected AutoCAD reference without requiring
  a reviewer to open nested JSON first.

Changes:

- `test_reference_request_run_stops_on_missing_reference` now includes a
  readable `current_acad_png` with matching SHA/size in the request package.
- The test asserts `run_summary.json`, `case_actions.tsv`, and
  `run_summary.md` all preserve the `current_acad_png_sha256`,
  `current_acad_png_size_bytes`, and compact `current_acad=` evidence on the
  `provide-returned-autocad-pngs` action.
- `tools/render_regression/README.md` clarifies that per-case action evidence
  is self-contained for missing-returned-reference handoffs as well as
  rejected-reference reuse failures.

Boundary:

- Test/documentation hardening only; the existing implementation already
  carried the evidence.
- No renderer change.
- No route priority change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 12 passed

python3 -m pytest tools/render_regression/tests -q
# 201 passed
```

## Follow-Up Request-Run Final Exit Provenance

Status: implemented in this branch.

Purpose:

- Make the `--fail-on-input-review` result explainable from uploaded artifacts,
  not only from the shell exit status.
- Avoid confusing unattended runs where `status=pass` and
  `recommended_next_action.domain=input-review` are correct, but the process
  exits `2` because the opt-in fail flag was enabled.

Changes:

- `run_summary.json`, the run-level `artifact_index.json`, and
  `run_summary.md` now include:
  - `fail_on_input_review`;
  - `final_exit_code`.
- `acad_reference_request_run.py` stdout prints both fields.
- Regression coverage asserts:
  - normal pass runs record `final_exit_code=0` and
    `fail_on_input_review=false`;
  - default input-review runs keep `final_exit_code=0`;
  - `--fail-on-input-review` input-review runs record `final_exit_code=2`.
- `tools/render_regression/README.md` documents that the uploaded summary
  artifacts explain the opt-in failure mode.

Boundary:

- Run provenance/reporting only.
- No renderer change.
- No compare metric change.
- No route priority change.
- No default behavior change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 11 passed
```

## Follow-Up Strict Current AutoCAD Sentinel Guards

Status: implemented in this branch.

Purpose:

- Make generated post-return strict route commands fail closed on the two
  current/rejected AutoCAD sentinel warnings, not only on the broader
  `input-review` action domain.
- Keep the handoff robust if future routing logic changes an action domain but
  the underlying request-validation issue code still identifies suspicious
  current AutoCAD evidence.

Changes:

- Generated `reference_request.md` route commands now include:
  - `--forbid-issue-code current_acad_png_missing`;
  - `--forbid-issue-code current_acad_matches_candidate_png`.
- The README strict route example now carries the same two issue-code guards
  and documents that generated strict commands include them by default.
- The request-run strict route helper in tests uses the same guards, keeping
  generated handoff and local regression coverage aligned.

Boundary:

- Generated operator command / route-guard hardening only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 24 passed
```

## Follow-Up Strict Pre-Capture Validation Failure

Status: implemented in this branch.

Purpose:

- Make generated pre-capture request-validation commands fail closed on
  warning-only input-review findings before an operator spends time exporting
  AutoCAD PNGs.
- Keep request-validation sentinel warnings such as missing or
  candidate-identical `current_acad_png` from being treated as a soft-green
  preflight in generated handoffs.

Changes:

- Generated `reference_request.md` validation commands now include
  `--fail-on-input-review`.
- The README validation example carries the same flag and documents that the
  generated pre-capture command fails on request-package warnings.
- Tests now assert both generated command blocks:
  - pre-capture validation carries `--fail-on-input-review`;
  - post-return request-run still carries `--fail-on-input-review`.

Boundary:

- Generated operator command / documentation hardening only.
- The underlying `acad_reference_batch.py --validate-request` default remains a
  soft review unless the flag is passed.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_batch.py -q
# 41 passed
```

## Follow-Up Validate-Request Input-Review Regression

Status: implemented in this branch.

Purpose:

- Directly prove that `acad_reference_batch.py --validate-request
  --fail-on-input-review` exits `2` when request validation produces a
  warning-only input-review finding.
- Guard the generated strict pre-capture command added above against future
  regressions in `_batch_final_exit_code` or validation artifact metadata.

Changes:

- `test_batch_generator_warns_when_current_acad_png_is_declared_but_missing`
  now runs the same warning-only request package twice:
  - default validation remains soft-review and exits `0`;
  - flagged validation exits `2`.
- The regression asserts the flagged `artifact_index.json` records:
  - `status=review`;
  - `final_exit_code=2`;
  - `fail_on_input_review=true`;
  - `current_acad_png_missing=1`.

Boundary:

- Test/evidence hardening only.
- No command default behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 29 passed
```

## Follow-Up Strict Route Status Distribution Guard

Status: implemented in this branch.

Purpose:

- Let route checks assert an exact routed status distribution, not only require
  or forbid known status names.
- Make generated post-return strict route commands prove the expected successful
  three-artifact shape: input-prep, compare, and request-run all at
  `status=pass`.
- Catch future unknown or renamed status values that would not be covered by
  the existing forbid list.

Changes:

- `acad_artifact_route.py` adds repeatable
  `--require-status-count <status=count>`.
- Generated `reference_request.md` strict route commands now include
  `--require-status-count pass=3`.
- The README strict route example and status-guard documentation describe the
  exact `pass=3` requirement.
- Regression coverage proves:
  - `--require-status-count pass=3` succeeds for three routed pass artifacts;
  - a `pass=1, review=1` route fails with a status-count mismatch;
  - generated handoff Markdown and the request-run strict helper carry the
    same status-count guard.

Boundary:

- Route assertion / generated operator command hardening only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_artifact_route.py \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 102 passed
```

## Follow-Up Strict Route Action Distribution Guard

Status: implemented in this branch.

Purpose:

- Make generated post-return strict route commands prove the expected action
  code distribution, not only action-domain and status distributions.
- Catch future route drift where an action remains in the `continue` or
  `pass-review` domain but no longer represents the known strict handoff shape.

Changes:

- Generated `reference_request.md` strict route commands now include:
  - `--require-action-count continue-to-request-run=1`;
  - `--require-action-count review-x3-pass=2`.
- The README strict route example and action-count documentation describe that
  the expected shape is one input-prep continuation plus compare/request-run
  pass-review actions.
- The request-run strict route helper in tests uses the same action-count
  requirements.

Boundary:

- Generated operator command / route-action assertion hardening only.
- `review-x3-pass` remains a review action, not an AutoCAD-equivalence claim.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 25 passed
```

## Follow-Up Strict Final-Exit-Code Guard

Status: implemented in this branch.

Purpose:

- Make generated post-return strict route commands explicitly reject opt-in
  hard-failure exit codes in addition to requiring the expected zero-exit-code
  distribution.
- Prevent an input-review hard failure (`final_exit_code=2`) from being mixed
  into a supposedly ready matched-view pass bundle.

Changes:

- Generated `reference_request.md` strict route commands now include
  `--forbid-final-exit-code 2` beside the existing
  `--require-final-exit-code-count 0=2`.
- The README strict route example and final-exit-code guard documentation now
  describe this ready-bundle invariant.
- The request-run strict route helper in tests carries the same forbid guard.

Boundary:

- Generated operator command / final-exit-code assertion hardening only.
- No command default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 25 passed
```

## Follow-Up Strict Artifact-Kind Distribution Guard

Status: implemented in this branch.

Purpose:

- Let route checks assert exact handoff artifact-kind counts, not only artifact
  kind presence.
- Make generated post-return strict route commands fail closed on stale,
  duplicated, or incomplete operator artifact bundles.

Changes:

- `acad_artifact_route.py` adds repeatable
  `--require-artifact-kind-count <kind=count>`.
- Generated `reference_request.md` strict route commands now require:
  - `reference_request_validation_tsv=2`;
  - `reference_intake_tsv=2`;
  - `case_actions_tsv=1`;
  - `summary_tsv=1`.
- The counts match the existing strict handoff surface:
  input batch and wrapper both surface validation/intake TSVs, while
  case-actions and compare summary TSVs appear once.
- README and strict helper tests now carry the same exact artifact-kind
  distribution.

Boundary:

- Route assertion / generated operator command hardening only.
- No artifact schema change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_artifact_route.py \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 104 passed
```

## Follow-Up Strict Compare Distribution Guard

Status: implemented in this branch.

Purpose:

- Make generated post-return strict route commands positively require the
  matched-view compare distribution, not only forbid known bad compare buckets.
- Ensure the strict handoff proves the compare route has:
  - triage bucket `matched-pass=1`;
  - viewspace status `match=1`;
  - X3 band `pass=1`.

Changes:

- Generated `reference_request.md` strict route commands now include:
  - `--require-triage-bucket matched-pass=1`;
  - `--require-viewspace-status match=1`;
  - `--require-x3-band pass=1`.
- The README strict route example and compare-distribution guard section now
  describe the positive requirements alongside the existing mismatch /
  review / fallback forbids.
- The request-run strict route helper in tests uses the same positive compare
  distribution requirements.

Boundary:

- Generated operator command / compare-distribution assertion hardening only.
- Matched-view X3 pass artifacts still require human review before any
  AutoCAD-equivalence wording.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 25 passed
```

## Follow-Up Strict Action-Domain Distribution Guard

Status: implemented in this branch.

Purpose:

- Make generated post-return strict route commands prove the expected successful
  action-domain distribution, rather than only forbidding known bad domains.
- Catch future route-domain drift where a new or renamed action domain is not
  explicitly listed in the forbid set.

Changes:

- Generated `reference_request.md` route commands now include:
  - `--require-action-domain-count continue=1`;
  - `--require-action-domain-count pass-review=2`.
- The required distribution describes the strict matched-view handoff shape:
  input preparation continues to the request run, while the compare and wrapper
  routes are matched-view pass artifacts that still require human review before
  AutoCAD-equivalence wording.
- The README strict route example and action-domain-count documentation now
  record the same distribution.
- The request-run strict route helper in tests uses the same requirements, so
  generated handoffs and local regression coverage stay aligned.

Boundary:

- Generated operator command / route-domain assertion hardening only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 24 passed
```

## Follow-Up Strict Route Status Guards

Status: implemented in this branch.

Purpose:

- Make generated post-return strict route commands fail closed on routed
  artifact statuses as well as action domains, issue codes, viewspace status,
  and X3 bands.
- Catch mixed or malformed route bundles where a nested route is still
  `blocked`, `review`, or `viewspace_mismatch` even if another assertion surface
  looks acceptable.

Changes:

- Generated `reference_request.md` route commands now include:
  - `--forbid-status blocked`;
  - `--forbid-status review`;
  - `--forbid-status viewspace_mismatch`.
- The README strict route example and status-guard documentation now state that
  generated strict commands forbid those statuses by default.
- The request-run strict route helper in tests uses the same status guards, so
  local regression coverage matches generated operator handoffs.

Boundary:

- Generated operator command / route-status assertion hardening only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 24 passed
```

## Follow-Up Request Validation Review Routing

Status: implemented in this branch.

Purpose:

- Prevent warning-only request-validation issues from being hidden behind a
  top-level `review-x3-pass` recommendation when the matched-view compare
  itself passes.
- Treat request-package warnings like returned-reference intake warnings:
  visible by default as `input-review`, and optionally hard-failing with
  `--fail-on-input-review`.

Changes:

- `acad_reference_request_run.py` now recommends
  `inspect-request-package-warnings` when request validation is in `review` or
  has warnings but no errors.
- Warning-only request-validation case actions now use
  `inspect-request-package-warnings` instead of the harder
  `fix-request-package`; error cases still use `fix-request-package`.
- `acad_artifact_route.py` classifies the new action as `input-review` and
  ranks it with returned-reference warning review.
- `test_reference_request_run_surfaces_request_validation_review_warnings`
  proves a `current_acad_png_missing` warning remains visible in the top-level
  recommendation and can become exit `2` with `--fail-on-input-review`.
- The README documents that request-validation warnings are also covered by
  the input-review lane.

Boundary:

- Operator routing/reporting hardening only.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 13 passed

python3 -m pytest tools/render_regression/tests -q
# 206 passed
```

## Follow-Up Missing Current AutoCAD Warning Route Guard

Status: implemented in this branch.

Purpose:

- Prove the existing route-level issue-code guard can fail closed on
  `current_acad_png_missing`.
- Give strict CI jobs a direct guard for rejecting request packages whose
  declared rejected-reference PNG cannot be read.

Changes:

- `test_cli_forbid_missing_current_acad_warning` asserts
  `acad_artifact_route.py --forbid-issue-code current_acad_png_missing` exits
  `2` and reports the exact issue count when the warning appears in routed
  request-validation counts.
- The README documents the strict guard example beside
  `current_acad_matches_candidate_png`.

Boundary:

- Guard coverage/documentation only; `--forbid-issue-code` already existed.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 75 passed

python3 -m pytest tools/render_regression/tests -q
# 205 passed
```

## Follow-Up Missing Current AutoCAD Path Warning

Status: implemented in this branch.

Purpose:

- Prevent a declared `current_acad_png` path from silently weakening the
  rejected-reference sentinel when the file is missing or unreadable.
- Keep the signal at warning severity because `current_acad_png` is optional;
  the warning tells operators the declared rejected-reference provenance could
  not actually be checked.

Changes:

- Request validation now emits `warning:current_acad_png_missing` when
  `current_acad_png` is present in the request package but the resolved file is
  not readable.
- `test_batch_generator_warns_when_current_acad_png_is_declared_but_missing`
  covers the JSON, Markdown, TSV, and artifact-index surfaces.
- The README documents the warning and its rejected-reference-sentinel
  boundary.

Boundary:

- Request-validation hardening only.
- Warning severity; no new hard block.
- No renderer change.
- No route priority change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 29 passed

python3 -m pytest tools/render_regression/tests -q
# 204 passed
```

## Follow-Up Current AutoCAD Candidate Warning Route Guard

Status: implemented in this branch.

Purpose:

- Prove the existing route-level issue-code guard can fail closed on the new
  `current_acad_matches_candidate_png` request-validation warning.
- Give CI jobs a direct guard form for rejecting request packages that appear
  to bind the VemCAD candidate PNG as the current/rejected AutoCAD reference.

Changes:

- `test_cli_forbid_current_acad_candidate_identity_warning` asserts
  `acad_artifact_route.py --forbid-issue-code
  current_acad_matches_candidate_png` exits `2` and reports the exact issue
  count when that warning appears in routed request-validation counts.
- The README documents the strict guard example.

Boundary:

- Guard coverage/documentation only; `--forbid-issue-code` already existed.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 74 passed

python3 -m pytest tools/render_regression/tests -q
# 203 passed
```

## Follow-Up Current AutoCAD Candidate Identity Warning

Status: implemented in this branch.

Purpose:

- Add a low-noise wrong-file signal to request validation before any returned
  AutoCAD PNG exists.
- Warn when the current/rejected AutoCAD PNG is byte-identical to the VemCAD
  candidate PNG, because that usually means the request package bound the
  candidate render as the AutoCAD reference.
- Keep the signal at warning severity: it is operator evidence for suspicious
  input provenance, not an AutoCAD-equivalence gate.

Changes:

- Request validation now emits
  `warning:current_acad_matches_candidate_png` when readable
  `current_acad_png` provenance and candidate PNG provenance have the same
  SHA256.
- `test_batch_generator_warns_when_current_acad_matches_candidate_png` covers
  the JSON, Markdown, TSV, and artifact-index surfaces.
- The README documents the warning and its non-equivalence boundary.

Boundary:

- Request-validation hardening only.
- No renderer change.
- No route priority change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 28 passed

python3 -m pytest tools/render_regression/tests -q
# 202 passed
```

## Follow-Up Route Case Action Evidence Visibility

Status: implemented in this branch.

Purpose:

- Keep top-level route reports useful for operator triage when the routed
  artifact is a one-command request run.
- Surface per-case action evidence, including compact `current_acad=...`
  provenance, directly in route text/Markdown instead of requiring a reviewer
  to open `run_summary.md` first.
- Preserve the existing route decisions and counts while making the human
  report carry the same evidence already present in route JSON.

Changes:

- `acad_artifact_route.py` now prints one `case_action:` line per request-run
  action in text output.
- Route Markdown now includes a per-route `Case Actions` table with action,
  domain, source, issue codes, evidence, and artifact.
- `test_routes_run_case_actions` now asserts that action evidence and artifacts
  are visible in both text and Markdown route reports.
- The README documents route-level case-action evidence visibility.

Boundary:

- Route-report visibility only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 73 passed

python3 -m pytest tools/render_regression/tests -q
# 201 passed
```

## Follow-Up Request Case Count Validation

Status: implemented in this branch.

Purpose:

- Prevent stale or hand-edited `reference_request.json` metadata from
  misstating the size of the recapture handoff.
- Keep `case_count`, when declared, tied to the full request `cases[]` list
  before any `--case-id` partial processing.

Changes:

- Request validation now reports:
  - `request_case_count_invalid` when `case_count` is present but not an integer.
  - `request_case_count_mismatch` when declared `case_count` differs from the
    full unfiltered `cases[]` length.
- The check runs before `--case-id` filtering, so validating one selected case
  from a larger request does not falsely fail.
- The README documents the case-count consistency check.

Boundary:

- Request-package validation only.
- Missing `case_count` remains allowed for older/manual request packages.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 26 passed
```

## Follow-Up Case Action Current AutoCAD Evidence

Status: implemented in this branch.

Purpose:

- Carry the newly validated `current_acad_png` provenance into the final
  one-command `case_actions[]` / `case_actions.tsv` surface.
- Make rejected-reference reuse failures self-contained in the top-level
  operator table: the row now shows both the rejected/current AutoCAD PNG SHA and
  the returned PNG SHA.

Changes:

- `case_actions[]` evidence now includes optional:
  - `current_acad_png_sha256`
  - `current_acad_png_size_bytes`
- `case_actions.tsv` adds `current_acad_png_sha256` and
  `current_acad_png_size_bytes` columns.
- Compact `evidence` strings now include `current_acad=<sha:size>` when
  available.
- `run_summary.md` receives the same compact evidence through its Case Actions
  table.
- The README documents that case actions carry current/rejected AutoCAD
  provenance when available.

Boundary:

- Operator evidence/reporting only.
- No request/intake validation rule change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 12 passed
```

## Follow-Up Current AutoCAD Provenance Validation

Status: implemented in this branch.

Purpose:

- Protect the rejected-reference reuse guard from hand-edited or stale request
  packages.
- When a recapture request includes a readable `current_acad_png` path, verify
  its declared `current_acad_png_sha256` / `current_acad_png_size_bytes` before
  AutoCAD fulfilment.

Changes:

- `reference_request_validation.json` rows now include optional
  `current_acad_png` and `current_acad_png_provenance`.
- `reference_request_validation.tsv` adds current AutoCAD path/SHA/size columns.
- `reference_request_validation.md` adds current AutoCAD path/provenance
  columns.
- Validation reports `current_acad_png_sha256_mismatch` and
  `current_acad_png_size_mismatch` when a readable current AutoCAD PNG disagrees
  with its declared provenance.
- The README documents that this strengthens the rejected-reference reuse guard.

Boundary:

- Request-package validation only.
- `current_acad_png` remains optional; the hash alone can still serve as the
  returned-reference reuse sentinel.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 24 passed
```

## Follow-Up Missing Reference Current AutoCAD Evidence

Status: implemented in this branch.

Purpose:

- Make `missing_references.*` handoffs carry the rejected/current AutoCAD PNG
  sentinel when a recapture request has one.
- Let the pre-export spreadsheet/Markdown handoff show not only the source DXF
  SHA but also the old AutoCAD PNG SHA that must not be returned unchanged.

Changes:

- `missing_references.json` rows now include:
  - `current_acad_png`
  - `current_acad_png_sha256`
  - `current_acad_png_size_bytes`
- `missing_references.tsv` adds matching current AutoCAD columns.
- `missing_references.md` adds `Current AutoCAD` and
  `Current AutoCAD SHA256` columns.
- The README documents the new rejected-reference sentinel in missing-reference
  handoffs.

Boundary:

- Operator handoff evidence only.
- No request/intake validation rule change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 27 passed
```

## Follow-Up Rejected Reference Reuse Guard

Status: implemented in this branch.

Purpose:

- Prevent a recapture loop from accidentally reusing the exact AutoCAD PNG that
  was already rejected as `viewspace_mismatch`.
- Make the generated recapture request carry enough provenance for the intake
  side to fail closed when the returned PNG is byte-identical to the rejected
  `current_acad_png`.

Changes:

- Generated `reference_request.json` recapture cases now include:
  - `current_acad_png_sha256`
  - `current_acad_png_size_bytes`
- Generated `reference_request.md` now shows the current rejected AutoCAD PNG
  SHA256 beside source and candidate provenance.
- Returned-reference intake now emits an error
  `returned_png_matches_rejected_reference` when the returned PNG SHA256 equals
  `current_acad_png_sha256`.
- The README documents the guard as a stale-reference reuse blocker.

Boundary:

- Input fail-closed guard only.
- This detects exact byte reuse of the rejected AutoCAD reference; it does not
  infer DXF-to-PNG content identity from a PNG.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_batch.py -q
# 34 passed
```

## Follow-Up Case Action Diagnostic Evidence

Status: implemented in this branch.

Purpose:

- Make the final one-command `case_actions[]` / `case_actions.tsv` rows
  self-contained enough for operator routing.
- Carry the file evidence already generated by request validation and
  returned-reference intake into the per-case action surface, so a reviewer can
  see which source DXF, candidate PNG, and returned AutoCAD PNG were involved
  without opening nested JSON artifacts.

Changes:

- `case_actions[]` rows now include diagnostic evidence fields when available:
  - `source_dxf_sha256` / `source_dxf_size_bytes`
  - `candidate_png_sha256` / `candidate_png_size_bytes`
  - `returned_png_sha256` / `returned_png_size_bytes`
  - `returned_png_size`
  - `identity_advisory`
  - compact `evidence`
- `case_actions.tsv` adds the same evidence columns before the artifact
  columns.
- `run_summary.md` Case Actions table adds a compact `Evidence` column.
- The README documents that this is file-provenance/operator evidence only.

Boundary:

- Operator evidence/reporting only.
- Diagnostic file identity surface only; this is not DXF-to-PNG content
  binding.
- No route priority change.
- No request/intake validation rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 11 passed
```

## Follow-Up Route Artifact-Kind Guards

Status: implemented in this branch.

Purpose:

- Let CI fail closed when a recursive route contains the expected route shapes
  but omits a required uploaded operator artifact.
- Distinguish route kinds (`batch`, `compare`, `request_run`) from the artifact
  kinds inside each routed `artifact_index.json`, such as
  `reference_request_validation_tsv`, `reference_intake_tsv`, and
  `missing_references_tsv`.
- Make the route JSON/text/Markdown summaries show artifact-kind counts so an
  operator can see whether the handoff files were actually present.

Changes:

- `acad_artifact_route.py` now records `artifact_kind_counts` on each route and
  aggregates them in batch-route summaries.
- Route text and Markdown reports surface the artifact-kind count distribution.
- The CLI adds `--require-artifact-kind` and `--forbid-artifact-kind`, which
  exit 2 when required handoff artifacts are missing or forbidden ones are
  present.
- Focused tests cover pass, missing-required, and forbidden-present cases.

Boundary:

- Route/operator evidence guard only.
- No route priority change.
- No request-run behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 73 passed

python3 -m pytest tools/render_regression/tests -q
# 195 passed
```

## Follow-Up Request-Run Route Artifact-Kind Summary

Status: implemented in this branch.

Purpose:

- Carry the new route-level artifact-kind evidence through the one-command
  request runner, not only the standalone route tool.
- Let `run_summary.json`, `run_summary.md`, the run-level
  `artifact_index.json`, routed request-run reports, and CI stdout show whether
  the expected operator artifacts actually travelled through the run.
- Avoid requiring an operator to open nested `route_summary.json` merely to see
  that `reference_request_validation_tsv`, `reference_intake_tsv`,
  `missing_references_tsv`, or compare-side artifacts were present.

Changes:

- `acad_reference_request_run.py` now copies
  `route_payload.artifact_kind_counts` into `route_artifact_kind_counts`.
- The run-level `artifact_index.json` stores that same distribution.
- `run_summary.md` and stdout print the route artifact-kind distribution.
- `acad_artifact_route.py` now preserves `route_artifact_kind_counts` when a
  request-run artifact index is routed again, and its text/Markdown reports
  display the nested distribution.
- Regression coverage proves a successful matched-view request run surfaces
  key artifact kinds across JSON, Markdown, stdout, and routed reports.

Boundary:

- Operator evidence/reporting only.
- No route priority change.
- No request-run action change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_request_run.py::test_reference_request_run_fulfills_and_compares_match \
  -q
# 1 passed

python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 73 passed

python3 -m pytest tools/render_regression/tests -q
# 195 passed
```

## Follow-Up Generated Route Command Artifact Guards

Status: implemented in this branch.

Purpose:

- Make the generated post-return `acad_artifact_route.py <next-run-dir>
  --recursive` command use the artifact-kind guards added in the previous
  slices.
- Fail closed if a run has the expected route topology but is missing the key
  uploaded handoff artifacts operators need for review.
- Keep the generated `reference_request.md` and README quick-start command in
  sync.

Changes:

- `acad_manifest_compare.py` now writes these guards into generated
  `reference_request.md`:
  - `--require-artifact-kind reference_request_validation_tsv`
  - `--require-artifact-kind reference_intake_tsv`
  - `--require-artifact-kind case_actions_tsv`
  - `--require-artifact-kind summary_tsv`
- `tools/render_regression/README.md` mirrors the same post-return route
  command.
- Regression coverage extracts both Markdown command blocks and asserts the
  four artifact-kind guards are present exactly once.

Boundary:

- Operator command hardening only.
- No route priority change.
- No request-run action change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 195 passed
```

## Follow-Up Strict Route Guard Execution Tests

Status: implemented in this branch.

Purpose:

- Prove the strict post-return route guard is not merely documented, but
  executable against real request-run outputs.
- Guard against over-tightening the generated command so that a clean
  matched-view pass can no longer satisfy it.
- Guard against under-tightening it so that a `viewspace_mismatch` run can pass
  the route guard because artifacts are present.

Changes:

- `test_acad_reference_request_run.py` now defines a strict post-return route
  argument helper matching the generated `reference_request.md` command.
- The clean matched-view pass test runs that guard and asserts exit `0`.
- The `viewspace_mismatch` test runs the same guard and asserts exit `2` with
  `forbidden action domain present: input=2`.

Boundary:

- Test/evidence hardening only.
- No generated command change in this slice.
- No route priority change.
- No request-run action change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 195 passed
```

## Follow-Up Generated Route Command Semantic Guards

Status: implemented in this branch.

Purpose:

- Keep the generated post-return route command from passing merely because exit
  codes and artifacts are success-shaped.
- Make the command also fail closed on routed semantic distributions that still
  require input recapture or renderer investigation.
- Prevent X3 `review`/`fallback` bands from being treated as a clean
  AutoCAD-parity result by unattended scripts.

Changes:

- `acad_manifest_compare.py` now writes these additional guards into generated
  `reference_request.md`:
  - `--forbid-action-domain input`
  - `--forbid-action-domain renderer-candidate`
  - `--forbid-viewspace-status mismatch`
  - `--forbid-x3-band review`
  - `--forbid-x3-band fallback`
- `tools/render_regression/README.md` mirrors the same quick-start route
  command.
- Regression coverage asserts the generated and documented command blocks carry
  those guards. The `input` assertion uses the exact line fragment so it cannot
  be satisfied accidentally by `input-review`.

Boundary:

- Operator command hardening only.
- No route priority change.
- No request-run action change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 195 passed
```

## Follow-Up Generated Route Command Final-Exit Guard

Status: implemented in this branch.

Purpose:

- Keep the generated post-return route command from passing solely because the
  route topology and uploaded artifacts exist.
- Require the routed final-exit distribution to be success-shaped before an
  unattended workflow interprets pixels or X3 output.
- Fail closed for `viewspace_mismatch`, input-review hard failures, compare
  failures, or any other request-run result where the one-command wrapper exits
  non-zero.

Changes:

- `acad_manifest_compare.py` now writes
  `--require-final-exit-code-count 0=2` into the generated post-return
  `acad_artifact_route.py <next-run-dir> --recursive` command.
- `tools/render_regression/README.md` mirrors the same guard in the quick-start
  route command.
- Regression coverage asserts the guard appears exactly once in generated
  `reference_request.md` and in the README command block.

Boundary:

- Operator command hardening only.
- No route priority change.
- No request-run action change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 195 passed
```

## Follow-Up Request-Run Input TSV Artifacts

Status: implemented in this branch.

Purpose:

- Keep the one-command AutoCAD reference request runner's top-level artifact
  surface aligned with the nested input artifacts.
- Let artifact-upload jobs collect request-validation, missing-reference, and
  returned-reference-intake TSVs from `run_summary.json/md` and the run-level
  artifact index without walking `input/`.

Changes:

- `acad_reference_request_run.py` now records
  `reference_request_validation_tsv` and `reference_intake_tsv` in
  `run_summary.json` when those nested files exist.
- `run_summary.md` lists `request validation tsv` and `reference intake tsv`
  in the Artifacts section.
- The wrapper-level `artifact_index.json` includes
  `reference_request_validation_tsv` and `reference_intake_tsv` artifacts.
- Existing recommended next actions still point at Markdown reports for human
  handoff; this only expands the machine-readable artifact surface.
- The README documents that the wrapper surfaces all three input TSVs:
  request validation, missing references, and reference intake.

Boundary:

- Run-level artifact surfacing only.
- No route priority change.
- No recommended-action target change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Reference Intake Markdown Provenance

Status: implemented in this branch.

Purpose:

- Let human reviewers confirm the exact returned AutoCAD PNG identity from
  `reference_intake.md` without opening `reference_intake.json` or the sibling
  TSV.
- Keep the human intake report aligned with the machine-readable
  `reference_intake.tsv` provenance surface.

Changes:

- `reference_intake.md` now adds a `Returned provenance` table column.
- Each returned provenance cell prints `sha256=<digest> size=<bytes>` when the
  returned PNG was readable and inspected.
- The Markdown table escaping test was updated for the extra column.
- The README documents that intake Markdown shows returned PNG provenance.

Boundary:

- Returned-reference intake Markdown evidence surface only.
- No intake rule change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 22 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Request Validation TSV

Status: implemented in this branch.

Purpose:

- Make request-package validation provenance machine-readable in the same way
  the missing-reference handoff already has a TSV surface.
- Let unattended CI, handoff scripts, and spreadsheet review inspect the
  per-case source/candidate SHA256+size, requested capture contract, and
  issue codes without parsing Markdown.

Changes:

- `acad_reference_batch.py --validate-request` and `--from-request` now write
  `reference_request_validation.tsv` beside
  `reference_request_validation.json/md`.
- The TSV has one row per request case and records:
  - case id / drawing id / recommended output name;
  - requested capture method / view contract / expected size;
  - resolved source DXF path plus source SHA256 and size;
  - resolved candidate PNG path plus candidate SHA256 and size;
  - per-case `severity:issue_code` values.
- Batch artifact indexes include `reference_request_validation_tsv`.
- `_clear_batch_outputs()` removes stale `reference_request_validation.tsv`.
- `reference_request_validation.md` now points at the sibling TSV.
- The README documents the TSV as the machine-readable companion to the
  request-validation Markdown provenance table.

Boundary:

- Request-validation evidence surface only.
- No request validation rule change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 22 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Reference Intake TSV

Status: implemented in this branch.

Purpose:

- Make returned AutoCAD PNG intake preflight evidence machine-readable.
- Let unattended CI, fail-closed review jobs, and spreadsheet handoff inspect
  actual/requested size, returned PNG provenance, capture-quality warnings, and
  identity-advisory hints without parsing `reference_intake.md`.

Changes:

- `acad_reference_batch.py --from-request` now writes
  `reference_intake.tsv` beside `reference_intake.json/md` whenever returned
  reference intake runs.
- The TSV has one row per returned reference and records:
  - case id / drawing id / recommended output name;
  - returned PNG path, width, height, requested expected size, long edge, mode,
    alpha flag, and corner white ratio;
  - returned PNG SHA256 and file size;
  - compact diagnostic-only identity advisory text;
  - per-case `severity:issue_code` values.
- Batch artifact indexes include `reference_intake_tsv`.
- `_clear_batch_outputs()` removes stale `reference_intake.tsv`.
- `reference_intake.md` now points at the sibling TSV.
- The README documents the TSV as the machine-readable companion to the intake
  Markdown preflight table.

Boundary:

- Returned-reference intake evidence surface only.
- No intake rule change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 22 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Route Case Action Issue-Code Counts

Status: implemented in this branch.

Purpose:

- Surface the new per-case `case_actions[].issue_codes` through
  `acad_artifact_route.py`, so CI route reports and recursive artifact routing
  can show the exact defect classes without opening `run_summary.json`.
- Keep this as a reporting-only route aggregation; it does not change the
  recommended action or route priority.

Changes:

- Request-run routes now compute `case_action_issue_code_counts` from
  `case_actions[].issue_codes`.
- Recursive/multi-artifact route summaries aggregate
  `case_action_issue_code_counts` across nested request-run routes.
- Route text and Markdown reports print the new counts.
- The README documents that route reports surface request/intake/case-action
  issue-code counts.

Boundary:

- Route evidence/reporting only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 70 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Request Validation Provenance Markdown

Status: implemented in this branch.

Purpose:

- Make request-package validation Markdown show the exact source DXF and
  candidate PNG provenance that was checked.
- Let reviewers confirm the bound file identities from the human-readable
  validation artifact instead of opening `reference_request_validation.json`.

Changes:

- `reference_request_validation.md` now adds `Source provenance` and
  `Candidate provenance` columns.
- Each provenance cell prints `sha256=<digest> size=<bytes>` when the file is
  present and validated.
- The README documents that request validation Markdown surfaces this
  provenance beside the resolved file paths.

Boundary:

- Request-validation evidence surface only.
- No request validation rule change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 22 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Batch Input-Review Fail Flag

Status: implemented in this branch.

Purpose:

- Give the standalone `acad_reference_batch.py --from-request` path the same
  opt-in fail-closed control as the one-command request runner.
- Keep default behavior unchanged: returned-reference intake warnings remain a
  soft `review` lane and the batch command exits `0` when manifest generation
  succeeds.
- Let CI jobs that stop at batch/intake artifacts fail closed on returned PNG
  quality or identity warnings without needing to invoke the wrapper or a
  separate route command.

Changes:

- `acad_reference_batch.py` now accepts `--fail-on-input-review`.
- When returned-reference intake status is `review`, the default final exit
  remains `0`; with the flag, the command returns `2`.
- The batch `artifact_index.json` records:
  - `fail_on_input_review`;
  - `final_exit_code`.
- Regression coverage creates a low-resolution but otherwise valid returned
  AutoCAD PNG path:
  - default batch behavior remains soft-review;
  - flagged batch behavior exits `2`;
  - `acad_manifest.json` and `candidate_cases.json` are still written, so the
    failure is an operator/CI gate, not a data-loss path.
- `tools/render_regression/README.md` documents that the lower-level batch path
  supports the same flag and artifact provenance as request-run.

Boundary:

- Standalone batch operator/CI fail-closed control only.
- No default behavior change.
- No renderer change.
- No compare metric change.
- No route priority change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# 22 passed
```

## Follow-Up Per-Case Action Artifact Resolution

Status: implemented in this branch.

Purpose:

- Make `case_actions` useful as a standalone batch triage table.
- Let operators sort/filter per-case actions and still copy a resolved handoff
  file path without opening route reports or resolving relative paths by hand.
- Keep the top-level recommended-action artifact resolution and per-case
  action rows aligned.

Changes:

- Each `case_actions[]` row now includes `artifact_resolved` and
  `artifact_exists` when the action has a handoff artifact.
- `case_actions.tsv` adds `artifact_resolved` and `artifact_exists` columns.
- The `run_summary.md` case-action table displays the resolved artifact path
  when available.
- Regression coverage pins:
  - pass-review / matched-pass rows resolve to `compare/summary.md`;
  - recapture rows resolve to `compare/reference_request.md`;
  - missing-reference rows resolve to `input/missing_references.md`.
- `tools/render_regression/README.md` documents the per-case resolved artifact
  fields.

Boundary:

- Per-case operator evidence only.
- No route priority change.
- No renderer change.
- No compare metric change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 10 passed
```

## Follow-Up Recapture Route Action Artifact

Status: implemented in this branch.

Purpose:

- Make `acad_artifact_route.py` point the recapture recommendation at the
  generated operator handoff file instead of only saying that a recapture is
  required.
- Keep recursive route summaries useful for unattended runs: the top-level
  `recommended_next_action.artifact` can now resolve to `reference_request.md`
  when compare output has generated one.

Changes:

- Compare routes with `triage_bucket_counts.recapture-required > 0` now set
  `recommended_next_action.artifact` to the `reference_request_markdown`
  artifact path when present.
- Route JSON/text/Markdown already resolve and print action artifacts; this
  change makes the recapture lane use that existing mechanism.
- End-to-end compare regression now asserts `route_summary.json` points at
  `reference_request.md` and reports `action_artifact_exists=true`.
- Route-only regression now asserts an isolated compare `artifact_index.json`
  with a `reference_request_markdown` artifact routes to that file.
- `tools/render_regression/README.md` documents the recapture action artifact
  behavior.

Boundary:

- Operator routing/reporting only.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.
- No generated request JSON schema/content change.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_artifact_route.py -q
# 72 passed
```

## Follow-Up Recommended Action Artifact Stdout

Status: implemented in this branch.

Purpose:

- Make CI/stdout logs show the concrete recommended handoff artifact instead
  of requiring operators to open route JSON/Markdown first.
- Align the one-command request runner's recapture top-level action with the
  generated recapture request, not just the compare summary.

Changes:

- `acad_manifest_compare.py` route stdout now prints the recommended action
  artifact, resolved artifact path, and whether the artifact exists when the
  route provides one.
- `acad_reference_batch.py` route stdout/stderr now prints the same artifact
  details for input-prep routes such as missing returned AutoCAD PNGs.
- `acad_reference_request_run.py` now prefers `compare/reference_request.md`
  as the top-level `recapture-autocad-or-provide-window` action artifact when
  that file exists, falling back to `compare/summary.md` only when no generated
  request exists.
- The one-command runner stdout now prints
  `recommended next action artifact` when the selected action has one.
- `tools/render_regression/README.md` documents the action-artifact stdout
  behavior.

Boundary:

- Operator logging/reporting only.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.
- No generated request JSON schema/content change.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_reference_batch.py \
  tools/render_regression/tests/test_acad_reference_request_run.py -q
# 39 passed
```

## Follow-Up Per-Case Recapture Action Artifact

Status: implemented in this branch.

Purpose:

- Align the one-command runner's per-case action table with the top-level
  recapture handoff.
- Avoid sending operators from a specific recapture case back to
  `compare/summary.md` when the concrete `compare/reference_request.md` handoff
  exists.

Changes:

- `acad_reference_request_run.py` now uses `compare/reference_request.md` as
  the artifact for per-case `recapture-autocad-or-provide-window` actions when
  that file exists.
- Other compare-derived actions still point at `compare/summary.md`; for
  example, `review-x3-pass` rows keep the compare summary artifact.
- Regression coverage asserts the JSON `case_actions[]`, Markdown case-action
  table, and `case_actions.tsv` all carry the correct per-case artifacts.
- `tools/render_regression/README.md` documents the per-case artifact behavior.

Boundary:

- Operator routing/reporting only.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.
- No generated request JSON schema/content change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 10 passed
```

## Follow-Up Run-Level Compare Reference Request Artifacts

Status: implemented in this branch.

Purpose:

- Make the one-command request-run artifact index list the generated compare
  recapture request directly.
- Let automation discover `compare/reference_request.md` from the run-level
  artifact index and run summary, without first opening the nested compare
  artifact index.

Changes:

- `acad_reference_request_run.py` now records these fields in
  `run_summary.json` when they exist:
  - `compare_reference_request_json`
  - `compare_reference_request_markdown`
- The run-level `artifact_index.json` now includes
  `compare_reference_request_json` and
  `compare_reference_request_markdown` artifact entries when the compare phase
  generated a recapture request.
- `run_summary.md` now lists the same compare reference request artifacts in
  its `Artifacts` section.
- Pass/matched runs, which do not generate a recapture request, keep those
  artifact entries absent.
- `tools/render_regression/README.md` documents the run-level artifact
  discovery behavior.

Boundary:

- Operator artifact discovery/reporting only.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.
- No generated request JSON schema/content change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 10 passed
```

## Follow-Up Legacy Batch Compare Optional Report Cleanup

Status: implemented in this branch.

Purpose:

- Prevent `autocad_batch_compare.py` diagnostic reruns against the same
  `--out-dir` from carrying stale optional reports into a later simpler run.
- Keep legacy batch-comparison evidence from implying that semantic/tile
  diagnostics ran when the current invocation did not request them.

Bug reproduced:

- First run uses semantic masks and `--tile-grid`, writing
  `semantic_summary.*`, `semantic_tile_summary.*`, `tile_summary.*`, and
  `tile_heatmaps/`.
- Second run reuses the same `--out-dir` with plain cases and no tile grid.
- Before this fix, stale optional reports and heatmaps remained on disk.

Changes:

- `autocad_batch_compare.py` now clears known batch outputs and optional
  artifact directories before each run.
- A regression test now proves a semantic/tile run followed by a plain run
  leaves no stale semantic or tile reports.

Boundary:

- Legacy diagnostic artifact hygiene only.
- No renderer change.
- No X3 scoring change.
- No compare metric behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_autocad_batch_compare.py -q
# passed
```

## Follow-Up Request-Run Stale Compare Cleanup

Status: implemented in this branch.

Purpose:

- Prevent repeated `acad_reference_request_run.py` executions against the same
  `--out-dir` from carrying stale compare artifacts into a later
  input-blocked run.
- Keep operator route evidence current when a previously successful run is
  rerun after returned AutoCAD PNGs are removed or missing.

Bug reproduced:

- First run succeeds and writes `compare/summary.json`.
- Second run reuses the same `--out-dir` but is blocked before compare because
  a returned AutoCAD PNG is missing.
- Before this fix, `run_summary.json`, `artifact_index.json`, and
  `route_summary.json` could still reference the stale compare output and stale
  `review-x3-pass` action.

Changes:

- `acad_reference_request_run.py` now clears run-level artifacts and the stale
  `compare/` directory before each run.
- The wrapper deliberately leaves `input/` ownership with
  `acad_reference_batch.py`, which already clears and rewrites its own batch
  artifacts.
- A regression test now proves the second input-blocked run has:
  - no `compare_summary_json`, `compare_summary_markdown`, or
    `compare_artifact_index`;
  - no stale `review-x3-pass` case action;
  - route counts derived only from the current missing-reference state.

Boundary:

- Wrapper artifact hygiene only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed
```

## Follow-Up Reference Request Boundary Metadata

Status: implemented in this branch.

Purpose:

- Make `reference_request.json` self-describing when it is handed off outside
  the original compare output directory.
- Preserve the no-equivalence boundary before AutoCAD capture fulfilment, not
  only after validation/intake reports are generated.
- Keep the external-input gate explicit: a request asks for fresh matched-view
  AutoCAD PNGs; it does not render, compare, tune X3, or claim AutoCAD
  equivalence.

Changes:

- `acad_manifest_compare.py` now writes a top-level `boundary` object into
  generated `reference_request.json`:
  - `renders_dxf=false`
  - `compares_renders=false`
  - `changes_x3_scoring=false`
  - `changes_renderer=false`
  - `requires_returned_autocad_png=true`
  - `requires_viewspace_match=true`
  - `autocad_equivalence_claim=false`
- `acad_reference_batch.py --validate-request` now copies that source request
  boundary into `reference_request_validation.json` as
  `source_request_boundary`.
- The validation Markdown report prints `source_request_boundary` beside the
  issue counts, so operators can audit the source package before fulfilment.

Boundary:

- Metadata/reporting only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py tools/render_regression/tests/test_acad_reference_batch.py -q
# 22 passed
```

## Follow-Up Source Request Boundary Propagation

Status: implemented in this branch.

Purpose:

- Carry the `reference_request.json` boundary added in the previous slice beyond
  the validation JSON itself.
- Let artifact-index and route consumers see whether the original request asked
  for returned AutoCAD PNGs, required matched-view comparison, and explicitly
  made no AutoCAD-equivalence claim.
- Keep recursive route inspection useful even when operators only inspect the
  generated `artifact_index.json` / `route_summary.*` files.

Changes:

- Batch `artifact_index.json` now includes `source_request_boundary` when
  `reference_request_validation.json` recorded one.
- `acad_reference_request_run.py` propagates that boundary into
  `run_summary.json`, `run_summary.md`, and the run `artifact_index.json`.
- `acad_artifact_route.py` carries `source_request_boundary` through batch and
  request-run route payloads and prints it in text/Markdown route reports.

Boundary:

- Metadata/reporting only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py tools/render_regression/tests/test_acad_reference_request_run.py tools/render_regression/tests/test_acad_artifact_route.py -q
# passed
```

## Follow-Up Source Request Boundary Route Guard

Status: implemented in this branch.

Purpose:

- Let operators fail closed when a routed run no longer carries the source
  request boundary.
- Make generated reference-request handoff commands verify both:
  - source artifact boundary: no AutoCAD-equivalence claim;
  - source request boundary: returned AutoCAD PNGs and matched-view comparison
    are still required.
- Keep compare-only routes from failing the guard: they do not own the source
  request package, while batch/request-run routes do.

Changes:

- `acad_artifact_route.py` adds `--require-request-boundary key=value`.
- The guard checks every route that exposes `source_request_boundary` and
  fails if none expose it.
- Generated `reference_request.md` route-inspection commands now include:
  - `--require-request-boundary autocad_equivalence_claim=false`
  - `--require-request-boundary requires_returned_autocad_png=true`
  - `--require-request-boundary requires_viewspace_match=true`

Boundary:

- Route/report guard only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up Route Request Boundary README

Status: implemented in this branch.

Purpose:

- Make the operator-facing render-regression README match the route guard added
  in the previous slice.
- Document that `--require-request-boundary` checks only routes that expose
  `source_request_boundary`, ignores compare-only routes, and fails if no
  routed artifact exposes the request boundary.
- Provide the full fail-closed route assertion used by generated
  `reference_request.md` handoff commands.

Changes:

- `tools/render_regression/README.md` now documents:
  - `--require-request-boundary autocad_equivalence_claim=false`
  - `--require-request-boundary requires_returned_autocad_png=true`
  - `--require-request-boundary requires_viewspace_match=true`

Boundary:

- Documentation only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed
```

## Follow-Up Request Validation Boundary Guard

Status: implemented in this branch.

Purpose:

- Move the request-boundary fail-closed check earlier, before time is spent
  capturing AutoCAD PNGs.
- Keep old request packages readable by default, while allowing generated
  handoff commands to require the boundary explicitly.
- Make the validation report show clear `missing_request_boundary` /
  `request_boundary_mismatch` issue codes when the source request package no
  longer carries the no-equivalence / returned-PNG / matched-view contract.

Changes:

- `acad_reference_batch.py --validate-request` and `--from-request` now accept
  repeatable `--require-request-boundary key=value`.
- Generated `reference_request.md` adds the request-boundary guard to the
  "Before Capture Or Fulfilment" validation command.
- `tools/render_regression/README.md` documents the pre-capture validation
  command with the same guard.

Boundary:

- Input-package validation guard only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up Request Run Boundary Guard

Status: implemented in this branch.

Purpose:

- Let `acad_reference_request_run.py` fail closed on the same source request
  boundary before it fulfills returned PNGs or runs matched-view comparison.
- Keep direct wrapper usage aligned with the pre-capture validation command and
  generated route guard.

Changes:

- `acad_reference_request_run.py` now accepts repeatable
  `--require-request-boundary key=value` and forwards it to
  `acad_reference_batch.py`.
- Generated `reference_request.md` adds the request-boundary guard to the
  `acad_reference_request_run.py` command.
- `tools/render_regression/README.md` documents the same guarded wrapper
  command.

Boundary:

- Wrapper input validation only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up Boundary Guard Handoff Coverage

Status: implemented in this branch.

Purpose:

- Keep the operator README's unattended-flow example aligned with generated
  `reference_request.md`.
- Prevent generated handoff tests from passing when only one of the three
  commands carries the request-boundary guard.

Changes:

- `tools/render_regression/README.md` now shows the guarded
  `acad_artifact_route.py <run-dir> --recursive --text` command with:
  - `--require-source-boundary autocad_equivalence_claim=false`
  - `--require-request-boundary autocad_equivalence_claim=false`
  - `--require-request-boundary requires_returned_autocad_png=true`
  - `--require-request-boundary requires_viewspace_match=true`
- `test_acad_manifest_compare.py` now asserts each
  `--require-request-boundary` line appears three times: validate, run, and
  route.

Boundary:

- Documentation/test hardening only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up From-Request Boundary Guard Regression

Status: implemented in this branch.

Purpose:

- Pin the direct `acad_reference_batch.py --from-request` failure path when a
  request-boundary guard rejects the package.
- Prove fulfilment stops before manifest/intake generation, while still leaving
  request-validation artifacts and a route action for operators.

Changes:

- `test_acad_reference_batch.py` now covers:
  - `--from-request ... --require-request-boundary autocad_equivalence_claim=false`
    with a mismatched request boundary;
  - `reference_request_validation.json` status `blocked`;
  - batch `artifact_index.json` stage `request_validation`;
  - route action `fix-request-package`;
  - no `acad_manifest.json` or `reference_intake.json` generated.

Boundary:

- Test hardening only.
- No renderer change.
- No X3 scoring change.
- No compare behavior change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed
```

## Follow-Up Source Report Issue Code Counts

Status: implemented in this branch.

Purpose:

- Make the source request-validation and returned-reference intake reports
  summarize their issue classes directly.
- Let operators understand why a source report is `blocked` or `review`
  without scanning every per-case table row or opening route artifacts.

Changes:

- `reference_request_validation.json` now includes top-level
  `issue_code_counts`.
- `reference_request_validation.md` prints `issue_code_counts`.
- `reference_intake.json` now includes top-level `issue_code_counts`.
- `reference_intake.md` prints `issue_code_counts`.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Source report evidence only.
- No request validation semantics change.
- No intake warning/blocking semantics change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Batch Route Issue Code Counts

Status: implemented in this branch.

Purpose:

- Make batch/input-stage route reports carry the same concrete issue-code
  evidence as run-level route reports.
- Let CI jobs that stop at request validation, missing references, or returned
  PNG intake expose the exact request/intake issue classes without opening
  nested JSON artifacts.

Changes:

- `acad_reference_batch.py` now aggregates
  `reference_request_validation_issue_code_counts` from
  `reference_request_validation.json`.
- `acad_reference_batch.py` now aggregates
  `reference_intake_issue_code_counts` from `reference_intake.json`.
- `acad_artifact_route.py` now passes those counts through batch routes, so
  route JSON, text, and Markdown display them.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Batch artifact metadata and route-report evidence only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_batch.py \
  tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Batch Aggregate Issue Code Counts

Status: implemented in this branch.

Purpose:

- Make recursive/multi-index route summaries expose aggregate request/intake
  issue-code counts at the top level.
- Let CI jobs that upload a single route batch summary see the exact input
  issue classes without drilling into each nested route.

Changes:

- `acad_artifact_route.py` now sums
  `reference_request_validation_issue_code_counts` across nested routes.
- `acad_artifact_route.py` now sums `reference_intake_issue_code_counts`
  across nested routes.
- Batch route JSON, text, and Markdown summary output display those aggregate
  counts when present.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Route summary metadata only.
- No route priority change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Issue Code Counts

Status: implemented in this branch.

Purpose:

- Preserve request-validation and returned-reference intake issue-code counts
  when a run-level artifact index is routed through `acad_artifact_route.py`.
- Let CI jobs that upload only route reports still show why a request run is in
  input review.

Changes:

- Request-run route payloads now carry:
  - `reference_request_validation_issue_code_counts`
  - `reference_intake_issue_code_counts`
- Text and Markdown route reports print these fields when present.
- Tests cover JSON payload, text output, and Markdown output.

Boundary:

- Route-report evidence only.
- No route priority change.
- No input gate semantics change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Run Intake Issue Code Counts

Status: implemented in this branch.

Purpose:

- Make one-command run summaries explain why returned-reference intake is in
  `review`, without requiring the operator to open `input/reference_intake.*`
  first.
- Surface request-validation error codes in the same place for blocked input
  packages.

Changes:

- `acad_reference_request_run.py` now adds:
  - `reference_request_validation_issue_code_counts`
  - `reference_intake_issue_code_counts`
- `run_summary.md` prints both code-count fields.
- The run-level `artifact_index.json` carries both fields so artifact routers
  and CI consumers can inspect them without opening nested JSON.
- Existing recommended-action ordering is unchanged.

Boundary:

- Run-summary and artifact-index evidence only.
- No input gate semantics change.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Action Artifact Resolution Report

Status: implemented in this branch.

Purpose:

- Make route reports directly actionable when they select a handoff artifact.
- Avoid a second "open the artifact index, then manually resolve the relative
  path" step in CI logs or uploaded Markdown reports.

Changes:

- `acad_artifact_route.py` now annotates single-route and multi-route payloads
  with:
  - `action_artifact_resolved`
  - `action_artifact_exists`
- Relative action artifacts are resolved with the same source
  `artifact_index.json` rule already used by `--require-action-artifact-exists`.
- Text and Markdown route reports print the resolved path and existence state
  when a selected action names an artifact.
- Tests cover single-route and batch-route reporting.

Boundary:

- Route-report evidence only.
- No route priority change.
- No route gate semantics change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
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

## Follow-Up Request Validation Expected Size Evidence

Status: implemented in this branch.

Purpose:

- Make the request-validation report display the expected AutoCAD PNG size that
  it already validates.
- Let operators see the capture-size contract in
  `reference_request_validation.json/md` before returned AutoCAD PNGs exist,
  without reopening the original request package.

Changes:

- `acad_reference_batch.py` now writes per-case
  `requested_expected_size` as compact `WIDTHxHEIGHT` text in request
  validation rows.
- `reference_request_validation.md` adds an `Expected size` table column.
- `tools/render_regression/README.md` documents the operator-facing behavior.

Boundary:

- Request-validation evidence only.
- No request validation semantics change.
- No renderer change.
- No X3 scoring change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
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

## Follow-Up Request-Run Case Actions TSV

Status: implemented in this branch.

Purpose:

- Add a spreadsheet-friendly per-case action artifact to request-run outputs.
- Let operators sort/filter cases by action code, action domain, source,
  triage bucket, view-space status, and X3 band without scraping Markdown or
  manually reshaping JSON.

Changes:

- `acad_reference_request_run.py` now writes `case_actions.tsv` beside
  `run_summary.json/md`.
- `run_summary.json` includes `case_actions_tsv`.
- The run-level `artifact_index.json` includes a `case_actions_tsv` artifact.
- `run_summary.md` links the TSV in the artifact list.

Boundary:

- Reporting artifact only.
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

## Follow-Up Missing References TSV

Status: implemented in this branch.

Purpose:

- Add a spreadsheet-friendly missing-reference handoff artifact.
- Let operators sort/copy the exact returned AutoCAD PNG filenames and expected
  paths without scraping `missing_references.md`.

Changes:

- `acad_reference_batch.py` now writes `missing_references.tsv` beside
  `missing_references.json/md`.
- `missing_references.md` links the TSV path.
- Batch artifact indexes include `missing_references_tsv`.
- `_clear_batch_outputs()` removes stale `missing_references.tsv` on successful
  reruns, matching the JSON/Markdown cleanup behavior.

Boundary:

- Missing-input reporting artifact only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Request-Run Missing References TSV

Status: implemented in this branch.

Purpose:

- Surface the spreadsheet-friendly missing-reference handoff artifact from the
  higher-level request-run wrapper.
- Keep operators from having to inspect the nested input directory or scrape
  Markdown to find `missing_references.tsv`.

Changes:

- `acad_reference_request_run.py` now records `missing_references_tsv` in
  `run_summary.json`.
- `run_summary.md` lists the TSV under artifacts when the wrapper is
  input-blocked.
- The wrapper-level artifact index includes `missing_references_tsv`.
- The existing recommended next action still points to the Markdown report,
  because that remains the human-readable handoff.

Boundary:

- Artifact surfacing only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Missing Reference Capture Contract Columns

Status: implemented in this branch.

Purpose:

- Make the missing-reference handoff TSV directly actionable for AutoCAD export.
- Keep the requested capture method, view contract, and expected size beside the
  missing output filename/path instead of requiring operators to cross-reference
  `reference_request.json`.

Changes:

- `missing_references.json` rows now include:
  - `requested_capture_method`;
  - `requested_view_contract`;
  - `requested_expected_size` as a compact `WIDTHxHEIGHT` string when present.
- `missing_references.tsv` adds the same capture-contract columns.
- `missing_references.md` shows the capture/view/size fields in its table.

Boundary:

- Missing-input handoff artifact only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Action Artifacts

Status: implemented in this branch.

Purpose:

- Let standalone route reports point directly at the human-readable artifact for
  the recommended action.
- Avoid a two-step "read route, then open artifact index, then find the report"
  loop for missing-reference and request/intake input gates.

Changes:

- `acad_artifact_route.py` now pulls action artifacts from batch artifact
  indexes when available:
  - `fix-request-package` -> `reference_request_validation_markdown`;
  - `provide-returned-autocad-pngs` -> `missing_references_markdown`;
  - `inspect-returned-reference-warnings` -> `reference_intake_markdown`.
- Text route output now includes `action_artifact` when the recommended action
  has a target artifact.

Boundary:

- Read-only route surfacing only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Missing Reference Source DXF Handoff

Status: implemented in this branch.

Purpose:

- Make the missing-reference handoff self-contained for AutoCAD export.
- Keep the source DXF path and optional source hash on the same row as the
  requested output PNG and capture contract.

Changes:

- `missing_references.json` rows now include:
  - `source_dxf`;
  - `source_dxf_sha256` when the request package already has it.
- `missing_references.tsv` adds `source_dxf` and `source_dxf_sha256` columns.
- `missing_references.md` includes the source DXF in its table.

Boundary:

- Missing-input handoff artifact only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Action Artifact Gate

Status: implemented in this branch.

Purpose:

- Let unattended checks assert that the top-level route action points at the
  expected human-readable handoff artifact.
- Prevent a green route code/domain check from hiding a missing or wrong action
  artifact path.

Changes:

- `acad_artifact_route.py` now accepts `--require-action-artifact <path-suffix>`.
- The check compares against `recommended_next_action.artifact` with
  slash-normalized suffix matching so absolute CI paths remain stable.
- Failure output prints the actual action artifact and action code.
- README documents the combined `--require-action`, `--require-action-domain`,
  and `--require-action-artifact` guard for missing AutoCAD reference PNGs.

Boundary:

- Route-gate assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Action Artifact Exists Gate

Status: implemented in this branch.

Purpose:

- Let unattended checks prove the selected route action's handoff artifact is
  actually present, not just named.
- Resolve relative action artifacts from the source `artifact_index.json`
  directory so checks do not depend on the shell's current working directory.

Changes:

- Batch route top-level actions now record their selected
  `source_artifact_index` and `source_route_index`.
- `acad_artifact_route.py` now accepts `--require-action-artifact-exists`.
- The existence check resolves `recommended_next_action.artifact` relative to
  the selected source artifact index when the artifact path is relative.
- Tests cover both the pass path and fail-closed missing-file path.

Boundary:

- Route-gate assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Forbidden Domain Gate

Status: implemented in this branch.

Purpose:

- Let unattended route checks fail closed when any routed action belongs to a
  forbidden domain, even if the top-level recommended action is a higher
  priority input repair.
- Prevent mixed routes from hiding `renderer-candidate` work behind an input
  gate.

Changes:

- `acad_artifact_route.py` now accepts repeatable
  `--forbid-action-domain <domain>`.
- Multi-route payloads are checked against `recommended_action_domain_counts`.
- Request-run payloads are checked against `case_action_domain_counts`.
- Single-route payloads fall back to the top-level recommended action domain.
- Request-run route payload/text/Markdown now surface
  `case_action_domain_counts`.

Boundary:

- Route-gate assertion/reporting only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Forbidden Action Gate

Status: implemented in this branch.

Purpose:

- Let unattended route checks fail closed on one specific routed action code,
  even when that action shares an otherwise allowed domain.
- Prevent a coarse `--require-action-domain input` guard from accepting a run
  that still contains `recapture-autocad-or-provide-window` when a workflow is
  deliberately expecting a different input action.

Changes:

- `acad_artifact_route.py` now accepts repeatable `--forbid-action <code>`.
- Multi-route payloads are checked against `recommended_action_counts`.
- Request-run payloads are checked against `case_action_counts`.
- Single-route payloads fall back to the top-level recommended action code.
- Failure output prints both the forbidden action counts and the full routed
  action-count summary.

Boundary:

- Route-gate assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Route Action Domain Count Gate

Status: implemented in this branch.

Purpose:

- Let unattended route checks assert exact action-domain distribution, not only
  the top-level action domain or a forbidden-domain absence.
- Cover workflows that need to prove a route contains a known mix of `input`,
  `renderer-candidate`, `pass-review`, or `continue` work without enumerating
  every concrete action code.

Changes:

- `acad_artifact_route.py` now accepts repeatable
  `--require-action-domain-count <domain=count>`.
- Multi-route payloads are checked against `recommended_action_domain_counts`.
- Request-run payloads are checked against `case_action_domain_counts`.
- Single-route payloads fall back to the top-level recommended action domain.
- Failure output prints both the mismatched expectations and the full routed
  action-domain count summary.

Boundary:

- Route-gate assertion only.
- No route priority change.
- No renderer change.
- No X3 scoring or AutoCAD-equivalence wording change.
- No private drawing or AutoCAD PNG committed.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
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

## Follow-Up Manifest Compare Row Domains

Status: implemented in this branch.

Purpose:

- Carry action-domain routing at the per-case compare row level.
- Make `summary.json`, `summary.tsv`, `summary.md`, and the compare
  `artifact_index.json` classify each case as `input`, `renderer-candidate`,
  `pass-review`, or `input-review`.
- Keep `viewspace_mismatch` rows explicitly in the `input` domain so low pixel
  scores cannot be mistaken for renderer work.

Changes:

- `acad_manifest_compare.py` now annotates each compared row with
  `recommended_action_domain`.
- `summary.json` and the compare artifact index include
  `recommended_action_domain_counts`.
- `summary.tsv` adds a `recommended_action_domain` column.
- `summary.md` prints the domain in both the case table and triage-priority
  table.

Boundary:

- Compare-report metadata only.
- No X3 scoring change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
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
3. `fix-returned-reference-input` when intake is `blocked`.
4. `inspect-returned-reference-warnings` when intake is `review`.
5. `recapture-autocad-or-provide-window` on `viewspace_mismatch`.
6. `review-x3-pass` on matched-view pass.
7. `inspect-compare-failure` on compare failures.

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

## Follow-Up Render Regression README Test Count Drift

Status: implemented in this branch.

Purpose:

- Keep the operator README from hard-coding a stale render-regression test
  count.
- Make the pytest command itself the authoritative verification instruction as
  evidence/operator hardening slices continue to add tests.

Changes:

- `tools/render_regression/README.md` now says to run
  `python3 -m pytest tools/render_regression/tests -q` and trust pytest's live
  output for the test count.
- The note still preserves the important operator property: the suite uses
  synthetic images and does not require `render_cli`.

Boundary:

- Documentation-only drift repair.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest tools/render_regression/tests -q
# 169 passed
```

## Follow-Up Request-Run Validation Warning Visibility

Status: implemented in this branch.

Purpose:

- Keep `acad_reference_request_run.py`'s Markdown and CLI output aligned with
  its JSON payload.
- Surface request-validation warnings and issue-code counts in the operator
  path before returned-reference intake or compare output can distract from a
  bad request package.

Changes:

- `run_summary.md` now prints
  `reference_request_validation_warnings` beside validation errors and
  validation issue-code counts.
- The request-run CLI stdout now prints
  `reference request validation issue codes` on both input-blocked and compare
  paths.
- Regression coverage proves:
  - pass runs show `reference_request_validation_warnings: 0`;
  - blocked request-validation runs print the concrete
    `source_dxf_sha256_mismatch=1` issue code in stdout.

Boundary:

- Operator visibility only.
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

## Follow-Up Request-Run Intake Error Visibility

Status: implemented in this branch.

Purpose:

- Keep `run_summary.md` explicit when returned-reference intake is blocked.
- Avoid relying on `reference_intake_status` plus issue-code inference to know
  whether the returned AutoCAD PNG preflight has actual errors.

Changes:

- `run_summary.md` now prints `reference_intake_errors` beside
  `reference_intake_warnings`.
- Regression coverage proves:
  - pass runs show `reference_intake_errors: 0`;
  - returned PNG size mismatch runs show `reference_intake_errors: 1`.

Boundary:

- Operator Markdown visibility only.
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

## Follow-Up Request-Run Case Action Count Visibility

Status: implemented in this branch.

Purpose:

- Keep `run_summary.md` as specific as `run_summary.json` and CLI stdout.
- Let operators see the exact next-action distribution from Markdown without
  opening JSON or TSV artifacts.

Changes:

- `run_summary.md` now prints `case_action_counts` beside
  `case_action_domain_counts`.
- Regression coverage proves:
  - pass runs show `review-x3-pass=1`;
  - returned-reference input errors show `fix-returned-reference-input=1`.

Boundary:

- Operator Markdown visibility only.
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

## Follow-Up Request-Run Preflight Status In Route Artifacts

Status: implemented in this branch.

Purpose:

- Make request-run `artifact_index.json` and route reports carry the same
  preflight status/error/warning counts that `run_summary.json/md` already
  carries.
- Let artifact-route consumers understand request-validation and
  returned-reference intake state without opening nested preflight JSON files.

Changes:

- Request-run artifact indexes now include:
  - `reference_request_validation_status`;
  - `reference_request_validation_error_count`;
  - `reference_request_validation_warning_count`;
  - `reference_intake_status`;
  - `reference_intake_error_count`;
  - `reference_intake_warning_count`.
- `acad_artifact_route.py` preserves and prints those fields in JSON, text, and
  Markdown route reports.
- Regression coverage proves both direct route parsing and a full
  request-run-generated route summary expose the new fields.

Boundary:

- Artifact/report metadata only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring or AutoCAD-equivalence wording change.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_request_run.py \
  tools/render_regression/tests/test_acad_artifact_route.py -q
# 69 passed

python3 -m pytest tools/render_regression/tests -q
# 172 passed
```

## Follow-Up Compare Count Route Guards

Status: implemented in this branch.

Purpose:

- Let CI/operator route steps assert that a request-run actually compared the
  expected number of cases.
- Avoid relying only on bucket distributions when the first safety question is
  simpler: did the compare route cover all expected returned references?

Changes:

- `acad_artifact_route.py` adds:
  - `--require-compare-case-count <n>`;
  - `--require-compared-count <n>`.
- The guards read the correct field for:
  - a single compare artifact index (`case_count` / `compared_count`);
  - a single request-run artifact index (`route_compare_case_count` /
    `route_compared_count`);
  - recursive or multi-index route summaries (`compare_case_count` /
    `compared_count`).
- `tools/render_regression/README.md` documents the new guards beside the
  existing triage/viewspace/X3 distribution guards.

Boundary:

- Route guard hardening only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Batch Route Error/Warning Count Visibility

Status: implemented in this branch.

Purpose:

- Surface batch/input-prep `error_count` and `warning_count` in route reports.
- Let operators see whether a routed input-prep artifact is blocked by errors
  or merely in review without opening the batch artifact index JSON.

Changes:

- `acad_artifact_route.py` now preserves batch artifact `error_count` and
  `warning_count`.
- Route text and Markdown print those counts for any routed artifact that
  exposes them.
- Regression coverage proves a returned-reference intake block surfaces
  `errors: 1` and `warnings: 0` in both route text and Markdown.

Boundary:

- Route-report visibility only.
- No route priority change.
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

## Follow-Up Route Stage/Case Count Visibility

Status: implemented in this branch.

Purpose:

- Surface the routed batch/input-prep stage and case count in route text and
  Markdown.
- Let operators distinguish `request_validation`, `missing_references`, and
  `reference_intake` routes without opening the nested artifact index JSON.

Changes:

- Route text now prints `stage` and `case_count` whenever the routed artifact
  exposes them.
- Route Markdown prints the same fields.
- Regression coverage proves a returned-reference intake block surfaces
  `stage=reference_intake` and `case_count=1` in both text and Markdown.

Boundary:

- Route-report visibility only.
- No route priority change.
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

## Follow-Up Compare Route Count Visibility

Status: implemented in this branch.

Purpose:

- Surface compare-route `compared_count`, `viewspace_status_counts`, and
  `x3_band_counts` in route text and Markdown.
- Let operators see whether a routed compare artifact is dominated by matched
  renderer-candidate cases, recapture-required mismatches, or X3 band failures
  without opening `artifact_index.json`.

Changes:

- Route text now prints `compared_count` when a compare artifact exposes it.
- Route text and Markdown now print `viewspace_status_counts` and
  `x3_band_counts`.
- Regression coverage proves a mixed compare route surfaces:
  - `compared_count=2`;
  - `viewspace_status_counts=match=1, mismatch=1`;
  - `x3_band_counts=fail=1, fallback=1`.

Boundary:

- Route-report visibility only.
- No route priority change.
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

## Follow-Up Multi-Route Compare Count Visibility

Status: implemented in this branch.

Purpose:

- Surface compare-route count distributions in recursive/multi-index route
  summaries, not only inside each nested compare route.
- Let an unattended route artifact show whether its compare portion contains
  renderer-candidate, recapture-required, or X3 band failures without requiring
  operators to drill into every nested route.

Changes:

- Multi-route payloads now aggregate compare-route:
  - `compare_case_count`;
  - `compared_count`;
  - `triage_bucket_counts`;
  - `viewspace_status_counts`;
  - `x3_band_counts`.
- Multi-route text and Markdown summaries print those aggregates when compare
  routes are present.
- Regression coverage proves the top-level route summary still prioritizes
  input repair over renderer work while surfacing the nested compare
  distributions.

Boundary:

- Route-summary visibility only.
- No route priority change.
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

## Follow-Up Compare Distribution Route Guards

Status: implemented in this branch.

Purpose:

- Let unattended route checks fail closed on compare distribution drift, not
  only on top-level action/status/kind.
- Cover mixed route summaries where input repair correctly remains the top
  priority but the compare portion still contains `viewspace_mismatch`,
  `renderer-candidate`, or X3 band failures.

Changes:

- `acad_artifact_route.py` adds compare-distribution guards:
  - `--require-triage-bucket bucket=count`;
  - `--forbid-triage-bucket bucket`;
  - `--require-viewspace-status status=count`;
  - `--forbid-viewspace-status status`;
  - `--require-x3-band band=count`;
  - `--forbid-x3-band band`.
- The guards work for single compare routes and recursive/multi-route summaries
  because the previous slice aggregates compare counts at the top level.
- Regression coverage proves:
  - exact compare distributions can be required on a mixed batch;
  - a hidden `viewspace_status_counts.mismatch` fails closed even when an input
    repair route is the top-level recommendation.

Boundary:

- Route assertion only.
- No route priority change.
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

## Follow-Up Compare Distribution Guard README

Status: implemented in this branch.

Purpose:

- Keep the operator-facing render-regression README aligned with the
  compare-distribution route guards.
- Avoid hiding the new fail-closed guard syntax only in `--help` output or this
  closeout ledger.

Changes:

- `tools/render_regression/README.md` now documents:
  - `--require-triage-bucket` / `--forbid-triage-bucket`;
  - `--require-viewspace-status` / `--forbid-viewspace-status`;
  - `--require-x3-band` / `--forbid-x3-band`.
- The README includes examples for:
  - failing closed on any nested `viewspace_status_counts.mismatch`;
  - asserting a matched renderer-candidate distribution exactly.

Boundary:

- Documentation only.
- No route priority change.
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

## Follow-Up Request-Run Route Compare Distribution Summary

Status: implemented in this branch.

Purpose:

- Make the one-command `run_summary.json/md` show the same compare distribution
  evidence that `route_summary.json/md` already carries.
- Let operators inspect a request-run artifact without opening the nested route
  summary just to learn whether the compare portion is `matched-pass`,
  `viewspace_mismatch`, or an X3 failure distribution.

Changes:

- `acad_reference_request_run.py` now copies these route-summary aggregates
  into `run_summary.json`:
  - `route_compare_case_count`;
  - `route_compared_count`;
  - `route_triage_bucket_counts`;
  - `route_viewspace_status_counts`;
  - `route_x3_band_counts`.
- `run_summary.md` prints the same fields when route summary evidence exists.
- Regression coverage proves:
  - a pass run shows `matched-pass=1`, `match=1`, `pass=1`;
  - a mixed `viewspace_mismatch` run shows both `matched-pass` and
    `recapture-required`, plus `match=1, mismatch=1`.

Boundary:

- Run-summary evidence only.
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

## Follow-Up Request-Run Compare Summary README

Status: implemented in this branch.

Purpose:

- Keep the operator-facing render-regression README aligned with the
  request-run compare distribution summary fields.
- Avoid making operators discover `route_compare_case_count`,
  `route_triage_bucket_counts`, `route_viewspace_status_counts`, and
  `route_x3_band_counts` only by reading JSON output or the closeout ledger.

Changes:

- `tools/render_regression/README.md` now states that request-run summaries
  surface route compare case counts, compared counts, triage bucket counts,
  viewspace status counts, and X3 band counts when compare artifacts are
  present.

Boundary:

- Documentation only.
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

## Follow-Up Request-Run Compare Distribution CLI Logs

Status: implemented in this branch.

Purpose:

- Make CI logs show the request-run compare distribution directly, not only
  `run_summary.json/md`.
- Keep unattended jobs useful even when an operator only sees stdout from
  `acad_reference_request_run.py`.

Changes:

- `acad_reference_request_run.py` now prints route compare case count, compared
  count, triage bucket counts, viewspace status counts, and X3 band counts when
  those fields are present in the run summary.
- The duplicate success/input-blocked print blocks were consolidated through a
  shared `_print_run_summary()` helper.
- Regression coverage proves both pass and mixed `viewspace_mismatch` runs emit
  the new stdout lines.

Boundary:

- CLI log visibility only.
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

## Follow-Up Request-Run Compare CLI Log README

Status: implemented in this branch.

Purpose:

- Keep the operator-facing render-regression README aligned with the request-run
  stdout compare distribution lines.
- Make clear that CI logs now show the compare portion without requiring
  operators to open uploaded artifacts.

Changes:

- `tools/render_regression/README.md` now states that
  `acad_reference_request_run.py` prints route compare distributions to stdout
  when they are present.

Boundary:

- Documentation only.
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

## Follow-Up Request-Run Artifact Index Route Compare Evidence

Status: implemented in this branch.

Purpose:

- Make the run-level `artifact_index.json` carry the same route compare
  distribution evidence as `run_summary.json/md` and stdout.
- Keep machine consumers from having to open `run_summary.json` before they can
  fail closed on routed compare evidence.
- Preserve the no-guess discipline: a `viewspace_mismatch` distribution remains
  input/recapture evidence, not a renderer-tuning signal.

Changes:

- `acad_reference_request_run.py` now rewrites the final run-level
  `artifact_index.json` after route aggregation so it includes:
  - `route_count`, `route_kind_counts`, `route_status_counts`;
  - `route_recommended_action_counts` and
    `route_recommended_action_domain_counts`;
  - `route_compare_case_count`, `route_compared_count`,
    `route_triage_bucket_counts`, `route_viewspace_status_counts`, and
    `route_x3_band_counts`.
- The generated `route_summary.json/md` is recomputed after the final artifact
  index rewrite, so its nested request-run route sees the same evidence.
- `acad_artifact_route.py` now preserves these request-run `route_*` fields and
  prints them in text/Markdown route reports.
- Compare-distribution guards can read the request-run `route_*` fields, so a
  workflow can run `acad_artifact_route.py <run>/artifact_index.json` directly
  and still assert triage/viewspace/X3 distributions.
- `tools/render_regression/README.md` documents that run summaries, run-level
  artifact indexes, and stdout all carry the route compare distributions.

Boundary:

- Evidence and operator-routing hardening only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_request_run.py \
  tools/render_regression/tests/test_acad_artifact_route.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Reference Markdown Table Cell Escaping

Status: implemented in this branch.

Purpose:

- Keep operator-facing Markdown handoff tables structurally reliable when
  drawing IDs, returned PNG names, paths, or diagnostic text contain Markdown
  table metacharacters.
- Prevent `|` or newline characters in request/package fields from silently
  shifting columns in `missing_references.md` or `reference_intake.md`.

Changes:

- `acad_reference_batch.py` now formats Markdown table cells through shared
  helpers:
  - plain cells collapse newlines and escape Markdown table pipes/backticks;
  - code cells collapse newlines, escape table pipes, and choose a safe
    code-span delimiter when values themselves contain backticks.
- `missing_references.md` now escapes case IDs, drawing IDs, source DXF paths,
  recommended output names, capture/view/size cells, and expected paths.
- `reference_intake.md` now escapes case IDs, drawing IDs, recommended output
  names, size/expected-size cells, identity-advisory text, and issue summaries.
- Regression tests cover both reports with a drawing ID containing `|` plus a
  newline and an AutoCAD output filename containing `|`; the tests assert the
  rendered table rows keep the expected number of unescaped Markdown
  delimiters.

Boundary:

- Operator report formatting only.
- JSON and TSV payloads remain unchanged structured sources of truth.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed

python3 -m pytest tools/render_regression/tests -q
# passed
```

## Follow-Up Request Validation Markdown Table Cell Escaping

Status: implemented in this branch.

Purpose:

- Extend the Markdown table escaping hardening to the earliest request-package
  validation report.
- Keep `reference_request_validation.md` reliable when request package fields
  contain Markdown table metacharacters before any returned AutoCAD PNG is
  available.

Changes:

- The `reference_request_validation.md` table now formats case IDs, drawing
  IDs, recommended output names, capture/view/size cells, source DXF paths,
  candidate PNG paths, and issue summaries through the same Markdown-safe
  helpers used by the missing-reference and intake reports.
- Regression coverage runs `acad_reference_batch.py --validate-request` with a
  drawing ID containing `|` plus a newline and PNG names containing `|`, then
  asserts the rendered table row keeps the expected number of unescaped
  Markdown delimiters.
- `tools/render_regression/README.md` now names all three escaped operator
  Markdown tables: request-validation, missing-reference, and intake.

Boundary:

- Operator report formatting only.
- JSON and TSV payloads remain unchanged structured sources of truth.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_batch.py -q
# passed
```

## Follow-Up Request-Run Markdown Case Action Escaping

Status: implemented in this branch.

Purpose:

- Extend Markdown table escaping to the top-level unattended run summary.
- Keep `run_summary.md` reliable when case action rows inherit drawing IDs,
  output paths, or artifact paths containing Markdown table metacharacters.

Changes:

- `acad_reference_request_run.py` now formats run-summary artifact links and
  Case Actions table cells through local Markdown-safe helpers.
- The Case Actions table escapes case IDs, drawing IDs, action code/domain,
  source, triage/issue cells, and artifact paths.
- Regression coverage runs the full request-run pipeline with a drawing ID
  containing `|` plus a newline and returned/candidate/output paths containing
  `|`, then asserts the top-level Case Actions table keeps the expected number
  of unescaped Markdown delimiters.
- `tools/render_regression/README.md` now states that request-run summaries use
  the same operator-cell escaping for case-action rows and artifact links.

Boundary:

- Operator report formatting only.
- JSON and TSV payloads remain unchanged structured sources of truth.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# passed
```

## Follow-Up Manifest Compare Markdown Cell Escaping

Status: implemented in this branch.

Purpose:

- Bring the manifest-compare summary and generated recapture request Markdown
  tables onto the same safe table/code-cell formatting used by the input and
  request-run reports.
- Keep `summary.md` and `reference_request.md` structurally reliable when case
  IDs, drawing IDs, or recommended output names contain Markdown table
  metacharacters.

Changes:

- `acad_manifest_compare.py` now has Markdown-safe plain/table/code cell
  helpers that collapse CR/LF, escape Markdown table pipes, and choose a safe
  code-span delimiter for code-style cells.
- The compare summary Issues/Cases/Triage tables, artifact-path bullets, and
  generated recapture request table now use those helpers.
- Regression coverage runs a real `viewspace_mismatch` compare with a case ID
  containing `|` and a drawing ID containing `|` plus a newline, then asserts
  the summary Cases table, Triage table, and recapture request table keep their
  expected number of unescaped Markdown delimiters.
- `tools/render_regression/README.md` now records that manifest-compare
  Markdown reports also use the same safe cell formatting.

Boundary:

- Operator report formatting only.
- JSON and TSV payloads remain unchanged structured sources of truth.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up Route Markdown Code-Span Escaping

Status: implemented in this branch.

Purpose:

- Finish the operator Markdown escaping pass on the route-report layer.
- Keep `route_summary.md` readable when action artifacts or routed artifact
  paths contain Markdown code-span delimiters or table metacharacters.

Changes:

- `acad_artifact_route.py` now formats Markdown route report values through
  safe plain/code cell helpers that collapse CR/LF, escape table pipes, and
  choose a safe code-span delimiter when values contain backticks.
- Route Markdown output now applies those helpers to artifact index paths,
  action artifacts, resolved artifact paths, status/count fields, issue-count
  summaries, source boundaries, and routed compare distributions.
- Regression coverage routes a missing-reference artifact whose recommended
  Markdown path contains both `|` and a backtick, then asserts the rendered
  route report uses a safe code span and escaped pipe.
- `tools/render_regression/README.md` now records that route reports use the
  same safe code-span formatting for action artifacts and count summaries.

Boundary:

- Operator report formatting only.
- JSON and text route payloads remain unchanged structured sources of truth.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# passed
```

## Follow-Up Recapture Request Markdown Provenance Columns

Status: implemented in this branch.

Purpose:

- Surface the source/candidate identity evidence already present in
  `reference_request.json` directly in the operator-facing recapture request
  Markdown.
- Let handoffs verify the source DXF and candidate PNG provenance without
  opening JSON first.

Changes:

- `acad_manifest_compare.py` now adds `Source SHA256` and `Candidate SHA256`
  columns to generated `reference_request.md`.
- The values are sourced from the existing `source_dxf_sha256` and
  `candidate_png_sha256` fields already written to each request case.
- Regression coverage asserts the generated Markdown includes both hashes in
  the normal `viewspace_mismatch` request path.
- The Markdown escaping regression was updated for the wider recapture request
  table.
- `tools/render_regression/README.md` now documents that the recapture request
  Markdown surfaces these provenance values.

Boundary:

- Operator evidence surfacing only.
- `reference_request.json` schema/content is unchanged.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up Recapture Request Markdown Status Columns

Status: implemented in this branch.

Purpose:

- Make generated `reference_request.md` handoffs explain not only which files
  to recapture, but why they are in the recapture lane and what size contract
  the returned PNG should satisfy.
- Surface existing per-case request evidence without requiring operators to
  open `reference_request.json`.

Changes:

- `acad_manifest_compare.py` now adds `Current view`, `Current X3`, and
  `Expected size` columns to generated `reference_request.md`.
- The values are sourced from existing request case fields:
  `current_viewspace_status`, `current_x3_band`, and
  `requested_expected_size`.
- A local `_expected_size_text()` helper formats `requested_expected_size` as
  compact `WIDTHxHEIGHT` text for Markdown.
- Regression coverage asserts the normal `viewspace_mismatch` request
  Markdown includes `mismatch`, `fallback`, and `800x600`.
- The Markdown escaping regression was updated for the wider recapture request
  table.
- `tools/render_regression/README.md` now documents the visible recapture
  status/size columns.

Boundary:

- Operator evidence surfacing only.
- `reference_request.json` schema/content is unchanged.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# passed
```

## Follow-Up Route Final Exit Code Counts

Status: implemented in this branch.

Purpose:

- Surface request-run and batch `final_exit_code` evidence at the route-summary
  level, so uploaded directory reports show which directly routed artifact
  returned `0` versus an opt-in operator hard failure such as `2`.
- Keep the evidence aligned across `route_summary.json/md`,
  `run_summary.json/md`, the run-level `artifact_index.json`, and stdout.
- Preserve the no-guess discipline: exit-code aggregation is operator evidence,
  not a renderer-fidelity claim and not a new default gate.

Changes:

- `acad_artifact_route.py` now preserves `final_exit_code` on routed
  batch/request-run artifacts.
- Multi-route summaries now include `final_exit_code_counts` for directly
  routed artifacts that expose a final exit code.
- Request-run artifacts preserve nested `route_final_exit_code_counts`, and
  request-run summaries print that distribution in Markdown and stdout.
- Route text/Markdown reports print both per-route `final_exit_code` and
  nested `route_final_exit_code_counts` when present.
- `tools/render_regression/README.md` documents the route-level exit-code
  distribution.

Boundary:

- Evidence and operator-routing hardening only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_request_run.py \
  tools/render_regression/tests/test_acad_artifact_route.py -q
# 75 passed

python3 -m pytest tools/render_regression/tests -q
# 183 passed
```

## Follow-Up Route Final Exit Code Guards

Status: implemented in this branch.

Purpose:

- Let CI/operator scripts fail closed directly from `acad_artifact_route.py`
  when routed artifacts include an undesirable final exit code, such as an
  opt-in input-review hard failure returning `2`.
- Avoid requiring downstream jobs to parse `route_summary.json` with `jq` after
  `final_exit_code_counts` has already been computed by the route tool.
- Preserve default behavior: route commands still only fail on these exit-code
  distributions when an explicit guard flag is supplied.

Changes:

- `acad_artifact_route.py` now accepts:
  - `--require-final-exit-code <code>`;
  - `--forbid-final-exit-code <code>`;
  - `--require-final-exit-code-count <code=count>`.
- Multi-route payloads check top-level `final_exit_code_counts`.
- Single batch/request-run routes check their own `final_exit_code`.
- Guards intentionally do not recursively count
  `route_final_exit_code_counts`, avoiding double-counting the same nested
  evidence.
- `tools/render_regression/README.md` documents the new guard flags and a
  `--forbid-final-exit-code 2` example.

Boundary:

- Opt-in route guard only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 68 passed

python3 -m pytest tools/render_regression/tests -q
# 187 passed
```

## Follow-Up Compare Issue Code Counts

Status: implemented in this branch.

Purpose:

- Make compare manifest/candidate input problems visible as issue-code
  distributions, not just a raw `issue_count`.
- Let `acad_artifact_route.py --require-issue-code/--forbid-issue-code` fail
  closed on compare-layer issues such as `diagnostic_capture_method`,
  `missing_candidate_cases`, or `candidate_case_missing`.
- Preserve the existing routing discipline: issue-code counts do not change
  action priority, do not turn `viewspace_mismatch` into renderer work, and do
  not claim AutoCAD equivalence.

Changes:

- `acad_manifest_compare.py` now writes `issue_code_counts` into
  `summary.json`, `summary.md`, and `artifact_index.json`.
- `acad_artifact_route.py` preserves those counts as
  `compare_issue_code_counts`.
- Multi-route summaries aggregate `compare_issue_code_counts` alongside
  request-validation and returned-reference intake issue-code counts.
- Existing `--require-issue-code` and `--forbid-issue-code` guards now inspect
  compare issue-code counts too.
- `tools/render_regression/README.md` documents the expanded guard scope.

Boundary:

- Evidence and operator-routing hardening only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_manifest_compare.py \
  tools/render_regression/tests/test_acad_artifact_route.py -q
# 77 passed

python3 -m pytest tools/render_regression/tests -q
# 188 passed
```

## Follow-Up Route Issue Code Count Guard

Status: implemented in this branch.

Purpose:

- Let CI/operator scripts pin exact issue-code distributions, not only issue
  presence/absence.
- Keep request-validation, returned-reference intake, and compare issue-code
  guards consistent with the existing `code=count` style used by route
  distribution guards.
- Preserve the existing route priority and default exit behavior.

Changes:

- `acad_artifact_route.py` now accepts repeatable
  `--require-issue-code-count <code=count>`.
- The guard reads the same merged issue-code counts as
  `--require-issue-code` and `--forbid-issue-code`, including compare
  issue-code counts.
- `tools/render_regression/README.md` documents the new guard.

Boundary:

- Opt-in route guard only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_artifact_route.py -q
# 70 passed

python3 -m pytest tools/render_regression/tests -q
# 189 passed
```

## Follow-Up Request-Run Compare Issue Code Counts

Status: implemented in this branch.

Purpose:

- Keep request-run wrapper artifacts aligned with route compare issue-code
  evidence introduced by the compare issue-code-count slice.
- Let `run_summary.json`, run-level `artifact_index.json`, routed
  request-run artifacts, Markdown/stdout, and route guards see nested compare
  manifest/candidate issue-code distributions.
- Preserve the no-double-counting discipline: direct compare routes remain the
  source of truth when present; request-run nested compare counts are used when
  routing request-run artifacts by themselves.

Changes:

- `acad_reference_request_run.py` now copies route-level
  `compare_issue_code_counts` into `route_compare_issue_code_counts`.
- Run-level artifact indexes include `route_compare_issue_code_counts`.
- Run Markdown/stdout print non-empty `route_compare_issue_code_counts`.
- `acad_artifact_route.py` preserves request-run
  `route_compare_issue_code_counts`, prints them, and includes them in
  issue-code guards for single request-run artifacts.
- Multi-route summaries aggregate request-run nested compare issue-code counts
  only when no direct compare route is present, matching the existing
  compare-distribution pattern.

Boundary:

- Evidence and operator-routing hardening only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest \
  tools/render_regression/tests/test_acad_reference_request_run.py \
  tools/render_regression/tests/test_acad_artifact_route.py -q
# 81 passed

python3 -m pytest tools/render_regression/tests -q
# 189 passed
```

## Follow-Up Recapture Route Action Artifact Guard

Status: implemented in this branch.

Purpose:

- Make generated `reference_request.md` handoff commands fail closed when the
  routed `recommended_next_action.artifact` does not resolve to an existing
  file.
- Avoid a green boundary/action route check that points operators at a missing
  handoff artifact.
- Reuse the existing `acad_artifact_route.py --require-action-artifact-exists`
  guard instead of adding new route semantics.

Changes:

- `acad_manifest_compare.py` now adds `--require-action-artifact-exists` to
  the generated post-return `acad_artifact_route.py <next-run-dir> --recursive`
  command in `reference_request.md`.
- The generated handoff test asserts the guard appears exactly once in the
  route-inspection command block.

Boundary:

- Generated operator handoff hardening only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 8 passed

python3 -m pytest tools/render_regression/tests -q
# 189 passed
```

## Follow-Up Recapture Route Count Guard

Status: implemented in this branch.

Purpose:

- Make generated `reference_request.md` post-return handoff commands prove the
  full request-run route shape before operators interpret pixels.
- Fail closed when the recursive route did not produce the expected
  `batch + compare + request_run` evidence chain.
- Keep partial-return support intact: operators can repeat `--case-id <ID>` for
  returned cases only; a successful selected run still produces the same three
  route entries.

Changes:

- `acad_manifest_compare.py` now adds `--require-route-count 3` to the
  generated post-return `acad_artifact_route.py <next-run-dir> --recursive`
  command in `reference_request.md`.
- The generated handoff test asserts the route-count guard appears exactly once
  beside the existing boundary and action-artifact guards.

Boundary:

- Generated operator handoff hardening only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 8 passed

python3 -m pytest tools/render_regression/tests -q
# 189 passed
```

## Follow-Up Recapture Route Kind Guard

Status: implemented in this branch.

Purpose:

- Make generated `reference_request.md` post-return handoff commands prove the
  recursive route topology, not just the number of discovered artifact indexes.
- Fail closed if a run has three routed artifacts but is missing one of the
  required `batch`, `compare`, or `request_run` evidence nodes.
- Keep this as an opt-in generated handoff guard; route priority and default
  route behavior are unchanged.

Changes:

- `acad_manifest_compare.py` now adds `--require-kind batch`,
  `--require-kind compare`, and `--require-kind request_run` to the generated
  post-return `acad_artifact_route.py <next-run-dir> --recursive` command in
  `reference_request.md`.
- The generated handoff test asserts each required kind guard appears exactly
  once beside the existing boundary, route-count, and action-artifact guards.

Boundary:

- Generated operator handoff hardening only.
- No route priority change.
- No default exit-code behavior change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 8 passed

python3 -m pytest tools/render_regression/tests -q
# 189 passed
```

## Follow-Up Recapture Input-Review Fail Flag

Status: implemented in this branch.

Purpose:

- Keep generated `reference_request.md` post-return handoff commands aligned
  with the README's unattended wrapper example.
- Fail closed when returned-reference intake warnings would otherwise leave a
  `pass` comparison with a recommended action in the `input-review` domain.
- Preserve the lower-level wrapper default: `acad_reference_request_run.py`
  remains review-lane by default unless `--fail-on-input-review` is passed.

Changes:

- `acad_manifest_compare.py` now adds `--fail-on-input-review` to the
  generated post-return `acad_reference_request_run.py` command in
  `reference_request.md`.
- The generated handoff test asserts the fail flag appears exactly once beside
  the request-boundary and route-topology guards.

Boundary:

- Generated operator handoff hardening only.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 8 passed

python3 -m pytest tools/render_regression/tests -q
# 189 passed
```

## Follow-Up Recapture Input-Review Route Guard

Status: implemented in this branch.

Purpose:

- Keep the generated post-return route-inspection command aligned with the
  generated wrapper's `--fail-on-input-review` behavior.
- Fail closed if any routed artifact still recommends an `input-review` action
  before operators interpret pixels.
- Avoid over-constraining legitimate outcomes: the guard does not forbid
  `viewspace_mismatch`, `renderer-candidate`, or `pass-review` results.

Changes:

- `acad_manifest_compare.py` now adds
  `--forbid-action-domain input-review` to the generated post-return
  `acad_artifact_route.py <next-run-dir> --recursive` command in
  `reference_request.md`.
- The generated handoff test asserts the route-level input-review guard appears
  exactly once.

Boundary:

- Generated operator handoff hardening only.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 8 passed

python3 -m pytest tools/render_regression/tests -q
# 189 passed
```

## Follow-Up README Recapture Guard Example

Status: implemented in this branch.

Purpose:

- Keep the README's post-return route example aligned with the generated
  `reference_request.md` handoff guard suite.
- Avoid an operator copying the README example and missing the stricter
  input-review, route topology, route count, and action-artifact checks.
- Make the README example itself test-covered so future guard additions do not
  silently drift from the generated handoff.

Changes:

- `tools/render_regression/README.md` now includes the same generated
  post-return route guards: `--forbid-action-domain input-review`,
  `--require-kind batch`, `--require-kind compare`,
  `--require-kind request_run`, `--require-route-count 3`, and
  `--require-action-artifact-exists`.
- `test_acad_manifest_compare.py` now extracts the README `<run-dir>` route
  example block and asserts the guard list is present there, avoiding a false
  pass from later explanatory sections.

Boundary:

- Operator documentation/test hardening only.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 9 passed

python3 -m pytest tools/render_regression/tests -q
# 190 passed
```

## Follow-Up README Request-Run Guard Example

Status: implemented in this branch.

Purpose:

- Keep the README's post-return `acad_reference_request_run.py` example
  test-covered alongside the route example.
- Prevent drift where the wrapper example loses its request-boundary checks or
  the `--fail-on-input-review` hardening flag while the generated handoff
  remains stricter.

Changes:

- `test_acad_manifest_compare.py` now extracts the README
  `acad_reference_request_run.py` example block and asserts it documents the
  three request-boundary guards plus `--fail-on-input-review`.

Boundary:

- Operator documentation/test hardening only.
- No README text change.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 10 passed

python3 -m pytest tools/render_regression/tests -q
# 191 passed
```

## Follow-Up Generated Handoff Block Assertions

Status: implemented in this branch.

Purpose:

- Strengthen the generated `reference_request.md` tests so guard flags must
  appear inside the intended fenced command blocks, not merely somewhere in the
  Markdown.
- Preserve the existing single-occurrence checks while preventing a future
  false green where explanatory prose mentions a guard but the command omits it.

Changes:

- `test_acad_manifest_compare.py` now has a shared
  `_markdown_block_after()` helper used by README and generated handoff tests.
- The generated `reference_request.md` test extracts the post-return
  `acad_reference_request_run.py` block and asserts the request-boundary guards
  plus `--fail-on-input-review` are present there.
- The same test extracts the post-return `acad_artifact_route.py` block and
  asserts the source/request boundary, input-review, topology, route-count, and
  action-artifact guards are present there.

Boundary:

- Test hardening only.
- No generated handoff text change.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 10 passed

python3 -m pytest tools/render_regression/tests -q
# 191 passed
```

## Follow-Up Recapture Expected Size Source

Status: implemented in this branch.

Purpose:

- Prevent generated recapture requests from inheriting a stale or chrome-cropped
  current AutoCAD PNG's pixel size when the manifest already declared the
  expected matched-view size.
- Keep the old PNG size as a fallback only when the manifest has no
  `expected_size` to carry forward.

Changes:

- `_compare_case()` now preserves the validated manifest `expected_size` on
  each compare row.
- `_write_reference_request()` now prefers row `expected_size` for
  `requested_expected_size`, falling back to the current AutoCAD PNG dimensions
  only when no expected size is available.
- Added a direct regression test where the current AutoCAD PNG is 640x480 but
  the manifest row declares 800x600; the generated request and Markdown keep
  800x600.

Boundary:

- Recapture request metadata hardening only.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Expected Size Summary Surface

Status: implemented in this branch.

Purpose:

- Surface the compare row `expected_size` in operator-readable outputs so the
  recapture size contract can be audited without opening `summary.json` or the
  generated request package.
- Keep this additive: JSON rows already carry the field; this exposes it in the
  TSV and Markdown summary tables.

Changes:

- `summary.tsv` now includes an `expected_size` column between
  `recommended_action_domain` and the artifact path columns.
- `summary.md` case rows now include an `Expected size` column.
- Existing manifest-compare tests assert `760x570` on a matched case and
  `800x600` on the recapture/mismatch case.

Boundary:

- Evidence surface hardening only.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_manifest_compare.py -q
# 11 passed

python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up README Expected Size Summary Note

Status: implemented in this branch.

Purpose:

- Keep operator documentation aligned with the expected-size summary surface.
- Make it clear that `summary.json`, `summary.tsv`, and `summary.md` now expose
  each row's `expected_size`, so operators do not need to open the generated
  request package merely to audit the capture-size contract.

Changes:

- `tools/render_regression/README.md` now states that compare summaries surface
  per-row `expected_size` alongside the existing recommended action domain
  evidence.

Boundary:

- Documentation-only.
- No wrapper default behavior change.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests -q
# 192 passed
```

## Follow-Up Case Action Issue Codes

Status: implemented in this branch.

Purpose:

- Make the one-command runner's per-case action table show the exact
  request-validation or returned-reference-intake issue codes for each case.
- Let unattended runs sort/filter `case_actions.tsv` by action and defect class
  without opening nested JSON or Markdown artifacts.

Changes:

- `case_actions[]` rows for request-validation and returned-reference-intake
  issues now include `issue_codes` such as
  `error:returned_png_size_mismatch` or
  `warning:long_edge_below_requested`.
- `case_actions.tsv` now has an `issue_codes` column after `issue_count`.
- `run_summary.md` Case Actions table now has an `Issue codes` column.
- The README documents the new spreadsheet triage field.

Boundary:

- Operator evidence/reporting only.
- No route priority change.
- No renderer change.
- No private drawing or AutoCAD PNG committed.
- No X3 scoring change.
- No AutoCAD-equivalence claim.

Verification:

```bash
python3 -m pytest tools/render_regression/tests/test_acad_reference_request_run.py -q
# 11 passed
```
