# VemCAD Current Plan Closeout and Verification (2026-06-27)

## Scope

This records the executable items found in the current VemCAD plan audit and the
verification evidence for each. It intentionally excludes production gates and
methodology decisions that need a fresh product decision.

Baseline at the start of this slice:

- VemCAD `origin/main`: `9e783a4`
- VemCAD gitlink `deps/cadgamefusion`: `4327230`
- CADGameFusion `origin/main`: `4327230`

## Completed

### 1. Desktop router readiness R0/R1/R2

PR: VemCAD #124, merged as `db70e81`

What changed:

- Converted the router-readiness taskbook into an executed R0/R1/R2 record.
- Corrected the route inventory to the actual router contract:
  `/health`, `/convert`, `/status/{task_id}`, `/manifest/{task_id}`, `/history`,
  `/projects`, `/projects/{project_id}/documents`,
  `/documents/{document_id}/versions`.
- Added launcher lifecycle tests for pre-ready handle stability and spawn
  failure classification.
- Added a router contract-inventory test to prevent stale `/jobs/{job_id}` /
  `/artifacts/{artifact_id}` language from returning.
- Added an opt-in real reference-router smoke:
  `node services/router/tools/router_reference_smoke.mjs`.

Verification:

```text
npm test
# tests 144
# pass 144

npm run test:web
# tests 123
# pass 123

node services/router/tools/router_reference_smoke.mjs
# status PASS; /health ok; router commit 4327230

git diff --check
# clean
```

CI on PR #124:

- `product-tests / core`: pass
- `product-tests / web-integration`: pass

### 2. Semantic dimension provenance A->C

CADGameFusion PR: #422, merged as `312bce4`

What changed:

- `render_cli` import now tags `*D` dimension-block primitives with
  `source_type="DIMENSION"`.
- Semantic masks can now populate the `dimension` class on real drawings.
- Color render output is byte-identical before/after for the covered fixtures.

VemCAD consumption PR: #127, merged as `383aa26`

What changed:

- Gitlink-only bump `deps/cadgamefusion` from `4327230` to `312bce4`.
- Ancestor guard passed: `312bce4` is reachable from CADGameFusion
  `origin/main`.

Verification before VemCAD PR:

```text
npm test
# tests 144
# pass 144

npm run test:web
# tests 123
# pass 123

git diff --check
# clean
```

CI on PR #127:

- `editor-light`: pass
- `render-image / build-and-smoke`: pass

### 3. G11 semantic diagnosis state

PR: VemCAD #123

What this closes:

- Records that the original G11 semantic mask diagnostic was inert because the
  importer did not emit the provenance read by the classifier.
- Records that Direction A's dimension part is now shipped and consumed through
  CADGameFusion #422 and VemCAD #127.
- Keeps the G11 verdict honest: dimension provenance is now available, but G11 is
  still not AutoCAD-equivalent while the X3 comparison remains dominated by
  view-space / framing mismatch.

## Explicit Non-Starts

These are not unfinished implementation from this slice; they require a separate
decision or corpus proof.

- **G11 view-space / framing contract.** Decide how AutoCAD PLOT view-space and
  `render_cli` model-space view should be aligned before interpreting X3 class
  scores.
- **`insert_text` provenance.** ATTRIB identity is discarded on the current
  libdxfrw render path; solving it is a parser/fork decision, not a VemCAD
  Python patch.
- **G11 hatch outlier.** Most hatch classification is already covered by the
  `__HATCH_FILL__` fallback; G11 remains a specific case to diagnose after the
  view-space question.
- **`view=sheet` default flip.** Human preview and X3 comparison have different
  framing requirements; defaulting sheet view needs a separate corpus gate and
  must not silently change X3 comparison framing.
- **Production or cloud decisions.** Router productization, deploy-location, and
  production cutovers remain user-gated.

## End State

- CADGameFusion main contains dimension provenance at `312bce4`.
- VemCAD main consumes that runtime through PR #127.
- Router readiness R1/R2 guardrails are in VemCAD main through PR #124.
- The remaining render-fidelity work is methodology-gated, not blocked on an
  unmerged obvious implementation slice.
