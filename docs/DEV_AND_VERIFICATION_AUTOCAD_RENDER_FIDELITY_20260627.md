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

### 4b. AutoCAD PLOT framing implementation check

The AutoCAD references in `/tmp/vemcadautocadplot/batch` are clean PLOT PDFs
generated by `batch2.scr`, not ad-hoc screenshots. The script uses:

```text
DWG To PDF.pc3, A4 landscape, Extents, Fit, Center, acad.ctb
```

So the fair comparison problem is not "get a cleaner screenshot"; it is that
AutoCAD PLOT frames model extents onto an A4 paper/printable area, while
render_cli's plain `view=extents` adds its own larger viewport margin. The
current `autocad_batch_compare.py` correctly surfaces that as a framing
mismatch:

```text
framing mismatches: 12
```

The implemented `view=acad-plot` service path reframes the existing VemCAD
render to the observed AutoCAD PLOT paper-fill envelope and then can be paired
with `style=acad-display`. It does not touch CAD geometry; it only removes the
paper-framing mismatch before comparison.

Result:

| ID | Base IoU | `style=acad-display` IoU | plot-frame + display IoU | Base color | Plot-frame + display color |
|---|---:|---:|---:|---:|---:|
| G01 | 0.8816 | 0.8818 | 0.8816 | 87.3 | 24.1 |
| G02 | 0.8792 | 0.8867 | 0.8974 | 113.2 | 72.9 |
| G03 | 0.9080 | 0.9081 | 0.9117 | 78.3 | 10.6 |
| G04 | 0.6664 | 0.6682 | 0.6745 | 58.4 | 47.9 |
| G05 | 0.8241 | 0.8245 | 0.8498 | 86.8 | 69.3 |
| G06 | 0.8965 | 0.8967 | 0.9258 | 91.0 | 14.5 |
| G07 | 0.8453 | 0.8456 | 0.8653 | 99.7 | 58.4 |
| G08 | 0.8113 | 0.8114 | 0.8309 | 96.7 | 47.1 |
| G09 | 0.8644 | 0.8656 | 0.8665 | 81.2 | 33.7 |
| G10 | 0.7980 | 0.7981 | 0.8193 | 54.5 | 14.6 |
| G11 | 0.3464 | 0.3567 | 0.3750 | 131.2 | 32.0 |
| G12 | 0.8256 | 0.8259 | 0.8204 | 61.9 | 23.2 |

The implementation check reduced framing mismatches from 12/12 to 2/12. This
is strong enough as an opt-in render-service view, but not as the default: G04
and G11 still need deeper diagnostics after the paper-frame mismatch is
removed.

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

The batch tool also has a diagnostic-only candidate frame mode:

```bash
python3 tools/render_regression/autocad_batch_compare.py \
  --cases /tmp/vemcad-fidelity-out/current_x3_source/cases.json \
  --out-dir /tmp/vemcad-fidelity-out/reference_envelope_tool_check \
  --candidate-frame reference-envelope
```

This writes temporary candidate PNGs into the output directory, frames VemCAD ink
into each AutoCAD PNG's ink envelope, and records the original candidate as
`source_ours`. It is not a render-service mode and not a gate; it is a diagnostic
to answer whether a low score survives after the known paper/capture envelope
difference is removed.

Current 12-case check:

- framing mismatches: `12/12 -> 0/12`
- G04: `0.6745` (`view=acad-plot + style=acad-display`) -> `0.6762`
- G11: `0.3750` (`view=acad-plot + style=acad-display`) -> `0.3364`

Interpretation: G04/G11 are not explained away by paper-envelope mismatch. G04
remains a dense table/text/linework fidelity problem; G11 remains an outlier
whose residual is dominated by registration/shape, not the global envelope.

### Semantic class diagnostics

The batch tool now reports capture/view-space framing divergence for every case
using the same `compare.framing_divergence()` logic as `compare_vs_acad.py`.
This is important because the existing 12 AutoCAD PLOT references are not
strictly in the same view-space as render_cli model-extents output:

```text
batch compare: 12 total, 11 fallback/not-comparable
framing mismatches: 12
```

Examples:

| ID | Ink IoU | framing_mismatch | fill Δx | fill Δy |
|---|---:|---|---:|---:|
| G03 | 0.9080 | true | 0.0667 | 0.0665 |
| G04 | 0.6664 | true | 0.1484 | 0.1506 |
| G11 | 0.3464 | true | 0.0261 | 0.1022 |

