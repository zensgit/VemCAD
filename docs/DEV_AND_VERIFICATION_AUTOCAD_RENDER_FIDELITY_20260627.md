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

### 4. AutoCAD-like display style probe

A narrower post-render probe mapped only low-saturation grey linework to black,
while preserving saturated CAD colours. This targets AutoCAD's common
plot/display treatment for table/grid strokes without turning the render into a
full grayscale diagnostic and without changing geometry.

Result on the 12 AutoCAD PLOT references:

| ID | Ink IoU before | Ink IoU after | Color dist before | Color dist after |
|---|---:|---:|---:|---:|
| G01 | 0.8816 | 0.8818 | 87.3 | 19.7 |
| G02 | 0.8792 | 0.8867 | 113.2 | 68.9 |
| G03 | 0.9080 | 0.9081 | 78.3 | 5.7 |
| G04 | 0.6664 | 0.6682 | 58.4 | 43.4 |
| G05 | 0.8241 | 0.8245 | 86.8 | 59.8 |
| G06 | 0.8965 | 0.8967 | 91.0 | 12.1 |
| G07 | 0.8453 | 0.8456 | 99.7 | 55.2 |
| G08 | 0.8113 | 0.8114 | 96.7 | 32.7 |
| G09 | 0.8644 | 0.8656 | 81.2 | 23.7 |
| G10 | 0.7980 | 0.7981 | 54.5 | 8.8 |
| G11 | 0.3464 | 0.3567 | 131.2 | 31.4 |
| G12 | 0.8256 | 0.8259 | 61.9 | 17.4 |

There were no Ink-IoU regressions in this probe. The improvement is mostly in
display colour distance, with small positive IoU movement. This is suitable as
an opt-in display style, not as a geometry fix and not as an AutoCAD-equivalent
claim.

Implemented as `style=acad-display`:

- default `style=source` remains unchanged;
- `style=acad-plot` remains the existing neutral grayscale diagnostic;
- `style=acad-display` preserves saturated source colours and only darkens
  neutral grey linework.

### 5. Render-cli content-bounds experiment

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

### Semantic class diagnostics

The batch tool now also accepts optional `semantic_mask` and `semantic_report`
fields per case. These are render_cli's candidate-side semantic class buffer and
report (`--class-mask-out` + `--report`). When present, the tool writes:

- `semantic_summary.json`
- `semantic_summary.tsv`

The rows report candidate class precision and AutoCAD reference coverage for
renderer-owned classes. This remains diagnostic: AutoCAD's semantic masks are
unknown, so these are not true per-class IoU gates.

Self-check on the current G04/G11 outliers:

```bash
python3 tools/render_regression/autocad_batch_compare.py \
  --cases /tmp/vemcad-fidelity-out/semantic_probe_20260627120422/semantic_cases.json \
  --out-dir /tmp/vemcad-fidelity-out/semantic_batch_tool_check
```

Result:

- 2 AutoCAD/VemCAD PNG pairs processed.
- 12 semantic class rows generated.
- G04 splits into multiple contributors instead of one root cause:
  - geometry precision: 0.6733
  - text precision: 0.7586
  - hatch precision: 0.4239
- G11 remains a combined view-space/registration problem:
  - geometry precision: 0.3278
  - text precision: 0.3959

This is the actionable read: G04 is not just a global lineweight problem, and
G11 is not fixed by changing the default extents window.

### G11 window scan

A small render_cli window scan was run against G11 after the unsafe
`union(header, content_bbox)` result above:

| Window | Ink IoU | Aspect delta | Result |
|---|---:|---:|---|
| extents | 0.3464 | 0.0575 | baseline |
| no-clip | 0.3464 | 0.0575 | no change |
| content_bbox window | 0.3534 | 0.0564 | tiny improvement only |
| taller header window | 0.3333 | 0.0561 | worse |

Conclusion: there is no obvious safe G11 plot-window tweak in this family.
Keep plot-window changes gated by multi-drawing evidence; do not make
`content_bbox` or `sheet` the AutoCAD comparison default.

## Current Development Plan

### P0: Plot-window strategy for G11-class drawings

Do not default render_cli to content-bounds union. Do not switch X3 to
`view=sheet`. The current G11 window scan found no safe plot-window family that
meaningfully improves G11. If this line continues, design an explicit AutoCAD
PLOT window strategy:

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

### P2: Style selection for AutoCAD-like display comparison

Use styles deliberately:

- `style=source`: source-colour baseline and default render-service behavior.
- `style=acad-display`: AutoCAD-like display review; preserves saturated CAD
  colours but maps neutral grey linework to black.
- `style=acad-plot`: neutral grayscale diagnostic style, not the closest
  AutoCAD-like display style for this batch.

## Boundary

This slice does not mark the corpus "AutoCAD-equivalent". The strongest current
group is visually close, but the formal X3 `PASS >= 0.97` threshold is not met.
The next renderer change should be gated by improvement on G11 or G04 without
regressing the good group.
