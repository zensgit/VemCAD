# VemCAD G11 Tile/Semantic Residual Boundary (2026-06-28)

## Status

This is the follow-up diagnosis after the render/font line reached VemCAD
`b6aa26f` and CADGameFusion `234ea72` (`romans.shx + hzdx.shx` baseline
tuning). It answers a narrower question than the earlier G11 boundary notes:

> After view-space normalization (`candidate-frame=reference-envelope`) and
> semantic masks, is there a low-risk renderer tweak that should be shipped next?

The answer is **no**. The newest evidence is useful and actionable, but it does
not justify another renderer change yet. The remaining G11 residual is split
between:

- bottom title-block / attribute text (`text` + `insert_text`);
- dimension text near the main view (`dimension`);
- ordinary geometry and global registration in the bottom/title-frame area.

Those are different mechanisms. A single global text, lineweight, clipping, or
view-mode tweak either barely moves G11 or regresses other drawings.

This note does not mark G11 as AutoCAD-equivalent and does not relax any X3
threshold.

## Repro

Artifacts were generated locally from the current render image:

- image: `ghcr.io/zensgit/vemcad-render:main`
- digest: `sha256:d0f07072ff9581bb1e752455b9463f5c0c6edfb5ee556fcf22840c282d4863bf`
- DXF: `/tmp/vacadbatchinputs/B11.dxf`
- AutoCAD reference: `/tmp/vemcadautocadplot/batch/png/G11-1.png`
- output root: `/tmp/vemcad-fidelity-out/g11_goal_semantic_tile_current/`

Render command:

```bash
docker run --rm \
  -v /tmp/vacadbatchinputs:/in:ro \
  -v /tmp/vemcad-fidelity-out/g11_goal_semantic_tile_current/renders:/out \
  --entrypoint render_cli ghcr.io/zensgit/vemcad-render:main \
  --input /in/B11.dxf \
  --out /out/G11_ours.png \
  --bg white \
  --width 2339 \
  --height 1653 \
  --report /out/G11_report.json \
  --class-mask-out /out/G11_semantic_mask.png
```

Compare command:

```bash
python3 tools/render_regression/autocad_batch_compare.py \
  --cases /tmp/vemcad-fidelity-out/g11_goal_semantic_tile_current/semantic_cases.json \
  --out-dir /tmp/vemcad-fidelity-out/g11_goal_semantic_tile_current/compare \
  --candidate-style acad-display \
  --candidate-frame reference-envelope \
  --tile-grid 6x4
```

Tile panels used for human inspection:

```text
/tmp/vemcad-fidelity-out/g11_goal_semantic_tile_current/tile_panels_v2/
```

Each panel contains aligned AutoCAD, aligned VemCAD, red/green overlay, and the
candidate semantic mask.

## Overall Score

The reference-envelope diagnostic keeps the view-space envelope identical before
scoring:

```text
ink_iou          0.8262
source_ink_iou   0.8021
delta_ink_iou   +0.0241
color_dist       97.5
aspect_delta      0.0
framing_mismatch false
band             fallback
```

This is better than the source render but still below the X3 pass/review target.
It is diagnostic evidence only; `candidate-frame=reference-envelope` is not a
production render mode.

## Semantic Class Summary

Candidate-side semantic classes are now populated, unlike the first G11 semantic
attempt:

```text
geometry     px 23015  precision 0.9295  reference_coverage 0.6097
dimension    px 11438  precision 0.4830  reference_coverage 0.1202
insert_text  px  3842  precision 0.6593  reference_coverage 0.0656
text         px  2368  precision 0.4413  reference_coverage 0.0184
hatch        px   642  precision 1.0000  reference_coverage 0.0232
other        px    30  precision 0.7000  reference_coverage 0.0018
```

Important reading: `precision` and `reference_coverage` are still
candidate-class-vs-total-AutoCAD-ink metrics. AutoCAD reference semantics are
unknown, so these rows identify where our candidate class lands, not a true
per-class AutoCAD IoU.

## Worst Tiles

The worst tiles by severity are:

| tile | ink_iou | ref_px | cand_px | missing | extra | interpretation |
|---|---:|---:|---:|---:|---:|---|
| row 3 col 5 | 0.7061 | 3618 | 3195 | 1379 | 569 | bottom-right title block/date area; text + insert_text residual with aligned geometry |
| row 3 col 4 | 0.7699 | 3492 | 4477 | 854 | 963 | title block text/attributes; candidate text appears heavier and shifted/wider |
| row 3 col 2 | 0.7954 | 3001 | 3437 | 756 | 519 | bottom title/company area; insert_text + geometry |
| row 3 col 3 | 0.6833 | 2023 | 1767 | 874 | 252 | title block/company text; text residual dominates the human read |
| row 2 col 3 | 0.6308 | 1094 | 1911 | 150 | 961 | main-view dimension text, especially `190X3=570`; dimension placement/font-width residual |

The row-3 tiles are mostly title-block/attribute text plus table geometry. The
row-2 col-3 tile is a different class: dimension text and dimension geometry near
the main view. That split is why a single global tweak is unsafe.

## Visual Findings

The tile panels show:

1. **Bottom/right title block**: AutoCAD's text is lighter and lands differently
   from VemCAD's title-block text. The semantic mask shows `text` and
   `insert_text`, with ordinary table geometry already aligned well in many
   subregions.
2. **Main-view dimension text**: `190X3=570` and nearby dimension labels land
   lower/wider in VemCAD than in AutoCAD. These are `dimension` records using
   `HGCAD.SHX/HGCADHZ.SHX`.
3. **Global registration remains visible** even after reference-envelope
   framing: some red/green pairs fan through the ellipse and frame. That points
   to view/capture semantics and text/layout together, not one glyph bug.

## Ruled-Out Candidate Tweaks

These are not safe next fixes:

- **content_bbox / full geometry window**: already tested in
  `VEMCAD_G11_AUTOCAD_COMPARISON_BOUNDARY_20260626.md`; it did not improve G11
  and severely degrades some other corpus drawings when used as a generic X3
  mode.
- **view=sheet**: useful for human preview and stray-entity drawings, but worse
  for this AutoCAD PLOT reference.
- **global ink thickening / lineweight multiplier**: previous min-filter probes
  produced only small movement and do not explain semantic split.
- **disable `romans/hzdx` overdraw globally**: a local experiment moved G11
  slightly upward (`0.8262 -> 0.8286`) but regressed the 12-drawing batch average
  and badly hurt G04 (`-0.0446`). That is not a safe renderer change.
- **global `romans/hzdx` width or baseline adjustment**: existing local probes
  moved G11 only marginally and had mixed corpus impact.

## Boundary

Do not ship another renderer tweak from the G11 aggregate score alone.

Before changing rendering behavior, the next implementation must target one
specific class and prove corpus impact:

1. **Dimension text slice**: HGCAD dimension text placement/width for row2-col3
   style cases. This needs a fixture or corpus check proving the fix helps
   dimension text without moving regular title-block text.
2. **Title-block/insert_text slice**: attribute/title-block text weight and
   alignment for `$TD_AUDIT_GENERATED_(345)` / `romans.shx + hzdx.shx`. Existing
   overdraw removal is not safe; a narrower rule would need its own evidence.
3. **View-space / AutoCAD PLOT contract slice**: if the AutoCAD reference is not
   truly in the same model-window semantics as `render_cli`, fix the capture or
   explicit window contract rather than trying to tune pixels.

Until one of those narrower slices is selected, G11 remains an honest outlier
with useful diagnostics, not a pass.
