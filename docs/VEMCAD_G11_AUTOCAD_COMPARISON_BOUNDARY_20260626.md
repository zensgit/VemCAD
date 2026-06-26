# VemCAD G11 AutoCAD Comparison Boundary (2026-06-26)

## Status

G11 (`J2925004-04-01_v2`, source DXF staged locally as `B11.dxf`) remains a real
AutoCAD-vs-VemCAD comparison outlier, but the failure is not explained by a
single safe renderer patch. The current evidence says the next safe step is to
improve view-space/text-layout diagnostics before changing rendering behavior.

This note intentionally does not mark G11 as passing and does not relax the
`compare_vs_acad.py` gate threshold.

## Baseline Evidence

AutoCAD reference:

- PNG: `/tmp/vemcadautocadplot/batch/png/G11-1.png`
- Size: `2339x1653`
- Capture path: clean AutoCAD PLOT/PNG export from the local batch run.

VemCAD reference:

- DXF: `/tmp/vacadbatchinputs/B11.dxf`
- Extents render: `/tmp/vemcad-g11-framing-out/G11_extents_render_cli.png`
- Render report: `/tmp/vemcad-g11-framing-out/G11_extents_report.json`

Baseline X3 result, AutoCAD first:

```text
ink IoU      : 0.3535
SSIM         : 0.1245
color dist   : 128.3
aspect delta : 0.0573
band         : fallback
```

The previously generated 12-drawing batch showed G11 as the dominant outlier:

```text
G11  ink IoU 0.3393  aspect delta 0.0573
```

## Ruled-Out Causes

### 1. Stale Header Extents Are Real, But Not the G11 Fix

The render report shows the DXF header clip is stale-small in X:

```json
"clip": {
  "min_x": -125,
  "min_y": -25,
  "max_x": 925,
  "max_y": 1460
},
"content_bbox": {
  "min_x": -125,
  "min_y": -25,
  "max_x": 1036.38864021677,
  "max_y": 1460
}
```

However, rendering G11 in the full `content_bbox` window did not improve the
AutoCAD comparison:

```text
current extents render       ink IoU 0.3535
content_bbox window render   ink IoU 0.3424
```

So the stale header remains a valid class of issue, but it is not the main
explanation for G11.

### 2. Resolution Mismatch Is Not the Main Cause

The original VemCAD batch render was `1600x1131`, while AutoCAD exported
`2339x1653`. Re-rendering VemCAD at AutoCAD's exact size still failed:

```text
render_cli --width 2339 --height 1653
ink IoU      : 0.3387
SSIM         : 0.0769
color dist   : 129.7
aspect delta : 0.0575
band         : fallback
```

### 3. `view=sheet` Is Worse For This AutoCAD Plot Baseline

`view=sheet` is useful for drawings with stray entities outside the sheet frame,
but it is not the right baseline for this G11 AutoCAD PLOT comparison:

```text
view=sheet ink IoU      : 0.2677
view=sheet aspect delta : 0.0738
```

Keep `view=sheet` as a preview/framing diagnostic, not as the default fix for
AutoCAD plot equivalence.

### 4. Simple Ink Thickening Is Not Enough

Post-processing VemCAD with increasingly thick min-filters only gave a small
increase:

```text
minfilter 3  ink IoU 0.3711
minfilter 5  ink IoU 0.3627
minfilter 7  ink IoU 0.3607
minfilter 9  ink IoU 0.3687
```

This rules out a simple global lineweight/font-weight multiplier as the safe
first fix.

### 5. No Single Display-Color Layer Explains The Failure

After the comparator's standard crop/resize/shift, every major color layer is
poorly aligned:

```text
dark     f1=0.1832  ours/acad pixel ratio=0.43
green    f1=0.0842  ours/acad pixel ratio=0.81
red      f1=0.0451  ours/acad pixel ratio=0.78
yellow   f1=0.1908  ours/acad pixel ratio=0.81
cyan     f1=0.0989  ours/acad pixel ratio=1.56
magenta  f1=0.0905  ours/acad pixel ratio=0.79
```