That means the old 12-case scores remain useful for exploratory trend checks
and visual review, but they are not a formal X3 gate until the AutoCAD reference
PNGs are re-captured in the same extents/window contract.

The batch tool also accepts optional `semantic_mask` and `semantic_report` fields
per case. These are render_cli's candidate-side semantic class buffer and report
(`--class-mask-out` + `--report`). When present, the tool writes:

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

Conclusion: there is no obvious safe G11 plot-window tweak in the
`content_bbox`/`sheet` family. The later plot-frame prototype is a different
family: it models the AutoCAD PLOT paper frame rather than a CAD world window.
Keep this opt-in and multi-drawing gated; do not make `content_bbox` or `sheet`
the AutoCAD comparison default.

## Current Development Plan

### P0: Plot-window strategy for G11-class drawings

Do not default render_cli to content-bounds union. Do not switch X3 to
`view=sheet`. The next aligned slice is an explicit AutoCAD PLOT framing
strategy:

- source of truth: AutoCAD PLOT "Extents / Fit / Center" behavior, not GUI
  screenshot;
- implemented as an opt-in `view=acad-plot` service view, separate from
  `style=acad-plot`;
- gate: reduce framing mismatch and improve the good group without claiming
  formal AutoCAD equivalence for G04/G11.

### P1: Dense table/text/linework for G04-class drawings

G04 is not a framing outlier; aspect is close. The remaining gap is dense
annotation/table/linework style. Next diagnostics should split:

- text/table ink;
- dimensions;
- hatch;
- ordinary geometry;
- layer/color/lineweight contribution.

Do not apply a global lineweight multiplier.

### P1a: Local-error heatmap for dense drawings

G04 remains low after both paper-envelope alignment and AutoCAD-like display
style:

- reference-envelope removes the global paper/capture envelope mismatch;
- global lineweight/thickening only moves the score modestly and regresses other
  drawings;
- the residual needs localization before another renderer change is justified.

`autocad_batch_compare.py --tile-grid COLSxROWS` adds a diagnostic local-error
grid after the same global X3 crop/resize/shift alignment. It writes
`tile_summary.json`, `tile_summary.tsv`, and per-case heatmaps. The report is
intended to answer whether a drawing's residual is concentrated in a table,
title block, dense text area, hatch area, or main geometry.

Boundary:

- diagnostic only, not a pass/fail gate;
- not a semantic mask and not an AutoCAD semantic oracle;
- useful for picking the next renderer fix, not for declaring equivalence.

Implementation check on the 12 AutoCAD PLOT references:

```bash
python3 tools/render_regression/autocad_batch_compare.py \
  --cases /tmp/vemcad-fidelity-out/current_x3_acad_display/cases.json \
  --out-dir /tmp/vemcad-fidelity-out/g04_tile_grid_diag \
  --candidate-frame reference-envelope \
  --tile-grid 6x4
```

Result:

- `12` pairs processed;
- `framing mismatches: 0` after reference-envelope framing;
- `288` local tile rows generated;
- G04 remains low (`ink_iou=0.6788`, `color_dist=47.3`), but the residual is
  now localized rather than treated as one opaque score.

G04's worst 6 local tiles:

| Tile | Ink IoU | Ref px | Cand px | Missing px | Extra px | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| r1 c0 | 0.4689 | 7424 | 10257 | 3458 | 5971 | left dense view / annotation area |
| r2 c5 | 0.4716 | 10421 | 6576 | 6748 | 1891 | right-side material/table area |
| r1 c5 | 0.6212 | 12110 | 10928 | 5078 | 3630 | right-side table / text block |
| r3 c5 | 0.6684 | 11541 | 11767 | 3825 | 3904 | bottom-right title/table block |
| r0 c5 | 0.7228 | 14698 | 9782 | 5267 | 1687 | upper-right table/header block |
| r3 c4 | 0.7336 | 10848 | 13340 | 2706 | 3771 | bottom table block |

Artifacts:

- `/tmp/vemcad-fidelity-out/g04_tile_grid_diag/tile_summary.tsv`
- `/tmp/vemcad-fidelity-out/g04_tile_grid_diag/tile_heatmaps/G04_tile_heatmap.png`
- `/tmp/vemcad-fidelity-out/g04_tile_grid_diag/overlays/G04_overlay.png`

