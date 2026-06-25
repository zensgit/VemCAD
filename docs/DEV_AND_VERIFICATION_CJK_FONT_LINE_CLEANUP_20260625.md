# DEV & VERIFICATION — CJK font line: remaining-dev plan + cleanup

Date: 2026-06-25 · Scope: VemCAD render image + CADGameFusion render layer.
This is the development plan **and** verification record for the *remaining* work on the
CJK-font line after the temporary image-side fontconfig bridge was retired.

## 1. The line so far (context)

The render service rendered empty-style Chinese DXF text in **DejaVu Sans** on the Linux
render host (no CJK glyphs / wrong typeface), because the importer baked macOS-only family
names the Linux image didn't know. Fixed across:

| PR | Role |
|---|---|
| VemCAD #93 | golden gate — catches `cjk_text → DejaVu Sans` |
| VemCAD #95 | temporary image fontconfig alias (`STFangsong`/`STSong` → CJK serif) |
| CADGF #410 → VemCAD #99 → #101 | importer root fix (empty-style) + bump + drop `STFangsong` alias |
| CADGF #412 → VemCAD #102 → **#103** | `STSong` normalized at the render layer + bump + **delete the whole alias conf** (`#103` in flight) |

`resolveTextFamily()` (CADGF render layer) is the home of the mapping: macOS-only ST*
families are remapped to portable host families on non-macOS; macOS keeps the real ones;
the importer is unchanged (editor parity).

## 2. Remaining-dev plan (this work)

| Item | What | Repo | Status | Gating |
|---|---|---|---|---|
| **A** | **#103** alias-conf deletion | VemCAD | in flight | render-image gate; **holds for 合** |
| **B** | **STKaiti / STHeiti** normalization | CADGF render layer (**#413**) | done, PR'd | advisory qt assertion |
| **C** | **Zhuque 仿宋 fetch** repair | VemCAD `fetch_fonts.sh` (this PR) | done, verified | cosmetic; render-image |

Sequencing: A is independent and in flight. B and C are independent of each other and were
developed in parallel. Each lands on an explicit **合**.

## 3. Item B — STKaiti / STHeiti normalization (CADGF #413)

**Problem.** `resolveTextFamily()` remapped only the *song/仿宋* families
(`STFangsong`/`STSong` → `defaultTextFamily()`). Explicit 楷体/黑体 styles still baked
`STKaiti`/`STHeiti`, absent on Linux → DejaVu Sans.

**Why not reuse `defaultTextFamily()`.** It is **song/serif only**. kai and hei are different
typeface classes, so each needs its own host-probed resolver (same QFontInfo pattern):
- `defaultKaiFamily()` — 楷 → `LXGW WenKai` (bundled OFL) with a CJK-serif fallback (kai ≈ serif > sans); never DejaVu Sans.
- `defaultSansFamily()` — 黑/sans → `Noto Sans CJK SC` (guaranteed via `fonts-noto-cjk`); a CJK **sans**, never a Latin sans or a serif.

`resolveTextFamily` maps `stkaiti → defaultKaiFamily()`, `stheiti → defaultSansFamily()`
(non-macOS only). **Result: no macOS-only ST* family reaches a Linux render host unmapped.**

**Verification.** `test_qt_document_commands` asserts (non-macOS) `resolveTextFamily("STKaiti")
== defaultKaiFamily()` and `!= "STKaiti"`, same for `STHeiti → defaultSansFamily()`, + macOS
passthrough. **Honest boundary:** advisory (CADGF has no gating path for Qt tests —
`qt-tests-trial` is `continue-on-error`, `local_ci.sh` builds `BUILD_EDITOR_QT=OFF`), matching
`STFangsong`/`STSong`'s existing coverage. The VemCAD golden gate exercises **empty-style**
`cjk_text` only — it does **not** test explicit kai/hei, so render-image green confirms *no
regression*, not these paths. (A SimSun/KaiTi/SimHei golden would gate them e2e; deliberately
out of scope — proportionate to rare explicit styles.)

## 4. Item C — Zhuque 仿宋 fetch repair (this PR)

**Problem.** `fetch_fonts.sh` pinned `ZhuqueFangsong-Regular.ttf` at Zhuque **v0.214**, which
404s (that release never existed; latest is v0.212). With Zhuque absent, `defaultTextFamily()`
on Linux fell to `Noto Serif CJK SC` — gate-correct but not the **preferred 仿宋** visual.

**Change.** Zhuque v0.212+ ships a release **ZIP** (`ZhuqueFangsong-v0.212.zip`), not a bare
`.ttf`. Repointed the pin to that ZIP and added `fetch_zip_ttf()` (curl → `unzip -j` the named
`.ttf` → fonts dir). Non-fatal on failure (Noto still covers CJK). LXGW WenKai's pin (v1.510)
still resolves (200) and is unchanged.

**Verification.**
- `bash -n services/render/tools/fetch_fonts.sh` — OK.
- Functional extraction test against the real v0.212 ZIP: `unzip -o -j … ZhuqueFangsong-Regular.ttf`
  → **8,824,084 bytes extracted OK**.
- End-to-end: render-image must stay green (`cjk_text → Noto Serif CJK SC`, golden 0 failures).
  Zhuque is *preferred-if-present*, so its presence is a visual upgrade, not a gate requirement.

## 5. Net state

After A + B + C land, the CJK-font line is fully clean:
- **No image-side fontconfig bridge** (the conf + Dockerfile `COPY` are gone — #103).
- **All macOS-only ST\* families** (`STFangsong`/`STSong`/`STKaiti`/`STHeiti`) are remapped to
  typeface-class-correct host families at the CADGF render layer; the importer is untouched.
- The preferred **仿宋 (Zhuque)** visual is restored on the render host (Item C), with
  `Noto Serif CJK SC` as the guaranteed fallback.

## 6. Out of scope / notes

- The importer still bakes macOS ST* names (editor parity); the render layer maps them. A
  deeper refactor (importer emits portable descriptors) is not warranted — the render-layer
  mapping is the established, sufficient architecture.
- Explicit kai/hei aren't gated end-to-end (no SimSun/KaiTi/SimHei golden) — proportionate to
  rare styles; advisory qt coverage + render-image no-regression is the chosen boundary.
- Each PR (A/#103, B/#413, C/this) holds for an explicit **合**; nothing self-merges.
