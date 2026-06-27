# VemCAD App Desktop / Router Readiness Taskbook

Date: 2026-06-27

Status: execution taskbook; no runtime change in this document.

Baseline:
- VemCAD `origin/main`: `5a7c5e0`
- `deps/cadgamefusion` gitlink on that baseline: `4327230`
- Previous line closed: P2 workbench split through S4, with S5 deferred until a product need justifies the risky `bootstrapCadWorkspace` runtime extraction.

## 1. Decision

Open the next line as **Desktop / Router local readiness**.

This line should not reopen the completed web workbench split, and it should not jump to cloud routing. The product value now is to make the local desktop application path easier to run, verify, and package around the existing Router and CADGameFusion web viewer.

## 2. Current State

| Surface | Live state on baseline | Consequence |
| --- | --- | --- |
| Desktop shell | Product repo has `apps/desktop/README.md`; the working Electron shell still lives in CADGameFusion under `tools/web_viewer_desktop/main.js`. | Do not assume VemCAD already owns desktop runtime code. |
| Product router | `services/router/launcher.mjs` and `main.mjs` supervise the CADGameFusion reference Python router. | VemCAD already owns the product-side Router process boundary. |
| Router contract | `services/router/CONTRACT.md` documents `/health`, `/convert`, `/jobs/{job_id}`, and `/artifacts/{artifact_id}`. | Contract guards can be added in VemCAD without changing CADGameFusion. |
| Solve service | `services/solve/README.md` is a placeholder for future hosted solver orchestration. | Keep it out of this line. |
| Web workbench | P2 S1-S4 are closed and verified; S5 is explicitly deferred. | Do not continue refactoring the web bootstrap as the next default move. |

## 3. In Scope

1. Local Router lifecycle evidence.
2. Product-side Router launcher contract guards.
3. Minimal desktop/router bridge scoping for a packaged local app.
4. Documentation and tests that protect the current dependency direction.

## 4. Out Of Scope

1. Cloud or multi-user Router orchestration.
2. Database-backed job storage, OAuth, or remote worker pools.
3. Rewriting the Python reference router.
4. Moving the Electron shell from CADGameFusion into VemCAD before the ownership boundary is designed.
5. Broad desktop UI or packaging redesign.
6. Converter/plugin path transport changes.
7. Web viewer business-logic refactors.
8. Reopening P2 S5 unless a product need makes the risk worthwhile.

## 5. Stable Contracts To Guard

### Product Router Launcher

`services/router/launcher.mjs` should continue to expose a small supervised lifecycle:

- starts the configured Router command,
- resolves with `{ url, ready(), stop() }`,
- reports process spawn and readiness failures with stable error codes,
- treats `stop()` as idempotent best effort.

### Router HTTP Surface

`services/router/CONTRACT.md` should stay aligned with the reference Router surface:

- `GET /health`,
- `POST /convert`,
- `GET /jobs/{job_id}`,
- `GET /artifacts/{artifact_id}`.

### Desktop Shell Boundary

Until VemCAD owns desktop runtime code, CADGameFusion remains the shell implementation owner. VemCAD may add product readiness documentation or tests, but code changes inside the Electron shell must be done in CADGameFusion first and consumed by a gitlink bump.

## 6. Recommended Slices

### R0 - Taskbook And Index

Repo: VemCAD

Deliverables:
- this taskbook,
- README index entry.

Verification:
- `git diff --check`.

### R1 - Product Router Contract Guard

Repo: VemCAD

Goal: make the product-side Router launcher safe to evolve before desktop packaging depends on it.

Deliverables:
- unit tests under `services/router/tests/`,
- a mocked-process launcher test for the `{ url, ready, stop }` shape,
- failure tests for spawn failure and readiness timeout error codes,
- an idempotent `stop()` test,
- a contract inventory test that checks `services/router/CONTRACT.md` still names the four stable routes.

Verification:
- `npm test`,
- no CADGameFusion code changes.

Merge policy:
- VemCAD-only PR, owner/branch-rule gated.

### R2 - Real Reference Router Smoke

Repo: VemCAD

Goal: prove VemCAD can launch the CADGameFusion reference Router in a developer environment without turning that proof into a brittle default test.

Deliverables:
- an opt-in smoke script that starts the real CADGameFusion Router,
- polls `/health`,
- tears down cleanly,
- emits explicit SKIP when Python or Router prerequisites are absent.

Verification:
- smoke run in one real local environment,
- smoke not added to default `npm test` until CI prerequisites are known.

Merge policy:
- VemCAD PR after R1.

### R3 - Desktop Shell Cleanup Scoping

Repo: CADGameFusion first, then VemCAD gitlink bump if code changes land.

Goal: inspect the current Electron shell lifecycle and decide whether any local packaging cleanup is actually needed.

Deliverables:
- read-only finding note or taskbook update,
- if code is needed, a CADGameFusion PR with focused tests,
- a VemCAD gitlink bump after CADGameFusion merge.

Verification:
- desktop smoke relevant to the changed behavior,
- VemCAD consumer verification after bump.

Guardrail:
- do not duplicate VemCAD `services/router/launcher.mjs` into CADGameFusion unless the ownership boundary is explicitly changed.

### R4 - Router Launcher Dedup Design Lock

Repo: VemCAD or cross-repo design doc.

Goal: decide whether launcher logic should remain product-side only or whether a shared lower-layer launcher core belongs in CADGameFusion.

Entry condition:
- R1 and R2 evidence exists,
- R3 has confirmed the desktop shell's real needs.

Non-goal:
- no implementation until the ownership decision is ratified.

## 7. Definition Of Done For This Line

The line is complete when:

1. Product Router lifecycle is covered by VemCAD tests.
2. At least one real local Router launch smoke has been run and recorded, or the missing prerequisite is explicitly documented.
3. Desktop shell ownership is documented with no hidden dependency-direction inversion.
4. Any CADGameFusion desktop change has a matching VemCAD gitlink bump and consumer verification.
5. Cloud/multi-user Router work remains deferred unless separately opted in.

## 8. Recommended Next Move

Start with R1.

It is small, VemCAD-only, and gives the next desktop/app work a protected product Router boundary before any package or UI work depends on it.
