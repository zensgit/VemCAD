# DEV & VERIFICATION — CJK font line: remaining-dev plan + cleanup

Date: 2026-06-25 · Scope: VemCAD render image + CADGameFusion render layer.
Development plan **and** verification record for the *remaining* CJK-font-line work after the
temporary image-side fontconfig bridge was retired.

> PR states drift; this doc describes **roles + verification**, not live merge status. Every PR
> below merges only on an explicit owner **合** — read "PR" as "open PR, merges on 合", whatever
> its current state when you read this.

## 1. The line so far (context)

The render service rendered empty-style Chinese DXF text in **DejaVu Sans** on the Linux render
host, because the importer baked macOS-only family names the Linux image didn't know. Fixed across:

| PR | Role |
|---|---|
| VemCAD #93 | golden gate — catches `cjk_text → DejaVu Sans` |
| VemCAD #95 | temporary image fontconfig alias (`STFangsong`/`STSong` → CJK serif) |
| CADGF #410 / VemCAD #99 / #101 | importer root fix (empty-style) + bump + drop `STFangsong` alias |
| CADGF #412 / VemCAD #102 / #103 | `STSong` normalized at the render layer + bump + delete the whole alias conf |

`resolveTextFamily()` (CADGF render layer) is the home of the mapping: macOS-only ST* families
are remapped to portable host families on non-macOS; macOS keeps the real ones; the importer is
unchanged (editor parity).

## 2. Remaining-dev plan (this work)

| Item | What | Repo / PR | Verification | Note |
|---|---|---|---|---|
| **A** | delete alias conf + Dockerfile `COPY` | VemCAD #103 | render-image green, **no bridge** | merges on 合 |
| **B** | STKaiti / STHeiti normalization | CADGF #413 | advisory qt assertion | merges on 合 |
| **C** | Zhuque 仿宋 fetch + OFL license repair | VemCAD #104 (this) | `bash -n` + extraction tested | makes Zhuque **available, not preferred** — see §4 |

A is independent; B and C are independent of each other (parallelizable). Each lands on an explicit 合.

## 3. Item B — STKaiti / STHeiti normalization (CADGF #413)

**Problem.** `resolveTextFamily()` remapped only the *song/仿宋* families (`STFangsong`/`STSong` →
`defaultTextFamily()`). Explicit 楷体/黑体 styles still baked `STKaiti`/`STHeiti`, absent on Linux →
DejaVu Sans.

**Why not reuse `defaultTextFamily()`.** It is **song/serif only**. kai and hei are different
typeface classes, so each needs its own host-probed resolver (same QFontInfo pattern):
- `defaultKaiFamily()` — 楷 → `LXGW WenKai` (bundled OFL) with a CJK-serif fallback (kai ≈ serif > sans); never DejaVu Sans.
- `defaultSansFamily()` — 黑/sans → `Noto Sans CJK SC` (guaranteed via `fonts-noto-cjk`); a CJK **sans**, never a Latin sans or a serif.

`resolveTextFamily` maps `stkaiti → defaultKaiFamily()`, `stheiti → defaultSansFamily()` (non-macOS
only). **Result: no macOS-only ST* family reaches a Linux render host unmapped.**

**Verification.** `test_qt_document_commands` asserts (non-macOS) `resolveTextFamily("STKaiti") ==
defaultKaiFamily()` and `!= "STKaiti"`, same for `STHeiti → defaultSansFamily()`, + macOS
passthrough. Confirmed on CADGF CI: `qt_document_commands_run … Passed`, Build Core ×3 green.
**Honest boundary:** advisory (CADGF has no gating path for Qt tests — `qt-tests-trial` is
`continue-on-error`, `local_ci.sh` builds `BUILD_EDITOR_QT=OFF`), matching `STFangsong`/`STSong`'s
existing coverage. The VemCAD golden gate exercises **empty-style** `cjk_text` only — it does **not**
test explicit kai/hei, so render-image green confirms *no regression*, not these paths.

## 4. Item C — Zhuque 仿宋 fetch + OFL license repair (this PR)

