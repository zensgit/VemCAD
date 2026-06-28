# VemCAD G11 HGCAD Dimension Text Probe (2026-06-28)

## Status

This is the narrow follow-up to
`VEMCAD_G11_TILE_SEMANTIC_RESIDUAL_BOUNDARY_20260628.md`: test whether the
G11 row2/col3 residual can be safely explained by `source_type=DIMENSION` text
using the `HGCAD.SHX/HGCADHZ.SHX` style.

Result: **no renderer change should ship from this slice.**

The probe found real HGCAD dimension text in the suspicious region, but
idealized pixel experiments show that moving only HGCAD dimension text, or even
all dimension-class ink, does not materially improve the X3 score. The residual
is therefore not a simple HGCAD baseline/placement bug.

## Inputs

- VemCAD main before this note: `95e17f8`
- CADGameFusion render layer consumed by VemCAD: `234ea72`
- render image: `ghcr.io/zensgit/vemcad-render:main`
- image digest observed locally:
  `sha256:d0f07072ff9581bb1e752455b9463f5c0c6edfb5ee556fcf22840c282d4863bf`
- DXF: `/tmp/vacadbatchinputs/B11.dxf`
- AutoCAD reference: `/tmp/vemcadautocadplot/batch/png/G11-1.png`
- diagnostic root:
  `/tmp/vemcad-fidelity-out/g11_goal_semantic_tile_current/`

The comparison mode is the same as the prior boundary note:

```text
candidate-style: acad-display
candidate-frame: reference-envelope
tile-grid:       6x4
base ink_iou:    0.8262
```

## Why HGCAD Dimension Text Was Plausible

The worst non-title-block tile is row2/col3:

```text
row 2 col 3
ink_iou 0.6308
ref_px 1094
cand_px 1911
missing 150
extra 961
```

Candidate semantic contribution in that tile:

```text
dimension px 1227  precision 0.1548  reference_coverage 0.1764
geometry  px  950  precision 0.6737  reference_coverage 0.7093
```

The render report confirms nearby HGCAD dimension text records, all with
`render_baseline_adjust_px=0`:

```text
entity 191  x=1199.38  y=980.55  style=HGCAD  font=HGCAD.SHX/HGCADHZ.SHX  width_factor=0.75
entity 202  x=1535.27  y=980.55  style=HGCAD  font=HGCAD.SHX/HGCADHZ.SHX  width_factor=0.75
entity 224  x=1173.37  y=901.73  style=HGCAD  font=HGCAD.SHX/HGCADHZ.SHX  width_factor=0.75
```

Visually, the `190X3=570` style dimension label looked slightly misplaced, so
an HGCAD-dimension-only baseline adjustment was the right first hypothesis.

## Probe 1: Shift Only Estimated HGCAD Dimension Text Rectangles

Method:

- use `text_placement.records` to find `semantic_class=dimension` records whose
  font provenance contains `HGCAD`;
- map source render screen coordinates through the reference-envelope transform;
- inside each small text rectangle, move only pixels whose semantic mask class is
  `dimension`;
- compare each modified candidate against the same AutoCAD reference.

Result:

```text
base 0.8262
dy -12  0.8261  delta -0.0001
dy -10  0.8262  delta +0.0000
dy  -8  0.8261  delta -0.0001
dy  -6  0.8260  delta -0.0002
dy  -4  0.8262  delta +0.0000
dy  -3  0.8263  delta +0.0001
dy  -2  0.8263  delta +0.0001
dy  -1  0.8264  delta +0.0002
dy  +1  0.8260  delta -0.0002
dy  +2  0.8262  delta +0.0000
dy  +3  0.8261  delta -0.0001
dy  +4  0.8264  delta +0.0002
dy  +6  0.8263  delta +0.0001
dy  +8  0.8261  delta -0.0001
dy +10  0.8262  delta +0.0000
dy +12  0.8262  delta +0.0000
```

Maximum movement is noise-level (`+0.0002`), not an actionable fix.

## Probe 2: Shift All Dimension-Class Ink

As an upper-bound sanity check, shift all pixels in the reference-framed semantic
`dimension` class. This is intentionally too broad and would not be a shippable
fix, but it tests whether dimension-class registration is the dominant X3 lever.

Result:

```text
base 0.8262
dx +0 dy -8  0.8258  delta -0.0004
dx +0 dy -4  0.8262  delta +0.0000
dx +0 dy -2  0.8264  delta +0.0002
dx +0 dy +2  0.8262  delta +0.0000
dx +0 dy +4  0.8264  delta +0.0002
dx +0 dy +8  0.8258  delta -0.0004
dx -4 dy +0  0.8261  delta -0.0001
dx -2 dy +0  0.8263  delta +0.0001
dx +2 dy +0  0.8263  delta +0.0001
dx +4 dy +0  0.8261  delta -0.0001
```

Again, no meaningful improvement.

## Conclusion

Do not add an HGCAD dimension baseline offset or width tweak from G11. The
evidence does not support it.

The next productive direction is not another `HGCAD.SHX` pixel tweak. It should
be one of:

1. **title-block / insert_text measurement**: the worst tiles are row3 title
   block areas with `text + insert_text + table geometry`, and they still carry
   visible weight/placement differences;
2. **AutoCAD PLOT view-space contract**: G11 remains sensitive to plot/reference
   framing semantics even after reference-envelope diagnostics;
3. **better text diagnostics**: add a non-sensitive per-text placement probe that
   can compare expected text boxes without exposing drawing text values.

Until then, G11 remains an honest, diagnosed outlier rather than a renderer patch
target.
