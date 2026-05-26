# VemCAD Submodule Hygiene Plan (2026-05-26)

## Why this exists

The **Project Runtime / headless solve API** line is closed at a clean milestone
(PRs #2–#6 merged). The next *user-visible* step — a **live solver loop in the web
viewer** — lives in the `deps/cadgamefusion` submodule, which is currently tangled.
This plan **regularizes the submodule first**, so the solver-UI work lands on clean
ground and so a pre-existing fresh-clone breakage gets fixed.

> Boundary (decided 2026-05-26): the interactive web viewer's live solver loop
> belongs to the **submodule line**, not the (now-closed) product-runtime line.

This document is the **read-only audit + plan only**. No commits, pushes, pointer
changes, or prunes have been performed.

## Audit findings (read-only, 2026-05-26)

Submodule remote: `zensgit/CADGameFusion`. Branch `main`, **ahead 75 / behind 0** of
`origin/main` (origin/main tip = `1fceead`).

1. **The 75 unpushed commits are ALL the DXF/DWG render-fidelity line** — hatch
   patterns, MTEXT, fonts/SHX, the libdxfrw DWG reader, dimensions, canvas. **None**
   are solver/constraint commits.
2. **VemCAD's submodule pointer `b6f3917` is UNPUSHED on CADGameFusion** (it is the
   local `main` HEAD, not an ancestor of `origin/main`). Consequence: a fresh
   `git clone --recursive` of VemCAD **cannot resolve the submodule**. ← latent
   breakage to fix.
3. **The solver UI is ALREADY on `origin/main`** (commit `07beb83`:
   `ui/solver_action_panel.js` + `solver_action_flow_banner.js` +
   `solver_action_flow_console.js` + its smoke). It is **not** in the 75-commit
   backlog. So a solver-loop branch cut from CADGameFusion `origin/main` already has
   the UI present (display-only — see the prior data-flow map).
4. **The dirty working tree is a *different* line's WIP** — web-runtime-hardening /
   bootstrap / offline (`app.js`, `service-worker.js`, `web_viewer_desktop/main.js`,
   several `editor_*_smoke.js`, untracked `legacy_app_bootstrap.js`,
   `product_bootstrap_import_graph.js`, `service_worker_*_smoke.js`, fixtures) plus
   **one** minor modified solver smoke (`solver_action_panel_smoke.js`). It is NOT
   solver-feature work and NOT part of the 75 DXF commits.
5. **2 stashes**: fillet/circle editor WIP on `codex/step183-nightly-gate`
   (unrelated to this plan).
6. **45 prunable worktree registrations are DANGLING** — they point at
   `/Users/huazhou/...` (another machine; absent here) and are marked `prunable`.
   **Separately, 22 local branches have `[gone]` upstreams** (their `origin`
   remote-tracking branch was deleted — merged + cleaned up upstream). These are two
   distinct counts (a prunable worktree ≠ a gone-upstream branch). Hygiene noise only.

## Cleanup plan

> ⚠️ Step A assumes you have push rights to `zensgit/CADGameFusion` and that the
> DXF-line owner is ready to ship the 75 commits. Confirm both before starting; do
> not push speculatively.

### A. What to push to CADGameFusion first (as PR(s))

- **The 75 unpushed DXF/DWG render-fidelity commits on `main`.** This is the DXF
  line's shipping pass. Cut an **isolated worktree off CADGameFusion `origin/main`**
  and ship them — either as one "DXF render-fidelity batch" PR, or split by
  sub-theme (hatch / MTEXT / DWG-reader / dimensions / fonts) for reviewability.
- **Solver UI**: nothing to push — already on `origin/main` (`07beb83`).

### B. What WIP to stash / split (leave untouched for now)

- The **dirty working tree** (web-runtime-hardening / bootstrap / offline) is a
  different line's WIP. **Leave it untouched throughout this plan.** It stays local
  on top of whatever `main` becomes; the pointer bump does **not** move or clean it
  ("bump pointer" ≠ "clean tree"). Its owner triages it on its own branch.
- The **2 stashes** and the merged `codex/*` branches: their owner's call; not this
  pass.
- The **1 modified solver smoke** (`solver_action_panel_smoke.js`): fold into the
  future solver-loop work, not this hygiene pass.

### C. When the parent (VemCAD) updates the submodule pointer

- **Only after** the 75 are pushed and CADGameFusion `origin/main` advances to
  include them. Then bump VemCAD's pointer to a commit that is **provably on
  CADGameFusion `origin/main`**, as a **single deliberate commit containing only the
  pointer change** (gitlink-only diff), via an isolated worktree off VemCAD
  `origin/main`, as its own small PR.
- This bump also **fixes the current fresh-clone breakage** (finding #2).
- Never bump the pointer to an unpushed commit (that is today's broken state).

### D. How to avoid a PR #2-style submodule pointer accident

PR #2's actual cause was *branching VemCAD off a stale local main, which dragged the
submodule pointer*. Concrete guardrails:

1. **Isolated worktrees off `origin/main`** — in CADGameFusion exactly as in VemCAD.
   Never commit feature work onto the 75-ahead local `main`.
2. **Pointer bump = a single, gitlink-only commit.** Never let a VemCAD *feature*
   branch carry an incidental pointer change.
3. **Guardrail check before any bump** — in CADGameFusion run:
   `git merge-base --is-ancestor <new-pointer> origin/main` (exit 0 = fetchable).
   This single check would have caught PR #2's leak; CI can enforce it.
4. **Bonus hygiene** — `git worktree prune` in the submodule clears the 45 dangling
   `huazhou` worktree registrations; the 22 `[gone]`-upstream branches + stale
   stashes are their owner's to prune.

### Then (separate effort — NOT this plan): the user-visible solver loop

Off CADGameFusion `origin/main` (which already has the solver UI), wire the live
loop entirely inside the submodule:
`solver.export-project` (→ CADGF-PROJ) → `solve_from_project` (submodule's own
solver binary) → `solver.import-diagnostics` → **geometry writeback**. This does
**not** route through the product `/solve` service.

## Status

Read-only audit + plan only — **no commits / pushes / pointer changes / prunes
performed.** Executing A–D requires confirming push rights and the DXF-line owner's
sign-off (the 75 commits are their backlog).
