# AutoCAD Render Fidelity Development and Verification (2026-06-27)

## Goal

Compare representative training drawings in AutoCAD and VemCAD, identify the
remaining display gaps, and avoid guessing renderer fixes from a single global
score.

## Inputs

- Training DXF directory:
  `/Users/chouhua/Downloads/训练图纸/训练图纸_dxf_oda_20260123`
- Current VemCAD worktree baseline: `108c9ed`
- CADGameFusion gitlink at baseline: `312bce4`
- Render image used for corpus rendering:
  `ghcr.io/zensgit/vemcad-render:main`
- Existing AutoCAD PLOT references:
  `/tmp/vemcadautocadplot/batch/png/G01-1.png` ... `G12-1.png`

No training drawing was committed to git.

## Executed Checks

### 1. Full training corpus sheet-readiness audit

Command shape:

```bash
python3 services/render/tools/sheet_readiness_audit.py \
  --input-dir /Users/chouhua/Downloads/训练图纸/训练图纸_dxf_oda_20260123 \
  --base-url http://127.0.0.1:18077 \
  --out-dir /tmp/vemcad-fidelity-out/sheet_audit \
  --width 1800 --height 1273 --bg white --style acad-plot
```

Result:

- 110 DXF files rendered in both `view=extents` and `view=sheet`.
- 109 pass.
- 1 review: `LTJ012306102-0084调节螺栓v2.dxf`.
- Review reason: `sheet detector fell back to extents`, not blank output or
  obvious over-crop.

Key artifacts:

- `/tmp/vemcad-fidelity-out/sheet_audit/summary.json`
- `/tmp/vemcad-fidelity-out/sheet_audit/contact_sheet_01.png` ...
  `contact_sheet_07.png`

Interpretation:

- The current renderer is broadly stable over the 110-DXF corpus.
- `view=sheet` remains useful for human sheet-framing diagnostics.
- `view=sheet` is not a blanket fix for AutoCAD PLOT comparison; previous G11
  evidence and this run both support keeping X3 comparison on extents/source
  unless a specific plot-window rule is chosen.

### 2. AutoCAD PLOT comparison rerun on current renderer

The older 12-reference AutoCAD batch was rerun with the current render image.
The important correction from this run is style selection:

- `style=source` is closer to AutoCAD PLOT for display fidelity than
  `style=acad-plot`.
- `style=acad-plot` is a neutral grayscale diagnostic style, not the best
  "looks like AutoCAD" display style.

Current `source` results:

| ID | Drawing | Ink IoU | Aspect delta | Notes |
|---|---|---:|---:|---|
| G01 | `LTJ012306102-0084调节螺栓v2` | 0.8816 | 0.0003 | good group |
| G02 | `BTJ01239901522-00拖轮组件v2` | 0.8792 | 0.0004 | good group |
| G03 | `BTJ01231501522-00短轴承座(盖)v2` | 0.9080 | 0.0003 | best group |
| G04 | `J2925001-00再沸器v2` | 0.6664 | 0.0035 | dense table/text/linework outlier |
| G05 | `J0724006-05上封头组件v1` | 0.8241 | 0.0010 | style/linework residual |
| G06 | `J2825003-05下筒体组件v2` | 0.8965 | 0.0003 | best group |
| G07 | `J2925001-05管束v2` | 0.8453 | 0.0003 | good group, dense content |
| G08 | `J0224070-04-07捕集口v1` | 0.8113 | 0.0006 | style/linework residual |
| G09 | `BTJ01239601522-03扭转弹簧v1` | 0.8644 | 0.0006 | good group |
| G10 | `J0225004-04-05下封板v2` | 0.7980 | 0.0015 | style/linework residual |
| G11 | `J2925004-04-01底板v2` | 0.3464 | 0.0575 | view-space/framing outlier |
| G12 | `比较_LTJ012306102-0084...` | 0.8256 | 0.0005 | good group |

Artifacts:

