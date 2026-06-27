# Render Fidelity — Fork A (continue #100) scoping taskbook

> Status: **SCOPING / opt-in pending**. Doc-only. No code in this PR.
> Repo: VemCAD `services/render/` · base `origin/main` (`5a7c5e0`, post-#100/#107) · branch `claude/render-fork-a-taskbook`.
> Convention: this is the planning half; the chosen task gets its own `DEV_AND_VERIFICATION_*` impl record.

## 0. Why this doc exists
The owner picked **Fork A — “continue #100 follow-ups”** over Fork B (AutoCAD reference comparison closed-loop). This taskbook grounds the current state, **surfaces the one discriminating question (use case)**, ranks the candidate follow-ups by that question, and asks for a per-phase opt-in on the first task. It deliberately does **not** pre-commit to code.

## 1. Grounded state (verified on `origin/main`)
- **#107 MERGED** 06-26 08:46 (`a48eb39`) — `fix(render): read nested render_cli_report.view for sheet detection` (the [P1] bug split out of #100).
- **#100 MERGED** 06-26 16:34 (`7c20b75e`) — `feat(render): grayscale plot style + sheet-readiness audit`. It added:
  - `style=acad-plot` — a **PNG-only neutral grayscale** post-process (`renderer.py:136 apply_acad_plot_style`, applied at `:305`). Its docstring states the intent explicitly: neutralise colour **so fidelity-comparison metrics and human review are not dominated by bright annotation ink**. Style enters the cache key (`as_dict`) so a coloured render can't satisfy a plot request. `_ALLOWED_STYLE = ("source", "acad-plot")` (`renderer.py:23`).
  - `services/render/tools/sheet_readiness_audit.py` (380 lines) — an **ops/audit tool**: renders every DXF in a runtime-supplied directory twice (`view=extents` + `view=sheet`) through a **running** vemcad-render service, emits JSON + contact sheets. By design it takes a directory at runtime; **training/customer drawings are NOT committed**.
- **`view` default is `extents` everywhere** (`main.py:214/366 Query("extents")`, `renderer.py:68`). `view=sheet` (plot preview: detect 图框 window at extents, re-render — `renderer.py:216-240`) is opt-in. The audit tool exists to answer one product question: **is `view=sheet` good enough to become the default?**
- **CI**: `render-tests.yml` runs `pytest services/render/tests -q` + `pytest tools/render_regression/tests -q` on a fast per-PR gate (numpy/PIL installed; render_cli-dependent tests auto-skip). **Additions to `services/render/tests/test_plot_style.py` are auto-run — no Yuantus-style CI-registration gotcha here.**
- **render_regression scaffolding** already exists (`tools/render_regression/baseline.py` 3-tier baselines: self / ref-render / **acad**; `ci_render_golden.py` + `ci_e2e_check.py` golden loop) — that is **Fork B territory; out of scope here**, noted only so we don't rebuild it.

## 2. The discriminating question (please answer)
Every Fork-A candidate only makes sense under a specific **use case**. #100 built one style (`acad-plot`) for **comparison** and one tool (audit) for **defaulting `view=sheet`**. So:

> **What is the next step actually for?**
> (i) **Make `view=sheet` the default preview** (advance the readiness decision #100’s audit was built for), or
> (ii) **Better plot/preview OUTPUT** (e.g. monochrome / lineweight plot styles for export), or
> (iii) **Stronger fidelity-comparison** tooling (this is Fork B — declined, listed only for contrast).

This matters because the candidates below trade off directly, and one obvious-looking task (a second plot style) is **weakly justified** until (ii) is confirmed (see A2).

## 3. Candidate backlog (ranked by defensibility)

### A1 — Advance the `view=sheet → default` readiness thread  *(most defensible; = #100’s own narrative)*
- **Why**: this is the product question #100’s 380-line audit was explicitly built to answer; nothing else in Fork A is as on-thread.
- **In-repo, no customer assets** sub-options:
  - **A1a** — commit a **tiny synthetic DXF fixture corpus** + a CI-runnable readiness smoke that exercises the audit’s pure logic (`image_stats`, sheet-window detection) against fixtures, turning a today-operator-only tool into a repeatable in-CI signal.
  - **A1b** — harden/observe **sheet detection** (`renderer.py:216-240` 图框 window) for the edge cases that currently block flipping the default (e.g. no title block, multi-frame, rotated sheets) — with tests.
- **Operator-gated remainder (flagged, not in scope of the in-repo task)**: the *actual* “ready to be default” verdict needs a **real training/customer drawing corpus + running service** — same operator-evidence pattern as pact / CAD-helper. A1a/A1b move the in-repo parts; the go/no-go on the default flip stays owner/ops-gated.
- **Risk**: low (additive; default unchanged until a separate, evidence-backed flip).

### A2 — Plot-style OUTPUT extension (e.g. `acad-mono` monochrome, or lineweight)  *(only if use case (ii) is real)*
- **Open question first**: grayscale `acad-plot` was chosen *for comparison*; **monochrome is strictly worse for comparison** (threshold discards tonal info). It only adds value as **plot/preview OUTPUT**. So A2 needs a stated output use case — do **not** build it on the strength of #100’s “this is grayscale, not monochrome” line, which is a disambiguation, not a roadmap.
- **Fidelity caveat**: a cheap PNG grayscale→threshold destroys anti-aliased linework and can drop thin light lines; *faithful* monochrome maps entities to black **pre-raster** (render_cli side), which a post-process can’t reproduce. So “done right” is more than a ~15-line mirror of `apply_acad_plot_style`.
- **If approved**: mechanically clean — add to `_ALLOWED_STYLE`, add `apply_*_style`, refactor the `if params.style == "acad-plot"` site (`renderer.py:305`) into a small dispatch map, add `test_plot_style.py` cases (assert pure black/white, size + alpha preserved). `parse()`/cache-key/HTTP `style=` plumbing already generalise.
- **Risk**: low mechanically, but **medium product-justification** + a real fidelity caveat.

### A3 — sheet-readiness audit productization (report/ops surface)
- Turn the audit’s JSON into a shareable report / ops view. **Depends on the same operator drawing assets as A1’s remainder**; mostly valuable once A1a gives a repeatable input. Lower priority than A1a.

### DROPPED — CJK/STSong font-fallback cleanup
- **Owned by concurrent sessions** — worktrees `codex/render-cjk-stfont-alias`, `claude/bump-cadgf-stsong`, `claude/drop-cjk-alias-conf` + `docs/DEV_AND_VERIFICATION_CJK_FONT_LINE_CLEANUP_20260625.md` / `..._RENDER_FONT_LINE_COMPLETION_20260626.md`. Do not touch (parallel-session discipline).

## 4. Recommendation & opt-in request
**Recommend A1a** (synthetic fixture corpus + CI readiness smoke) as the first task: it is the most on-thread with #100, fully in-repo, low-risk, and produces a durable repeatable signal — while honestly leaving the operator-gated “flip the default” verdict for later evidence. **A2 only if** the owner confirms a plot-OUTPUT use case (question (ii)).

**Need from owner (per-phase opt-in):** answer §2’s use-case question and pick the first task (A1a / A1b / A2 / A3). On selection I’ll write the impl-side `DEV_AND_VERIFICATION_*` and implement in this worktree.

## 5. Verification approach (for whichever task is picked)
- New tests land in `services/render/tests/` (auto-run by `render-tests.yml`); render_cli-dependent assertions guarded so they auto-skip on the fast gate.
- A1a fixtures: synthetic/committed only (no customer drawings in git).
- No change to the `view=extents` default and no geometry change in any candidate; `style`/`view` remain opt-in. Default-flip (if ever) is a separate, evidence-backed PR.
