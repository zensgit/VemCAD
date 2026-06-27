# DEV & VERIFICATION — Render semantic-class provenance + X3 framing detection (2026-06-27)

Scope: completing the development that the G11 semantic-diagnosis
(`VEMCAD_G11_SEMANTIC_DIAGNOSIS_RESULT_20260627.md`) and AutoCAD-comparison
boundary docs left open — making `render_cli`'s semantic class buffer actually
classify the annotation classes on real drawings, and making the X3 comparator
correctly attribute capture/view-space mismatches. This record maps the unfinished
items, what was developed in parallel, the verification gathered, and the honest
decision-gated / owned-elsewhere remainder.

## 1. Unfinished-item inventory (what this addressed vs what is deliberately parked)

The semantic class diagnostic (#110/#112) was plumbed end-to-end **except** the
upstream entity-provenance metadata its classifier
(`scene_renderer::semanticClassName`, keys `source_type`/`text_kind`/
`attribute_tag`) reads — render_cli's `CadgfDrwAdapter` import path never emitted
it, so DIMENSION / HATCH / INSERT-derived primitives collapsed into geometry/text.
That, plus the X3 view-space/framing misattribution, was the developable remainder.

| Item | Status | Notes |
|---|---|---|
| dimension provenance | ✅ done | CADGF #422 (`312bce4`) + VemCAD bump #127 |
| hatch provenance | ✅ done | CADGF #423 (`bb03cce`) + VemCAD #130 |
| insert_text provenance | ✅ done | CADGF #423 (`bb03cce`) + VemCAD #130 |
| X3 framing/view-space detection (solo part) | ✅ done | VemCAD #132 |
| real per-PR CI gate (render_cli semantic E2E) | ✅ done | VemCAD #130 (render-image) |
| G11 diagnosis doc | ✅ done | VemCAD #123 (merged) |

### Parallel tracks (the "可并行开发" answer)

Three independent tracks, developed in parallel (different repos / files, no shared
edit surface):

- **Track A — CADGF C++ adapter** (dimension → then hatch + insert_text): all in
  `plugins/dxf_libdxfrw_adapter.{cpp,hpp}` + the render_cli ctest. Serialised
  *within* the track (same file) but independent of B and C.
- **Track B — VemCAD Python comparator** (X3 framing detection):
  `tools/render_regression/{compare.py,compare_vs_acad.py}` + tests + README. No
  C++/submodule dependency; ran fully in parallel with Track A (a separate agent).
- **Track C — A→C plumbing**: VemCAD gitlink bumps + the render-image CI gate;
  sequenced after each CADGF merge.

### Deliberately NOT built (decision-gated / frozen by prior owner decision)

Per `VEMCAD_DEVELOPMENT_PLAN.md` "执行收口状态": P2 god-file split (demand-driven),
P3 desktop-shell convergence, P4 cloud/multi-user (deployment frozen = desktop
single-user), P4 router rewrite (python→node), D1b first-class coincident, OCCT,
P5 Qt role. These are trigger-gated and were left untouched.

### Needs the user's environment (cannot be done solo)

- Render-service **S3 deploy** (`deploy_on_host.sh` on the host where Yuantus runs).
- **X3 AutoCAD reference capture** + the score-moving X3 parity fix (render_cli
  `--window` matching the AutoCAD plot, or re-exporting the ref fit-to-extents):
  needs the AutoCAD machine / plot-window values. This PR set delivers only the
  *detection + attribution* half (Track B).

### Owned elsewhere (other in-flight PRs, not touched)

CADGF #363 (solver Jacobian), #120–#128 (ABI/editor P1/P2 series); VemCAD #1
(copilot WIP), #128 (AutoCAD batch compare — *complemented* by Track B, not
duplicated).

## 2. What was developed

### Track A — render_cli import-path provenance (CADGF `CadgfDrwAdapter`)

The classifier is keyed on per-entity metadata `dxf.entity.<id>.source_type` (read
by `scene_renderer::lookup_entity_meta`). The adapter now emits it across the
block-expansion seam:

- **dimension** (#422): `expandBlock` gained an `originType` param (propagated
  through recursion); each expanded primitive is tagged via `setEntitySourceType`;
  the referenced `*D` dimension-block expansion passes `"DIMENSION"`.
  `addPolylineToDoc` returns the entity id so line/arc/circle primitives can be
  tagged.