This is not isolated to one display color. The manual split above has since
been productized as `compare_vs_acad.py --class-report --print-classes` in
PR #109, which reproduces the same class-level conclusion while keeping the
main X3 gate semantics unchanged.

This still does not prove which CAD entity class is wrong: display colors are
diagnostic buckets, not semantic masks for text, dimensions, hatches, ordinary
geometry, or title-block attributes.

## Text / Title-Block Findings

G11 is heavily text/title-block driven. A raw DXF pass found 215 text-like
entities, but most are block definitions or attribute material rather than
direct modelspace text.

Important facts:

- Direct visible modelspace `TEXT/MTEXT`: 1 `MTEXT`
- Top-level inserts: `*U15`, `*U17`, `HC_BTL_BLK`
- `HC_BTL_BLK` has 16 ATTRIB values, including title metadata such as:
  - `底板`
  - `J2925004-04-01`
  - `1:5`
  - `S30408`
  - `12.15`
- The CADGameFusion libdxfrw fork parses `ATTRIB/ATTDEF` through `processAttrib()`
  and calls `iface->addText(txt)` for non-empty values, so this is not simply
  "all attributes are missing".
- The render report currently records `text_entities=39`, which is plausible
  after filtering to visible/renderable document text, expanded inserts, and
  dimension blocks.

The visual difference still strongly involves title-block and annotation
geometry: VemCAD and AutoCAD show the same drawing, but the effective framing,
text density, and per-layer registration differ enough that global ink overlap
is not meaningful as a single actionable signal.

## Correct Boundary

Do not implement a broad renderer tweak from G11's global IoU alone.

Specifically, do not:

- switch AutoCAD comparison to `view=sheet` by default;
- use header `clip` or existing report `clip` as a "robust" substitute for
  geometry content bounds;
- add a global text-size, font-weight, or lineweight multiplier based only on
  this drawing;
- mark the drawing as AutoCAD-equivalent while the X3 score is in fallback.

## Recommended Next Slice

The display-color diagnostic is now available, and it confirms G11 is not a
single visible-color failure. The next developable slice should add true
renderer-supplied semantic evidence, then use that evidence to choose a renderer
fix:

1. Add a render/report diagnostic that separates text, dimensions, hatches,
   ordinary geometry, and title-block/attribute text in the output.
2. Extend the X3 comparison report to emit per-semantic-class scores using
   those masks instead of only the combined ink IoU or display-color buckets.
3. Re-run G11 with those semantic masks.
4. Only then choose a narrow fix, likely one of:
   - MTEXT/ATTRIB attachment or wrapping refinement;
   - title-block attribute placement/scale refinement;
   - plot-style lineweight mapping;
   - a stricter AutoCAD export/window contract if the current PLOT baseline is
     not in the same semantic view-space as `render_cli`.

This keeps the G11 target honest: the goal is not "make one raster overlap by
guessing"; it is "identify the mismatching render class and fix that class
without regressing the 12-drawing batch."

## Semantic Mask Diagnostic Path

The renderer-side shape for that next slice is a single class-buffer pass, not
N separate per-class renders:

1. `render_cli --class-mask-out <png> --report <json>` emits the normal colour
   render and a candidate-side semantic class buffer in the exact same view.
2. The report's `semantic_classes.palette` gives the reserved colours for
   renderer-owned classes such as ordinary geometry, direct text, dimensions,
   hatches, and insert/title-block text.
3. `compare_vs_acad.py --semantic-mask <png> --semantic-render-report <json>`
   scores each candidate class against AutoCAD's total ink after the same X3
   alignment.

This is still diagnostic, not a new gate: AutoCAD reference semantics are
unknown, so the report exposes candidate-class `precision` and AutoCAD
`reference_coverage` instead of claiming a true per-semantic-class IoU.
