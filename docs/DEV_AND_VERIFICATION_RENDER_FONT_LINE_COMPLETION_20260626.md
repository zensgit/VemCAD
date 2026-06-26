# DEV & VERIFICATION — CAD render/font line: completion record

Date: 2026-06-26 · Scope: the DXF **render service** (VemCAD `services/render/`) + **CJK font** handling +
the **CADGameFusion render layer**. This is the *completion + verification* record for this line: what
shipped, mapped to the plan, the verification gathered, and the honest deferred / out-of-scope /
owned-elsewhere remainder. It does **not** cover the separate VemCAD roadmap lines P2–P5 (see §4).

## 1. What shipped (all on `main`)

| PR | What | Repo | SHA |
|---|---|---|---|
| #101 | drop the temporary `STFangsong` fontconfig alias (root fix landed) | VemCAD | `9f15a27` |
| #103 | remove the CJK fontconfig alias entirely (root fix consumed) | VemCAD | `7f39168` |
| #104 | repair Zhuque 仿宋 fetch (v0.212 zip) + **OFL license** + CJK DEV/V | VemCAD | `34e93fa` |
| #413 | normalize explicit `STKaiti`/`STHeiti` at the render layer | CADGF | `d72d6b41` |
| #414 | prefer Zhuque Fangsong over Noto on the Linux render host | CADGF | `811d7e9` |
| #105 | bump CADGameFusion → `811d7e9` (Zhuque-preferred + STKaiti/STHeiti) | VemCAD | `28d9bc0` |
| #106 | CJK DEV/V update — Zhuque now the resolved 仿宋 | VemCAD | `1fe0eb5` |
| #107 | read nested `render_cli_report.view` for sheet detection | VemCAD | `a48eb39` |
| #100 | grayscale plot style + sheet-readiness audit (report-view split to #107) | VemCAD | `7c20b75e` |
| #371 | extract DXF top-level insert committers (refactor) | CADGF | `5de7fbb` |
| #3216 | publish consumer pact only on `push:main` (off-main hygiene) | metasheet2 | `ddd63fdc` |

## 2. Map to the plan

- **CJK font correctness** (`DEV_AND_VERIFICATION_CJK_FONT_LINE_CLEANUP_20260625.md` §1–2): empty-style
  Chinese text rendered DejaVu Sans → fixed at the importer root (CADGF #410/#412); the temporary
  image-side fontconfig bridge retired (#101/#103); macOS-only `ST*` families remapped at the render
  layer; explicit `STKaiti`/`STHeiti` normalized (#413). **Done.**
- **Authentic 仿宋 visual** (CJK §6, was deferred from #104): Zhuque made *available* + OFL-compliant
  (#104), then *preferred* (CADGF #414 reorder) and *resolved* (#105 bump). **Done** — the full
  available → OFL-compliant → preferred → resolved chain.
- **Grayscale plot style + sheet-readiness** (#100 PR body): `style=acad-plot` grayscale plot-raster
  profile + the ~380-line sheet-readiness audit tool + the report-view sheet fix (split to #107). **Done.**
- **Committer refactor** (#371): top-level INSERT loop extracted from `dxf_block_entry_committers.cpp`
  into `dxf_top_level_insert_committers.{cpp,h}`, behavior-preserving. **Done.**
- **Cross-repo off-main hygiene** (#3216): the MetaSheet2 consumer-publish gated to `push:main`, removing
  the off-main-pact-version *cause* (provider-side #869 `--main-branch` already neutralized the *effect*).
  **Done.**

## 3. Verification (in-transcript evidence only)

- **All PRs merged with green CI** on the current base (the SHAs in §1; CADGF #371 was rebased onto
  current `811d7e9` and re-run, replacing the stale April badge with current-run-ID greens — Build Core
  ×3 + Local CI + Qt + Exports/Validation).
- **`cjk_text → Zhuque` proof** — the render-image `build-and-smoke` log (post-#105) reads
  `cjk_text font_resolution OK (resolved=Zhuque Fangsong)` (was `Noto Serif CJK SC`); golden e2e green
  (non-blank + deterministic across 2 passes).
- **OFL-license proof** — the same log shows `ZhuqueFangsong-OFL.txt (4389 bytes)` fetched into
  `services/render/fonts/` (the file that previously *failed*), now enforced by the
  `require_license_with_font` build guard (#104) so a font-without-license state fails the build.
- **Plot-style / sheet orthogonality (#100)** — a mock-based test (runs in CI; pytest **100 passed**)
  proves `style=acad-plot` leaves the sheet-mode / resolved-view headers unchanged (detected/fallback
  identical to the source style); a real-render `@needs_render_cli` test covers the same end-to-end
  locally.
- **#371 independent verification** — the owner's current-main merge simulation: clean merge onto
  `811d7e9`, local build (`BUILD_EDITOR_QT=OFF`) + 22/22 documented tests + a 26/26 broader DXF/editor
  subset, `git diff --check` clean — with a **current-drift control**: the 7 broader-suite failures
  reproduce on pure `origin/main`, so they are main drift, not #371 regressions.

## 4. Deferred / out-of-scope / owned-elsewhere (honest remainder)

None of these is an in-scope/unowned/unfinished gap; each is a flagged decision, a parallel session's
work, or a separate line:

- **kai/hei end-to-end golden** — *deferred by decision* (CJK §6): no SimSun/KaiTi/SimHei golden gates
  explicit kai/hei e2e; proportionate to rare styles; advisory qt coverage + render-image no-regression
  is the chosen boundary.
- **`cad_package` pending/TTL state machine** — *v0 simplification* (render contract): v0 quarantines a
  missing payload instead of the full pending-state + TTL machine. A deliberate v0 decision.
- **Importer portable-descriptor refactor** — *not warranted* (CJK §6): the render-layer `ST*` mapping is
  the established, sufficient architecture; the importer keeps macOS names for editor parity.
- **Render diagnostics #108 / #109 / #110** (semantic-class / G11 AutoCAD-comparison boundary / X3
  color-class) — *in-flight on a parallel session*; named for completeness, not part of this closeout
  (don't-disrupt-parallel-lines).
- **VemCAD roadmap P2–P5** (workbench God-module split, desktop shell, router productization, Qt role
  convergence, per `VEMCAD_PLAN_PROGRESS_STATUS_20260528.md`) — *separate lines*, out of this render/font
  line. P1 was "用户已主动 CLOSE 此线 at milestone" — the precedent: lines close at milestones.

## 5. Net state

The CAD render/font line is **complete**. Render correctness for empty-style + explicit `ST*` families,
the Zhuque 仿宋 available→OFL-compliant→preferred→resolved chain, the grayscale plot style + sheet-readiness
audit, the committer refactor, and the cross-repo off-main hygiene are all on `main` with the verification
in §3. The discriminating scan (render contract + CJK §6) surfaced **no in-scope, unowned, unfinished
item** — so there is nothing left to build on this line; the remainder in §4 stays parked by decision,
ownership, or scope.
