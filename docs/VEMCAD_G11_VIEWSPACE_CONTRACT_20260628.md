# VemCAD G11 View-Space Contract (2026-06-28)

## Purpose

This note closes the next G11 slice after the HFit revalidation:

> Before changing renderer text/layout behavior again, make the AutoCAD PLOT vs
> `render_cli` view-space contract machine-readable and verify the current G11
> reference against it.

This is intentionally not a renderer tweak. It prevents a different class of
mistake: interpreting a low X3 score from two differently framed PNGs as a
rendering defect.

## Delivered Tooling

`tools/render_regression/compare_vs_acad.py` now supports:

- `--viewspace-report <json>` — writes `vemcad.x3_viewspace_contract/v1`.
- `--require-viewspace-match` — returns `2` when the contract status is not
  `match`.

The report records:

- `status`: `match`, `mismatch`, or `unavailable`;
- `framing`: page-fill per axis, divergence per axis, raw ink-bbox
  `aspect_delta`, and `framing_mismatch`;
- thresholds (`FRAMING_TOL`, `ASPECT_TOL`);
- the normal X3 summary;
- the recommended next action.

Default CLI behavior is unchanged: without `--require-viewspace-match`, the
tool remains diagnostic and returns `0`.

## G11 Verification

Current inputs:

- AutoCAD reference: `/tmp/vemcadautocadplot/batch/png/G11-1.png`
- VemCAD render: `/tmp/vemcad-fidelity-out/g11_hfit_20260627T235144/renders/G11_ours.png`
- render image: `ghcr.io/zensgit/vemcad-render:main` after VemCAD #159

Command:

```bash
python3 tools/render_regression/compare_vs_acad.py \
  /tmp/vemcadautocadplot/batch/png/G11-1.png \
  /tmp/vemcad-fidelity-out/g11_hfit_20260627T235144/renders/G11_ours.png \
  --viewspace-report /tmp/vemcad-fidelity-out/g11_viewspace_contract_20260628T035017/G11_viewspace_contract.json \
  --semantic-mask /tmp/vemcad-fidelity-out/g11_hfit_20260627T235144/renders/G11_semantic_mask.png \
  --semantic-render-report /tmp/vemcad-fidelity-out/g11_hfit_20260627T235144/renders/G11_report.json \
  --semantic-class-report /tmp/vemcad-fidelity-out/g11_viewspace_contract_20260628T035017/G11_semantic_classes.json \
  --print-semantic-classes
```

Result:

```text
status              mismatch
ref_fill_x          0.4361
ref_fill_y          0.9220
cand_fill_x         0.3732
cand_fill_y         0.7919
fill_divergence_x   0.0628
fill_divergence_y   0.1301
aspect_delta        0.0035
framing_mismatch    true
```

`--require-viewspace-match` returns `2` on the same G11 pair, as expected.

Interpretation:

- G11 is **not** a same-view-space X3 reference today.
- The candidate and AutoCAD reference differ in page-fill on both axes; both
  exceed the `0.05` tolerance.
- The normal X3 score is still useful as a diagnostic, but must not be used as a
  renderer equivalence verdict.

## Boundary

Do not mark G11 as AutoCAD-equivalent while the view-space contract status is
`mismatch`.

Do not use `candidate-frame=reference-envelope` as a production pass. It is a
diagnostic lens that removes one paper-framing mismatch so residual locations
can be inspected; it is not proof that the original AutoCAD PNG and render_cli
output share a model window.

Do not ship another renderer text/layout tweak from G11 aggregate movement
until either:

1. AutoCAD is recaptured/exported at a model-extents window matching
   `render_cli`, or
2. `render_cli` is run with an explicit `--window` proven to match the AutoCAD
   PLOT window.

## Next Useful Slice

The next development step is now sharply scoped:

- if the goal is a hard G11 X3 number, produce a matched AutoCAD reference or a
  matched render window, then rerun X3 with `--require-viewspace-match`;
- if the goal is renderer internals, work on static block text / MTEXT
  provenance, but keep its claims diagnostic until G11's view-space status is
  `match`.
