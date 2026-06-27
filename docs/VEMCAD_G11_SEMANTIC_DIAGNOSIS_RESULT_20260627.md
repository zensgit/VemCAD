# VemCAD G11 Semantic Diagnosis Result (2026-06-27)

## Status

This is the result of the **"Recommended Next Slice" step 3** from
`VEMCAD_G11_AUTOCAD_COMPARISON_BOUNDARY_20260626.md` — *re-run G11 with the
renderer-supplied semantic masks* now that the mask path is built
(render_cli `--class-mask-out` + `compare_vs_acad.py --semantic-mask`, PRs
#110/#112).

The diagnosis is complete and conclusive. It does **not** mark G11 as passing and
does **not** change any gate threshold. It surfaces **two CADGF-side (A→C) root
causes** and leaves the step-4 fix direction as a pending decision — the boundary
doc's whole purpose is to not guess a renderer fix from a global score, and the
semantic evidence confirms that caution.

## Method (reproducible)

Render layer = the `ghcr.io/zensgit/vemcad-render:main` image's `render_cli`
(current-main render layer, semantic-class feature #110). Submodule pointer on
`main` is `4b5f4bbd` (the #114 bump is a Zhuque-font fix; it does not touch the
classifier or the import path, so this finding holds for current `main`).

```bash
# 1. render B11.dxf (G11) white-bg at the AutoCAD plot size, with the semantic mask
docker run --rm -v /tmp/vacadbatchinputs:/in:ro -v "$OUT":/out \
  --entrypoint render_cli ghcr.io/zensgit/vemcad-render:main \
  --input /in/B11.dxf --out /out/G11_ours.png --bg white \
  --width 2339 --height 1653 \
  --report /out/G11_report.json --class-mask-out /out/G11_semantic_mask.png

# 2. score vs the AutoCAD reference, with per-semantic-class diagnostics
python3 tools/render_regression/compare_vs_acad.py \
  /tmp/vemcadautocadplot/batch/png/G11-1.png "$OUT/G11_ours.png" \
  --out "$OUT/G11_x3_overlay.png" \
  --semantic-mask "$OUT/G11_semantic_mask.png" \
  --semantic-render-report "$OUT/G11_report.json" \
  --print-semantic-classes
```

AutoCAD reference: `/tmp/vemcadautocadplot/batch/png/G11-1.png` (2339×1653, RGB).

## Finding 1 (load-bearing) — the semantic classifier is inert on G11 because the import path never emits the provenance metadata it keys on

The renderer's own per-class counts for G11:

```text
geometry 186 · text 39 · dimension 0 · hatch 0 · insert_text 0 · other 0
```

But the **source DXF demonstrably contains** the annotation entities those classes
exist for (raw group-code-0 histogram of `B11.dxf`):

```text
DIMENSION 14 · HATCH 3 · INSERT 21 · ATTRIB 16 · ATTDEF 24 · MTEXT 84 · TEXT 106
```

So 14 dimensions, 3 hatches, and a 16-ATTRIB title block (`HC_BTL_BLK`) all land in
`geometry`/`text`, not their semantic classes. The semantic mask PNG confirms it
visually: only the `geometry` (blue) and `text` (orange) palette colours appear —
no `dimension` red, `hatch` green, or `insert_text` purple anywhere.

**Mechanism (verified in source, not inferred).** `scene_renderer.cpp
::semanticClassName` classifies by metadata:

```cpp
const std::string source      = lookup_entity_meta(doc, entity.id, "source_type");
const std::string textKind    = lookup_entity_meta(doc, entity.id, "text_kind");
const std::string attributeTag= lookup_entity_meta(doc, entity.id, "attribute_tag");
if (source == "DIMENSION" || textKind == "dimension") return "dimension";
if (source == "HATCH"     || entity.line_type == "__HATCH_FILL__") return "hatch";
// Text with source=="INSERT" / attributeTag / text_kind attrib|attdef -> insert_text
```

Grepping the import / DXF-adapter / core path for any writer of `source_type`,
`text_kind`, or `attribute_tag` metadata returns **nothing**. The classifier was
landed (#110) reading provenance keys that the import pipeline does not produce, so
`lookup_entity_meta` always returns empty and every entity falls through to
`geometry`/`text` by `EntityType` alone. DIMENSION/HATCH/INSERT entities are
expanded into plain lines/text at import and lose the tag the classifier needs.

**Consequence:** the semantic diagnostic the boundary doc commissioned cannot
separate text / dimension / hatch / ordinary-geometry / title-block on exactly the
annotation-dense drawings (G11 class) it was built to diagnose. It is end-to-end
plumbed **except** for this upstream metadata, so today it only distinguishes
`geometry` vs `text`.

## Finding 2 — the X3 miss is a global registration / view-space mismatch, not a single rendered class

The X3 result (white bg, AutoCAD size):

```text
ink IoU 0.3424 · SSIM 0.0772 · color dist 131.9 · aspect delta 0.0575 · band fallback
```

The overlay shows red/green ink **fanning out across the whole drawing** (the main
ellipse, the dimension rails, the frame) — not a localized class error. Ink
bounding boxes:

```text
acad   ink_w 956  ink_h 1524  aspect(w/h) 0.627
ours   ink_w 959  ink_h 1355  aspect(w/h) 0.708     # same width, AutoCAD ~11% taller
```

Same width, ~11% taller on the AutoCAD side → after the comparator crops to ink
bbox and resizes to a common canvas, vertical features mis-register progressively.
This matches the boundary doc's ruled-out-but-real "stale header / not the same
semantic view-space as the AutoCAD PLOT" class of issue. **Because the registration
itself is off, the per-class `precision`/`reference_coverage` numbers
(geometry 0.33 / text 0.38) are depressed by alignment drift and are not evidence
that a specific class is rendered wrong.** (They are also candidate-side metrics —
AutoCAD semantics are unknown — so a low value means "our ink for that class does
not land on AutoCAD ink," which can be us, placement, or AutoCAD.)

## What this means

Both step-4 candidate directions are **CADGF / methodology side (A→C)**, exactly as
the boundary doc anticipated. No product-side (Python) change addresses either, and
manufacturing one would be the "guess a fix from a global score" failure the
boundary doc exists to prevent.

- **Direction A — make the semantic diagnostic real (prerequisite for the whole
  plan).** Emit `source_type` / `text_kind` / `attribute_tag` entity metadata at
  import — tag the primitives that block expansion produces from DIMENSION / HATCH /
  INSERT / ATTRIB with their origin class (and mark hatch fills `__HATCH_FILL__`).
  Then the semantic mask populates `dimension` / `hatch` / `insert_text` on real
  drawings and step 3 can actually isolate the failing class. Without this, the
  semantic line cannot answer "which class is wrong."

- **Direction B — resolve the X3 view-space / framing contract.** Decide whether the
  AutoCAD reference (PLOT) and `render_cli` (model-space extents) are in the same
  view space; the ~11% vertical mismatch says probably not. Fix is either a stricter
  X3 capture/window contract or a render window that matches the AutoCAD plot — a
  methodology decision plus possibly a renderer capability (layout / paper-space
  framing), not a pixel tweak.

- **Park.** The render/font line is already declared *complete* (#111) and G11 is a
  documented honest outlier. Accepting this diagnosis as the closeout — semantic
  mask proven inert-without-provenance, X3 miss proven view-space-dominated — and
  deferring both A and B until there is product demand is a legitimate stop.

## Boundary (unchanged)

Do not mark G11 AutoCAD-equivalent while X3 is in `fallback`. Do not relax the
`compare_vs_acad.py` gate. Do not add a global text/lineweight/scale multiplier from
G11's IoU. The next concrete code step is gated on the Direction A / B / Park
decision above.

## Update (2026-06-27): Direction A (dimension) shipped and consumed

Direction A's **dimension slice** shipped in **CADGameFusion PR #422**
(`feat(render): emit dimension provenance metadata in render_cli import path`,
merged as `312bce4`). render_cli's `CadgfDrwAdapter` now tags `*D`
dimension-block primitives with `source_type="DIMENSION"`, so the semantic mask
classifies the `dimension` class (G11: 0 -> 86; a corpus drawing: 0 -> 48; color
render byte-identical before/after, i.e. no fidelity regression; new `qt_`-gated
regression test).

VemCAD consumed that CADGameFusion capability in **VemCAD PR #127** as a
gitlink-only bump to `312bce4` (merged as `383aa26`). The bump passed the
ancestor guard (`312bce4` is on CADGameFusion `origin/main`) and VemCAD's
consumer checks:

- `editor-light`: pass
- `render-image / build-and-smoke`: pass

**This ships the capability, not the G11 conclusion.** The actual class-level read
of G11 (which renderable class accounts for the AutoCAD mismatch) is the next step,
and per Finding 2 it stays confounded by the view-space / framing mismatch until
that is addressed — so dimension being classifiable does not by itself move the X3
score or "solve" G11.

The other two classes remain follow-ups: **insert_text** is a deeper change
(render_cli's libdxfrw path structurally discards ATTRIB identity; the
identity-preserving parser is convert_cli-only — a fork/parser decision); **hatch**
mostly already works via the `__HATCH_FILL__` fallback (a corpus drawing classifies
16 hatch entities), with G11's hatches a specific outlier.