**Problem.** `fetch_fonts.sh` pinned the Zhuque `.ttf` at **v0.214** (404 — that release never
existed; latest is v0.212) **and** fetched the OFL license from `…/master/LICENSE` (also 404 —
master/main don't carry it; the file is `LICENSE.txt` on the tag). So the font was missing, and even
once the font is fetched, the image would carry the `.ttf` **without** its OFL license — an OFL
compliance violation, not a cosmetic warning.

**Change.**
- Font: v0.212+ ships a release **ZIP** (`ZhuqueFangsong-v0.212.zip`), not a bare `.ttf`. Repoint to
  the ZIP + add `fetch_zip_ttf()` (curl → `unzip -j` the named `.ttf`).
- License: repoint to `…/v0.212/LICENSE.txt` so the OFL license travels with the font (required).
- LXGW WenKai's pin (v1.510) still resolves (200), unchanged.

**What this does and does NOT do (the corrected scope).** This makes Zhuque correctly **available**
(font + license) in the image. It does **not** change which family `cjk_text` resolves to:
`defaultTextFamily()`'s Linux prefer order still lists `Noto Serif CJK SC` **before**
`Zhuque Fangsong`, so `cjk_text` still resolves to **Noto Serif CJK SC** (gate-correct). Making
Zhuque the *preferred* resolution — the authentic 仿宋 visual — requires a CADGF prefer-order change
(§6), deliberately **not** done here. (Prior wording claiming this PR "restores the preferred 仿宋
visual" was wrong and has been corrected.)

**Verification.**
- `bash -n services/render/tools/fetch_fonts.sh` — OK.
- Functional extraction against the real v0.212 ZIP → `ZhuqueFangsong-Regular.ttf` **8,824,084 bytes OK**.
- License URL `…/v0.212/LICENSE.txt` → **200** (master/main → 404), content is the OFL.
- **CI proof (the required one):** `fetch_fonts.sh` now **enforces** the OFL invariant — a
  `require_license_with_font` guard **fails the build** on a font-present-without-license state. So the
  render-image `build-and-smoke` run doesn't merely *log* `ZhuqueFangsong-OFL.txt` alongside the `.ttf`
  in `services/render/fonts/`, it **cannot pass without it** (the prior run showed the `.ttf` succeed
  but `…-OFL.txt` fail — that is now a hard failure, not a warning). render-image stays green
  (`cjk_text → Noto Serif CJK SC`, 0 failures).

## 5. Net state

After A + B + C land:
- **No image-side fontconfig bridge** (the conf + Dockerfile `COPY` are gone — #103).
- **All four macOS-only ST\* families** (`STFangsong`/`STSong`/`STKaiti`/`STHeiti`) are remapped to
  typeface-class-correct host families at the CADGF render layer; the importer is untouched.
- Zhuque 仿宋 is correctly **bundled + OFL-compliant** (Item C). `cjk_text` resolves to
  `Noto Serif CJK SC` (the guaranteed CJK serif); Zhuque is staged but not yet the preferred face.

## 6. Out of scope / deferred follow-ups

- **Authentic 仿宋 preferred visual** (deferred, cosmetic). To make `cjk_text` resolve to
  `Zhuque Fangsong` (a true 仿宋) instead of `Noto Serif CJK SC` (a Song serif), reorder
  `defaultTextFamily()`'s Linux prefer list to put `Zhuque Fangsong` (+ `FangSong`/`仿宋`) **before**
  `Noto Serif CJK SC`, then bump VemCAD. Now safe because Item C makes Zhuque reliably present. Not
  done here — the owner flagged Zhuque as visual-priority/deferrable.
- The importer still bakes macOS ST* names (editor parity); the render layer maps them. A deeper
  importer refactor is not warranted.
- Explicit kai/hei aren't gated end-to-end (no SimSun/KaiTi/SimHei golden) — proportionate to rare
  styles; advisory qt coverage + render-image no-regression is the chosen boundary.
- Each PR (A/#103, B/#413, C/this) merges only on an explicit owner 合; nothing self-merges.
