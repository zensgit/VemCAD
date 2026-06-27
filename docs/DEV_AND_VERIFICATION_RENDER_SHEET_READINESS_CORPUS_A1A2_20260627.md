# A1a-2 — curated sheet-readiness corpus with KNOWN expected verdicts

> Task: Fork A → **A1a-2** (the substantive follow-up flagged in
> `DEV_AND_VERIFICATION_RENDER_SHEET_AUDIT_CI_SMOKE_A1A_20260627.md` §4).
> Repo: VemCAD · branch `claude/render-sheet-readiness-corpus` · base `origin/main` (`108c9ed`).
> Change: **test + spec + doc only.** No Python/tool change, no CI workflow change, no route change.

## 1. Scope (what this is / is NOT)

- ✅ IS: a **verdict-logic regression gate**. It proves the audit's `analyse_pair`
  reproduces KNOWN verdicts on a curated set of synthetic `(extents, sheet)` PNG
  pairs — one per verdict category — under the **shipping default thresholds**
  (`Thresholds()`). If someone retunes the thresholds or the verdict branches,
  this turns red.
- ❌ is NOT: a "`view=sheet` is ready to become the render default" go/no-go.
  That decision needs a **real operator / training / customer drawing corpus**
  with human-confirmed expectations (owner/ops-gated evidence) — still deferred,
  exactly as A1a §4 said. Synthetic fixtures cannot stand in for that.

This stays in the **fast-gate, fully-local-verifiable tier**. It deliberately
does **not** add a heavy render-image E2E step; the audit's `analyse_pair` is
pure numpy/PIL, so the curated corpus runs with no render service. A render-image
E2E that renders curated DXFs through the real `/render` and checks verdicts is a
possible future slice (heavy tier) — noted as a follow-up, not done here.

## 2. Why this is net-new (not redundant with A1a's "already unit-tested" note)

A1a observed `analyse_pair` is already unit-tested and a second generic test
would be redundant. The genuine gap this slice closes is the **edge-touch →
review** verdict:

| Category | Verdict | Covered before A1a-2? |
|---|---|---|
| clean | pass | yes (`test_audit_passes_clean_sheet_pair`) |
| over-crop (heavy ink loss) | fail | yes (`test_audit_fails_heavy_ink_loss`, but with a **per-test threshold override** `retained_fail=0.6`) |
| fallback / no-frame | review | yes (`test_audit_marks_fallback_for_review`) |
| **edge-touch** | **review** | **NO** — `test_image_stats_detects_ink_and_edges` only asserts the *stat* (`edge_ink_fraction > 0.02`); it never calls `analyse_pair`, so the edge-touch *verdict* was uncovered |

A1a-2 also tightens the existing coverage: every curated case runs under the
**default** `Thresholds()` (no per-case override), so it regresses the verdict
the audit actually ships, not a tuned one.

## 3. What changed

1. `services/render/tests/test_sheet_readiness_audit.py` — added the curated
   corpus as an inline `CURATED_CASES` source-of-truth list plus:
   - `test_curated_corpus_reproduces_known_verdict` (parametrized over the 4
     cases) — builds the synthetic pair per case via the existing `_drawing`
     helper and asserts `analyse_pair(...).status == expected` with `Thresholds()`.
   - `test_curated_corpus_covers_all_four_categories` — guards against a
     silently-empty parametrization (asserts exactly 4 cases, verdicts ⊆
     {pass, fail, review}).
   - `test_curated_corpus_json_matches_inline_cases` — asserts the spec file
     and the inline list agree, so neither drifts silently.
2. `tools/render_regression/sheet_corpus/corpus.json` — documents the curated
   cases (`name`/`category`/`expected_verdict` + fixture recipe). Mirror of the
   inline list; the test enforces agreement.
3. This doc.

### The four curated cases (default thresholds)

| name | extents | sheet | sheet_mode | measured | expected |
|---|---|---|---|---|---|
| clean_sheet | frame | frame | detected | retained 1.00, edge 0.00 | **pass** |
| over_crop | frame | crop | detected | retained ~0.13 < 0.35 | **fail** |
| edge_touch | frame | edge | detected | edge_frac ~0.056 ∈ (0.020, 0.060] | **review** |
| no_frame_fallback | frame | frame | fallback | clean pixels, but detector fell back | **review** |

Fixture recipes reuse the existing `_drawing` helper: `frame` = full frame +
cross-hairs (~7064 ink px), `crop` = tiny box (~912 ink px), `edge` = frame +
a line riding the top image edge.

> Note on the edge-touch fixture: edge_frac ~0.056 sits in the review band with
> ~8% headroom below `edge_fail` (0.060). It is deterministic for a symmetric
> horizontal line, so it is stable; the fixture must not be nudged in a way that
> raises edge ink, and the band must **not** be widened with a per-case
> threshold (that would break the "default thresholds = real regression"
> property).

## 4. Verification (local, mandatory)

`analyse_pair` / `image_stats` are pure numpy + PIL — no render service needed.

```
cd <worktree>
PYTHONPATH="<worktree>/src" /Users/chouhua/Downloads/Github/Yuantus/.venv-wp13/bin/python \
  -m pytest services/render/tests/test_sheet_readiness_audit.py -q
```

Result: **green** (existing cases + 6 new: 4 parametrized + 2 guards).
Also ran `tools/render_regression/tests` to confirm the new `sheet_corpus/`
dir does not trip any harness suite — green.

> Env note: the prebuilt `.venv-wp13` ships Pillow + pytest but **not** numpy
> (the audit tool imports numpy, so even the *pre-existing* test could not run
> there); `pip install numpy` was added to that venv to verify. CI supplies
> numpy via `render-tests.yml` (`pip install numpy pillow`), so this is a
> local-env gap, not a product gap.

CI: `services/render/tests/` auto-collects in `render-tests.yml` (no
ci.yml-style registration step in VemCAD), so the new tests run on any PR
touching `services/render/**`. The `corpus.json` lives under
`tools/render_regression/**`, also a render-tests trigger path.

## 5. Risk / rollback

- Additive, test-only: no change to render/geometry, no change to the
  `view=extents` default, no Python/tool change, no CI workflow change.
- Rollback = revert the test additions + delete `sheet_corpus/corpus.json`
  and this doc.

## 6. Follow-ups (not in this slice)

- **The real go/no-go**: curated corpus of **real** drawings (title block / 图框)
  with human-confirmed verdicts → the evidence needed to flip `view=sheet`
  default. Owner/ops-gated.
- **Heavy-tier E2E**: render curated DXFs through the real `/render` and assert
  the same verdicts (render-image.yml), once such DXF fixtures exist.