Interpretation: after paper-envelope mismatch is removed, G04's residual is
distributed across dense annotation/table regions and a left dense view. That
rules out another single global crop/scale/lineweight knob as the next safe
fix. The next renderer change should target a class of primitives with semantic
or local evidence, then prove it improves these hot tiles without regressing
the good group.

### P1b: Semantic tiles on the current render image

After `#138`, the current render image was refreshed with an isolated Docker
config to avoid the local credential-helper hang:

```text
ghcr.io/zensgit/vemcad-render:main
digest: sha256:5688ffff6f29b43d32de45a69b132677ce2bc490ac02c189a3e4d176971fcb44
```

G04 was re-rendered with `--class-mask-out` and compared with both
`--candidate-frame reference-envelope` and `--tile-grid 6x4`.

Render report semantic entity counts:

| Class | Count |
|---|---:|
| geometry | 5152 |
| text | 803 |
| dimension | 1147 |
| hatch | 3067 |
| insert_text | 27 |
| other | 0 |

Whole-drawing candidate semantic diagnostics:

| Class | Candidate px | Precision | Reference coverage | Interpretation |
|---|---:|---:|---:|---|
| geometry | 107271 | 0.6809 | 0.4647 | largest contributor |
| text | 38166 | 0.7834 | 0.1821 | right/table text contributes, not sole root |
| dimension | 19729 | 0.5363 | 0.0724 | real contributor, but smaller than geometry |
| hatch | 16578 | 0.4335 | 0.0407 | low precision in dense section views |
| insert_text | 1090 | 0.5899 | 0.0077 | minor |
| other | 403 | 0.7370 | 0.0067 | minor |

The semantic-tile diagnostic localizes those classes:

- worst tile `(1,0)` (left dense view): `hatch` and `geometry` dominate the
  candidate-side mismatch, with `dimension` secondary;
- worst tile `(2,5)` (right material/table area): mostly `text` plus some
  `geometry`;
- tiles `(1,5)`, `(0,5)`, `(3,5)` (right-side tables / title blocks): mostly
  `geometry` and `text`;
- lower-left dense tiles carry a mix of `geometry`, `dimension`, and hatch.

Artifacts:

- `/tmp/vemcad-fidelity-out/g04_current_digest_5688ffff/G04_report.json`
- `/tmp/vemcad-fidelity-out/g04_semantic_tile_digest_5688ffff/semantic_tile_summary.tsv`
- `/tmp/vemcad-fidelity-out/g04_semantic_tile_digest_5688ffff/tile_summary.tsv`
- `/tmp/vemcad-fidelity-out/g04_semantic_tile_digest_5688ffff/overlays/G04_overlay.png`

Interpretation: the next renderer optimization should be class-specific and
evidence-led. A safe next candidate is a hatch/geometry-focused investigation on
the left dense section-view tiles, then a separate table/text investigation for
the right-side table blocks. Do not collapse this into a single global lineweight
or crop rule.

### P2: Style selection for AutoCAD-like display comparison

Use styles deliberately:

- `style=source`: source-colour baseline and default render-service behavior.
- `style=acad-display`: AutoCAD-like display review; preserves saturated CAD
  colours but maps neutral grey linework to black.
- `style=acad-plot`: neutral grayscale diagnostic style, not the closest
  AutoCAD-like display style for this batch.

Current G04 style matrix, re-run after semantic-tile diagnostics:

| Candidate style | Ink IoU | Color dist | Framing mismatch | Interpretation |
|---|---:|---:|---|---|
| `source` | 0.6762 | 79.7 | false | source-colour baseline |
| `acad-display` | 0.6788 | 47.3 | false | best current AutoCAD-like display candidate |
| `acad-plot` | 0.6311 | 98.5 | false | worse for this coloured AutoCAD PLOT reference |

Artifacts:

- `/tmp/vemcad-fidelity-out/g04_style_matrix/compare/summary.tsv`
- `/tmp/vemcad-fidelity-out/g04_style_matrix/compare/tile_summary.tsv`
- `/tmp/vemcad-fidelity-out/g04_style_matrix/compare/overlays/acad_display_overlay.png`

Two false leads were explicitly checked and ruled out:

- **Global BYLAYER yellow text import is not broken.** A minimal DXF with
  `TEXT`/`MTEXT`, layer ACI 2, and entity colour 256 renders yellow through the
  current `render_cli` image.