- **hatch** (#423): block-nested SOLID hatches were stored as `BlockEntity{linetype
  "__SOLID__"}` and lost provenance across the block seam (linetype is occupied by
  the fill-style marker). Added a `BlockEntity.sourceType` channel; `addHatch` sets
  it to `"HATCH"`; `expandBlock` prefers `ent.sourceType` over the INSERT
  `originType`; the top-level solid-hatch path is tagged directly. The classifier is
  **not** widened (`__SOLID__` is shared by SOLID/TRACE quads + dimension
  arrowheads, which must stay geometry/dimension).
- **insert_text** (#423): the top-level INSERT `expandBlock` call passes
  `originType="INSERT"`, so INSERT-sourced (e.g. title-block) text classifies as
  `insert_text`.

All changes are additive metadata writes — invisible to the non-mask render path.

### Track B — X3 capture/view-space mismatch detection (VemCAD #132)

`compare_vs_acad.py` crops to each render's own ink bbox, so it is blind to
page-fill / view-space. When the AutoCAD ref is a paper-space PLOT and render_cli
draws model-space EXTENTS, the ink-IoU drops and reads as renderer infidelity. New
pure `compare.framing_divergence()` measures page-fill per axis + aspect_delta and
flags `framing_mismatch`; `compare_vs_acad.py` then emits "NOT COMPARABLE
(framing/capture mismatch)" instead of "DIVERGENT". Diagnostic only — does not
touch the CompareResult or the D2/regress gate. The score-moving parity fix is
explicitly out of scope (needs the AutoCAD env).

### Track C — A→C plumbing + the real CI gate (VemCAD #130)

CADGF per-PR CI does **not** build render_cli (`BUILD_EDITOR_QT=OFF` / no libdxfrw
in those jobs), so the in-repo render_cli ctests are local/developer gates. The
real per-PR gate is added VemCAD-side in `render-image.yml`: a new E2E step builds
the image (real Linux render_cli, from the bumped submodule) and renders the
in-submodule synthetic fixture (`render_cli_semantic_sample.dxf` — a `*D`
dimension + a block-nested SOLID hatch + INSERT text), asserting
`dimension`/`hatch`/`insert_text` are all non-zero.

## 3. Verification

### Local (the freshly-built render_cli, off current main)

| Drawing | class | before → after | check |
|---|---|---|---|
| G11 (real) | dimension | 0 → 86 | reclassified out of geometry/text |
| G11 | hatch | 0 → 4 | 3 SOLID block-hatches (one has 2 loops) |
| G11 | insert_text | 0 → 16 | the 16 title-block values |
| B01 (real) | dimension | 0 → 48 | |
| B01 | hatch | 16 → 20 | block-nested solids now classified |
| B01 | insert_text | 0 → 16 | |

- **Color render byte-identical before/after on G11 and B01** for every slice — the
  provenance metadata is invisible to the non-mask render path, so there is **no
  fidelity regression**.
- **Semantic mask visually correct**: dimension red / hatch green / insert_text
  purple / text orange / geometry blue, each on the right entities (title-block
  values purple, dimension annotation red, part outline blue).
- **ctests**: `render_cli_dimension_class_provenance` + the comprehensive
  `render_cli_semantic_class_provenance` (one ezdxf fixture exercising all three
  classes, asserts each > 0). The existing semantic smoke, the orphan-dimension
  adapter test, and 4 hatch adapter tests all still pass.
- **X3 framing (Track B)**: 10/10 pytest; real G11 → page-fill ref(y=0.922) vs
  ours(y=0.820), framing Δy=0.1022 (>0.05) → verdict "NOT COMPARABLE
  (framing/capture mismatch)" instead of "DIVERGENT". No gated number changed.

### CI

- CADGF **#422** (dimension) and **#423** (hatch+insert_text): all run-here checks
  green (validate-samples, Build Core ×3, Local CI, Qt Tests, quick-check, CI
  Summary). Merged.
- VemCAD **#130** (MERGED `24c0231`, submodule → `bb03cce`): the render-image E2E
  built render_cli from the bumped submodule and ran the semantic-provenance gate
  in CI — **the real per-PR proof**. CI log:
  `entity_counts: {dimension: 6, hatch: 1, insert_text: 1, ...}` →
  `[semantic-provenance] OK`; render-image job `completed/success`; `editor-light`
  green. The gate is now on `main` and guards future regressions.
- VemCAD **#132** (Track B, MERGED `a4a8fe3`): `build-and-smoke` + `pytest` green.

## 4. Net state

`render_cli --class-mask-out` now produces a **complete** semantic class buffer
(dimension / hatch / insert_text / text / geometry all populate correctly), so the
G11 boundary doc's class-level read is finally possible. The remaining X3 gap is
purely the view-space/framing **capture** mismatch — now auto-detected and
correctly attributed (Track B), with the score-moving parity fix honestly deferred
to the AutoCAD-environment work. All parked roadmap items remain decision-gated.

**Status: all slices merged to `main`.** CADGF #422 (`312bce4`) + #423 (`bb03cce`);
VemCAD #123 (diagnosis doc), #127 (dimension bump), #130 (`24c0231`, hatch+insert
bump + render-image semantic gate), #132 (`a4a8fe3`, X3 framing detection). VemCAD
`main` submodule pointer = `bb03cce`; the render-image semantic-provenance gate is
live on `main`. The only remaining work is the decision-gated / user-environment
items in §1 (render-service S3 deploy, X3 AutoCAD-machine parity capture, and the
frozen P2–P5 / D1b / OCCT roadmap), none of which is a no-decision developable gap.