- `/tmp/vemcad-fidelity-out/current_x3_source/summary.json`
- `/tmp/vemcad-fidelity-out/current_x3_source/contact_ours.png`
- `/tmp/vemcad-fidelity-out/current_x3_source/contact_overlay.png`

### 3. Lineweight experiment

A post-render min-filter thickening experiment was run to test whether global
lineweight was the main gap.

Result:

- 1 px thickening improves some drawings:
  - G06: 0.8965 -> 0.9363
  - G03: 0.9080 -> 0.9230
- It regresses others:
  - G01: 0.8816 -> 0.7691
  - G10: 0.7980 -> 0.7540
- G04 improves only modestly: 0.6664 -> 0.6954.
- G11 remains bad: 0.3464 -> 0.3747.

Conclusion: do not apply a global lineweight multiplier. The issue is
drawing/style dependent.

### 4. Render-cli content-bounds experiment

G11 report showed:

```json
{
  "clip": {"min_x": -125, "min_y": -25, "max_x": 925, "max_y": 1460},
  "content_bbox": {"min_x": -125, "min_y": -25, "max_x": 1036.38864021677, "max_y": 1460}
}
```

This proves G11 has real content outside the header-derived clip. A local
CADGameFusion experiment changed render_cli default extents to
`union(header_extents, content_bbox)`.

Verification:

- Local `render_cli` build succeeded.
- New stale-header regression test passed locally.
- G11 improved only slightly: 0.3464 -> 0.3505.
- G04 and G05 regressed badly:
  - G04: 0.6664 -> 0.4229
  - G05: 0.8241 -> 0.2325

Conclusion: do not ship `union(header, content_bbox)` as the default. Some
drawings contain far-away real content that AutoCAD PLOT does not use for the
main sheet window. The right fix is a plot-window decision, not a default extents
rewrite.

## Tooling Added

`tools/render_regression/autocad_batch_compare.py`

The tool takes a JSON list of AutoCAD PNG and VemCAD PNG pairs and writes:

- `summary.json`
- `summary.tsv`
- `overlays/*.png`
- `contact_autocad.png`
- `contact_vemcad.png`
- `contact_overlay.png`

It keeps customer/training drawings out of git while making the comparison
method repeatable.

Self-check:

```bash
python3 -m py_compile tools/render_regression/autocad_batch_compare.py
python3 tools/render_regression/autocad_batch_compare.py \
  --cases /tmp/vemcad-fidelity-out/current_x3_source/cases.json \
  --out-dir /tmp/vemcad-fidelity-out/autocad_batch_tool_check
```

Result:

- 12 AutoCAD/VemCAD PNG pairs processed.
- `summary.tsv`, `summary.json`, 12 overlays, and the three contact sheets were
  generated.
- The reproduced scores match the current `source` comparison run; the tool is
  diagnostic and intentionally does not turn visual closeness into a formal
  `PASS >= 0.97` claim.

## Current Development Plan

### P0: Plot-window strategy for G11-class drawings

Do not default render_cli to content-bounds union. Instead, design an explicit
AutoCAD PLOT window strategy:

- source of truth: AutoCAD PLOT "Extents / Fit / Center" behavior, not GUI
  screenshot;
- likely candidates: header clip, content bbox, sheet detector, or a detected
  plot-frame/layout window;
- gate: improve G11 without regressing G04/G05.

### P1: Dense table/text/linework for G04-class drawings

G04 is not a framing outlier; aspect is close. The remaining gap is dense
annotation/table/linework style. Next diagnostics should split:

- text/table ink;
- dimensions;
- hatch;
- ordinary geometry;
- layer/color/lineweight contribution.

Do not apply a global lineweight multiplier.

### P2: Source style as the default for AutoCAD-like display comparison

Use `style=source` for AutoCAD display-fidelity comparisons. Keep
`style=acad-plot` as a neutral grayscale diagnostic style.

## Boundary

This slice does not mark the corpus "AutoCAD-equivalent". The strongest current
group is visually close, but the formal X3 `PASS >= 0.97` threshold is not met.
The next renderer change should be gated by improvement on G11 or G04 without
regressing the good group.