- **The right-side G04 mismatch is not caused by the `acad-display` postprocess.**
  The relevant candidate crop is already grey/black in `style=source`; applying
  `acad-display` mainly improves neutral linework, it does not create the text
  colour mismatch.

Correct next optimization split:

1. **Left dense section-view tiles** — investigate hatch/geometry/dimension
   rendering. Do not use a global lineweight or crop rule; semantic tiles show
   hatch + geometry dominate.
2. **Right table / material / technical-requirements tiles** — investigate
   table/text placement and complex MTEXT/proxy paths separately. Treat colour
   as display evidence, not as proof of a single BYLAYER importer bug.

### P3: G11 ACI 255 helper/audit dimension cleanup

G11 (`B11.dxf`, `J2925004-04-01底板v2`) exposed an AutoCAD display mismatch
that was visible even before solving the broader paper-frame mismatch:
VemCAD displayed extra DIMENSION text and helper strokes such as
`600`, `190X3=570`, `15`, `230`, and `8-M8(...)` around the main view.
The AutoCAD reference did not display those helper dimensions the same way.

DXF inspection showed that the owning DIMENSION entities are on layer
`$TD_AUDIT_GENERATED_(2C7)`, whose layer colour is ACI 255 (true white). Their
referenced anonymous `*D` blocks, however, contain child primitives with
explicit ACI 2/3 colours. The renderer previously expanded the child primitives
and honoured those child colours, leaking the audit/helper dimension block into
the white-background render.

Two CADGameFusion fixes were shipped and consumed by VemCAD:

- CADGameFusion #424 / VemCAD #141: preserve ACI 255 as true white on light
  backgrounds while keeping AutoCAD's ACI 7 foreground-colour flip intact.
- CADGameFusion #425 / VemCAD #142: for `*D` blocks owned by a DIMENSION on an
  ACI 255 layer, expand child primitives on the parent DIMENSION layer and
  BYLAYER colour so the true-white parent layer controls visibility.

Verification:

- CADGameFusion #424 and #425 both passed the full CI matrix before merge.
- VemCAD #141 and #142 both passed `editor-light` and `render-image`
  `build-and-smoke`.
- VemCAD main `b80eceb` rebuilt and pushed `ghcr.io/zensgit/vemcad-render:main`
  digest `sha256:13601788bc9583276aa50d99efd94a2f6380e7560c3d8d0b5898e1756602ef95`.
- G11 was re-rendered from that image:
  `/tmp/vemcad-fidelity-out/g11_dimension_aci255_after_13601788/G11_ours.png`.
- Visual before/after contact sheet:
  `/tmp/vemcad-fidelity-out/g11_dimension_aci255_after_13601788/G11_acad_before_after_contact.png`.

Result:

- The extra visible audit/helper dimension labels and lines around the main
  G11 view were removed from VemCAD's render.
- `color_dist` improved from `139.2` after #424 to `122.9` after #425.
- Overall X3 is still **not comparable** because the AutoCAD PLOT reference and
  render_cli extents render remain in different view spaces:
  `framing div Δx=0.0628 Δy=0.1301`.

Follow-up batch rerun with the same `sha256:13601788...` render image:

- 12 AutoCAD references were re-rendered from `B01.dxf` ... `B12.dxf` and
  compared with `compare_vs_acad.py`.
- G04 improved from the earlier `source` baseline `0.6664` to `0.8423`.
- G11 improved from the earlier `source` baseline `0.3464` to `0.7712`.
- The other ten drawings stayed at their previous source-baseline values within
  rounding, so the ACI255/DIMENSION cleanup did not introduce a broad corpus
  regression.
- Artifacts:
  `/tmp/vemcad-fidelity-out/batch_after_13601788/compare/summary.tsv` and
  `/tmp/vemcad-fidelity-out/g04_current_after_13601788/G04_acad_old_new_overlay_contact.png`.

Interpretation: this is a real localized fidelity improvement, not a full G11
closure. The remaining G11 score is dominated by paper-frame/view-space
alignment and title-block/text appearance; do not use the global X3 number for
this pair until the reference and candidate are in the same view-space.

## Boundary

This slice does not mark the corpus "AutoCAD-equivalent". The strongest current
group is visually close, but the formal X3 `PASS >= 0.97` threshold is not met.
The next renderer change should be gated by improvement on G11 or G04 without
regressing the good group.
