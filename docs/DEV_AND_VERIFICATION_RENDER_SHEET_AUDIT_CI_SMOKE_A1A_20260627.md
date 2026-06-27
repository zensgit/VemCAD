# A1a — sheet-readiness audit: end-to-end CI smoke (advisory)

> Task: Fork A → **A1a** from `DEV_AND_VERIFICATION_RENDER_FIDELITY_FORK_A_TASKBOOK_20260626.md` (owner opt-in).
> Repo: VemCAD · branch `claude/render-sheet-audit-ci-smoke` (PR #125) · base `origin/main` (`5a7c5e0`).
> Change: **CI-only** (`.github/workflows/render-image.yml`) + this doc. **No Python/tool change.**

## 1. Honest scope reframe (smaller than the taskbook assumed)
A1a was described as "commit a synthetic DXF corpus + a CI readiness smoke exercising the audit's pure logic." On inspection two things changed the shape:
- **The audit's analysis logic is already unit-tested** — `services/render/tests/test_sheet_readiness_audit.py` covers `image_stats`, `analyse_pair` (pass/fail/review/fallback) and `write_contact_sheets`. A second fast-gate unit test would be redundant.
- **A committed corpus already exists** — `tools/render_regression/golden/*.dxf` (incl. `multi_frame.dxf`). No need to commit a new one.

So this slice delivers the one thing that was actually missing: **the audit tool run end-to-end in CI** (today it is operator-only — it needs a running render service + a drawings directory). It is wired as an **advisory** step that runs the existing audit over the existing golden corpus inside the render image and asserts a well-formed `summary.json`.

**What this is / is NOT:**
- ✅ IS: a *tool plumbing / regression* signal — "the audit still runs end-to-end and emits a schema-valid corpus summary."
- ❌ is NOT: a "`view=sheet` is ready to become the default" verdict. The golden set is render-regression material (it intentionally includes `garbage_extents`, degenerate inputs), so per-drawing pass/review/fail over it is meaningless as readiness. **The real readiness verdict needs a curated sheet corpus with known expectations → A1a-2 (next slice).**

## 2. What changed
New advisory step in `.github/workflows/render-image.yml` (after the golden E2E, before GHCR push):
- Starts the built `vemcad-render:ci` image (`docker run -d --network none --name …`), polls `/healthz` — **mirrors the existing service-smoke wiring** (in-container loopback via `docker exec`; the image ships numpy/Pillow per `services/render/requirements.txt`, so the audit's analysis half runs in-container).
- `docker cp`s the audit tool (not baked into the image) + the committed `tools/render_regression/golden` corpus into the container.
- Runs `sheet_readiness_audit.py --input-dir /golden --out-dir /tmp/audit_out --base-url http://127.0.0.1:8077` (`|| true` — the audit's own exit is nonzero on the regression corpus by design; that is not the gate).
- **Asserts** `summary.json` has `schema == vemcad.sheet_readiness_audit/v1` AND that **≥5 goldens rendered BOTH views with `error is None` + both PNGs** (`rendered_ok >= 5`) — i.e. the real `/render` path actually ran. A schema + `totals.count` check alone would pass even if `/render` failed on all 7, because the audit records each render exception as a `status="fail"` row while still writing the summary; counting error-free render pairs is what closes that false-green.
- `continue-on-error: true` → advisory; cannot block the heavy gate.

## 3. Verification status — **VERIFIED GREEN on the real heavy gate**
This needs the built render image (render_cli + Qt + fonts), which does not build on this dev machine, so it was verified in CI (like the pact Phase-A→B path):
1. Advisory (`continue-on-error: true`) — cannot break the heavy gate.
2. **✅ Verified** — PR #125, `render-image` → `build-and-smoke` **success**; the *Sheet-readiness audit E2E (advisory)* step really ran and logged **`[sheet-audit] OK total=7 rendered_ok=7`** (all 7 goldens rendered both views via the real `/render` path; `garbage_extents.dxf` shows `status=fail` on content but rendered without error, so it still counts in `rendered_ok`). The `[sheet-audit] OK` line prints ONLY when the assertion passes, so this is a real pass — NOT a `continue-on-error`-masked failure.
3. **Flip to blocking (pending owner go)**: now that it is green on a real run, a one-line follow-up removes `continue-on-error: true` so a broken/unverified audit fails the build (the audit becomes a guarded regression gate for the tool itself). Making the gate blocking is a deliberate, consequential change → owner-gated.

Static check done locally: `python -c "import yaml; yaml.safe_load(open('.github/workflows/render-image.yml'))"` parses clean.

## 4. Follow-up — A1a-2 (the real substance)
Build a **curated sheet corpus** (`services/render/tests/fixtures/sheet_corpus/` or under `tools/render_regression/`) of drawings with a title block / 图框 and **known expected verdicts** (clean sheet → pass; over-crop → fail; edge-touch → review; no-frame → fallback/review), and assert the audit reproduces those expectations. That is what actually advances the "make `view=sheet` the default" decision; this slice only makes the tool runnable-in-CI so A1a-2 has somewhere to land. The full go/no-go on flipping the default still needs a real customer/training drawing corpus (owner/ops-gated evidence).

## 5. Risk / rollback
- Additive + advisory: no change to render/geometry, no change to the `view=extents` default, no Python change. Worst case the new step is red and ignored (non-blocking) until fixed.
- Rollback = delete the step (one block). Flip-to-blocking is a separate, deliberate one-line follow-up gated on a green run.
