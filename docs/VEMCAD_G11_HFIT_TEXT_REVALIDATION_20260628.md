# VemCAD G11 HFit Text Revalidation (2026-06-28)

## Purpose

This note records the follow-up slice after the G11 title-block/semantic tile
diagnosis found a tempting but unproven signal: shifting bottom/title
`insert_text` left by roughly 4-6 pixels improved the diagnostic score by about
`+0.021`.

The concrete renderer question was:

> Is G11's title-block residual caused by libdxfrw `HFit` text being anchored at
> the second alignment point instead of the base point?

## What Shipped

CADGameFusion PR #435 fixed the real `HFit` semantics in
`plugins/dxf_libdxfrw_adapter.cpp`:

- `DRW_Text::HFit` now keeps the base point as the draw origin.
- The second point is used as the requested fit span.
- The effective text width factor is adjusted from the requested span instead of
  treating the second point as the origin.
- `HAligned` was intentionally left unchanged because it has different height /
  aspect semantics and was not proven by this slice.

VemCAD PR #159 consumed that fix with a gitlink-only bump:

- `deps/cadgamefusion`: `234ea72` -> `590cbf2`
- VemCAD `render-image` rebuilt and pushed `ghcr.io/zensgit/vemcad-render:main`
  after the bump.

## Verification

Local / CI verification:

- CADGameFusion #435: full CI passed, including Windows/macOS/Ubuntu core/build,
  Local CI, quick-check, validate-samples, and solve checks.
- VemCAD #159: `editor-light` and `build-and-smoke` passed.
- VemCAD main `render-image` passed after #159 and pushed the rebuilt main image.
- A minimal `HFit` DXF rendered through the rebuilt image reports
  `text_effective_width_factor = 5.000000`, proving the image contains the fix.

G11 revalidation used the rebuilt image:

```bash
docker run --rm \
  -v /tmp/vacadbatchinputs:/in:ro \
  -v /tmp/vemcad-fidelity-out/g11_hfit_20260627T235144/renders:/out \
  --entrypoint render_cli ghcr.io/zensgit/vemcad-render:main \
  --input /in/B11.dxf \
  --out /out/G11_ours.png \
  --bg white \
  --width 2339 --height 1653 \
  --report /out/G11_report.json \
  --class-mask-out /out/G11_semantic_mask.png
```

The AutoCAD comparison was then rerun with the same diagnostic mode used by the
prior G11 tile work:

```bash
python3 tools/render_regression/autocad_batch_compare.py \
  --cases /tmp/vemcad-fidelity-out/g11_hfit_20260627T235144/semantic_cases.json \
  --out-dir /tmp/vemcad-fidelity-out/g11_hfit_20260627T235144/compare/batch \
  --candidate-style acad-display \
  --candidate-frame reference-envelope \
  --tile-grid 6x4
```

## Result

The G11 output is unchanged by the `HFit` fix:

| Metric | Before | After |
| --- | ---: | ---: |
| batch `ink_iou` | `0.8262` | `0.8262` |
| batch `ssim` | `0.5288` | `0.5288` |
| batch `color_dist` | `97.5` | `97.5` |
| source `ink_iou` | `0.8021` | `0.8021` |

The old and new G11 PNGs are pixel-identical. The old and new render reports are
also semantically identical for the visible G11 text-placement records.

Why: the visible G11 `insert_text` records in `render_cli`'s report do not enter
the `HFit` path. They report empty alignment fields and stable generated style
width factors, for example:

- `semantic_class = insert_text`
- `source_type = INSERT`
- `text_style = $TD_AUDIT_GENERATED_(345)`
- `text_font_file = romans.shx`
- `text_bigfont_file = hzdx.shx`
- `text_effective_width_factor = 0.490000`
- `halign = ""`
- `valign = ""`

Raw `ATTRIB`/`ATTDEF` `72=5` records do exist in `B11.dxf`, but they are not the
rendered `insert_text` records that dominate the current G11 title-block
residual. The current visible residual is therefore not explained by the
`HFit` origin bug.

## Boundary

This slice is a valid CAD correctness fix, but **not** a G11 score-improvement
fix. Do not claim G11 has improved from #435/#159, and do not retry HFit as the
next G11 lever.

G11 remains in the same honest state as before:

- the baseline comparison is still below the X3 pass threshold;
- source-mode still reports a view-space / framing mismatch;
- reference-envelope diagnostics still show title-block/text residuals;
- the residual should not be hidden by a magic offset or global font/width
  multiplier.

## Next Useful Slice

If continuing G11, the next slice should target one of these narrower questions:

1. **AutoCAD PLOT view-space contract** — produce a reference whose model window
   is known to match `render_cli`, or render with an explicit matching window.
   This addresses the persistent source-mode `NOT COMPARABLE` verdict.
2. **Static block text / MTEXT provenance** — expose enough report fields to
   distinguish block `TEXT`, `MTEXT`, `ATTRIB`, and `ATTDEF` paths in the visible
   title block. G11 currently shows `insert_text` records without the alignment
   metadata needed to choose a safe renderer correction.
3. **Local font-metrics probe for the title block** — compare measured rendered
   text extents against the cell/grid geometry before changing renderer
   behavior. Any shift/scale change must be justified by entity-level evidence,
   not only by aggregate X3 movement.

Until one of those is selected, the renderer line should stay closed at the
current verified state.
