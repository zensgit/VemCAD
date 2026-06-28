# AutoCAD Render Fidelity — G05 Hatch Stray Fix

Date: 2026-06-28

Scope: training-batch render fidelity for the G05/B05 drawing. This records the
two CADGameFusion renderer fixes consumed by VemCAD and the post-fix comparison
evidence against the local AutoCAD PLOT PNG references.

## Problem

The G05 drawing showed visible hatch-derived geometry outside the intended
detail/table region. In the review contact sheet this appeared as tall green
vertical columns crossing the right-side detail views and BOM/title-table area.

This was not a view framing issue alone. The bad columns were present in the
rendered drawing content.

## Fixes Landed

1. CADGameFusion #427 / VemCAD #147
   - CADGameFusion: `c01456d632becfe845be9ad21b5061eff20b1742`
   - VemCAD: `cbe6db71893b90584c8f75dcd3042477ee1db174`
   - Change: hide implicit boundaries for pattern HATCH entities.
   - Result: correct and safe, but not sufficient for G05. The largest vertical
     hatch columns remained.

2. CADGameFusion #428 / VemCAD #148
   - CADGameFusion: `480e5e5e4a6c5c7f9eefb74b284279c67f777b13`
   - VemCAD: `21f4f21285cb9fe95cbc5bed6368e10b1f9b6070`
   - Change: sample clockwise HATCH arc edges geometrically instead of using
     mirrored raw DXF angle values directly.
   - Result: the tall G05 hatch columns disappeared.

## Root Cause

The main G05 failure came from clockwise HATCH arc edges whose raw DXF start/end
angles were mirrored relative to the geometric arc. The adapter sampled those
raw angles directly, which placed fill strokes on the opposite side of a
large-radius circle. For G05 this generated fill segments thousands of drawing
units away from the intended detail geometry.

The CADGameFusion regression test added by #428 uses a synthetic clockwise HATCH
arc that fails on the old adapter because the fill lands near the opposite side
of the circle, then passes when the arc angles are mirrored before sampling.

## Verification

### CADGameFusion

Local targeted tests passed before opening the PR:

```bash
cmake --build /private/tmp/cadgf-dimcolor-build \
  --target test_dxf_libdxfrw_hatch_clockwise_arc \
           test_dxf_libdxfrw_hatch_boundary_visibility \
           test_dxf_libdxfrw_truewhite_dimension_child_colors \
           test_dxf_libdxfrw_orphan_dimension_blocks -j2

ctest --test-dir /private/tmp/cadgf-dimcolor-build \
  -R 'test_dxf_libdxfrw_(hatch_clockwise_arc|hatch_boundary_visibility|truewhite_dimension_child_colors|orphan_dimension_blocks)_run' \
  --output-on-failure
```

CADGameFusion #428 CI passed:

- validate-samples
- quick-check
- Local CI
- Ubuntu/macOS/Windows core builds
- solve-loop checks

### VemCAD

VemCAD #148 was gitlink-only (`deps/cadgamefusion` from `c01456d` to
`480e5e5`). Guardrail:

```bash
git -C deps/cadgamefusion merge-base --is-ancestor 480e5e5 origin/main
```

VemCAD #148 checks passed:

- `editor-light`
- `render-image / build-and-smoke`

The main render image rebuilt and pushed:

- run: `28307200734`
- VemCAD commit: `21f4f21285cb9fe95cbc5bed6368e10b1f9b6070`
- image: `ghcr.io/zensgit/vemcad-render:main`
- digest: `sha256:b51da00255acf8c6495655e3ae4bb62b563acc1ca0655623816a9bff65f24147`

### Local Sample Rerun

Rendered G05 with the rebuilt image:

```bash
docker run --rm \
  -v /tmp/vacadbatchinputs:/in:ro \
  -v /tmp/vemcad-fidelity-out/G05_after_clockwise_arc_fix:/out \
  --entrypoint render_cli ghcr.io/zensgit/vemcad-render:main \
  --input /in/B05.dxf \
  --out /out/G05_ours.png \
  --bg white \
  --width 2339 \
  --height 1653 \
  --report /out/G05_report.json \
  --class-mask-out /out/G05_semantic_mask.png
```

Output:

- `rendered B05.dxf -> /out/G05_ours.png (2339x1653, 5332 entities, extents clip)`
- no visible tall hatch columns in the right detail/table area

G05 comparison against AutoCAD reference:

```text
source ink IoU:             0.8575
reference-envelope ink IoU: 0.8906
color distance:             85.5
aspect delta:               0.0003
```

Compared with the #147-only state:

```text
#147 reference-envelope ink IoU: 0.8640
#148 reference-envelope ink IoU: 0.8906
delta:                         +0.0266
```

The source IoU remains limited by the known AutoCAD PLOT vs render_cli
view-space difference, so the local visual before/after is the primary evidence
for this fix.

Artifacts:

- `/tmp/vemcad-fidelity-out/G05_after_clockwise_arc_fix/G05_right_area_before_after.png`
- `/tmp/vemcad-fidelity-out/G05_after_clockwise_arc_fix/G05_full_before_after.png`
- `/tmp/vemcad-fidelity-out/batch_after_clockwise_arc_fix/compare_acad_display_reference_envelope/summary.tsv`
- `/tmp/vemcad-fidelity-out/batch_after_clockwise_arc_fix/compare_acad_display_reference_envelope/contact_vemcad.png`
- `/tmp/vemcad-fidelity-out/batch_after_clockwise_arc_fix/compare_acad_display_reference_envelope/contact_overlay.png`

## Batch Status After Fix

All 12 training drawings were re-rendered with
`ghcr.io/zensgit/vemcad-render:main@sha256:b51da002...` and compared with the
AutoCAD references using `autocad_batch_compare.py --candidate-style
acad-display --candidate-frame reference-envelope --tile-grid 6x4`.

Worst rows after the G05 hatch fix:

| id | reference-envelope ink IoU | source ink IoU | note |
|---|---:|---:|---|
| G11 | 0.8030 | 0.7742 | dimension/text/insert-text alignment and plot-style differences |
| G10 | 0.8162 | 0.7979 | mostly view-space/text-dimension differences |
| G12 | 0.8288 | 0.8234 | revision-cloud/plot-style and text-dimension differences |
| G08 | 0.8307 | 0.8113 | text/insert-text precision remains weak |
| G05 | 0.8906 | 0.8575 | hatch-stray bug fixed; remaining differences are dimension/color/framing |

No new "large geometry outside the sheet" regression was observed in the
post-fix contact sheet.

## Follow-up Boundary

The next render-fidelity work should not be another global extents or lineweight
knob. The current remaining differences are in a different class:

- explicit AutoCAD PLOT framing / paper-fill strategy;
- plot-style/color mapping for comparison and human preview;
- dimension/text/insert-text placement and lineweight fidelity.

`view=sheet` remains useful for human preview diagnostics, but it should not be
made the AutoCAD comparison default. Existing docs already record that
G11-class comparisons are not fixed by switching to `view=sheet` or by using
content bounds as the default.
