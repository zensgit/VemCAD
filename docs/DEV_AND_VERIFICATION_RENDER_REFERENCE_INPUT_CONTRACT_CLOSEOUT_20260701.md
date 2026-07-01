# Render reference input contract hardening closeout (2026-07-01)

## Scope

This closeout records the post-G11 hardening work for the AutoCAD reference-input
chain. The goal was not to improve renderer pixels directly. It was to remove
false-green paths where a reference package, request run, or route summary could
look trustworthy even though the caller had not supplied integer sizes/counts or
an explicit AutoCAD capture contract.

The actual AutoCAD equivalence gate remains external-input bound: a fresh,
matched-view AutoCAD plot/export PNG is still required before a VemCAD-vs-AutoCAD
comparison can claim visual parity.

## Landed changes

| PR | Commit | Boundary hardened | Verification |
| --- | --- | --- | --- |
| #383 | `4a96978` | Route summary counts now reject bool, fractional, negative, and non-digit count values instead of silently folding them into routing totals. | Focused route tests: 81 passed. Full render-regression tests: 230 passed. CI `pytest` + `build-and-smoke` green. |
| #384 | `6f01922` | Manifest compare artifact boundary treats `compared_count` as true only when it is a strict non-negative integer. | Focused compare tests: 17 passed. Full render-regression tests: 231 passed. CI green. |
| #385 | `010a89c` | Direct `--cases` generation rejects non-integer `expected_size`; no more `int(...)` truncation/coercion for declared reference size. | Focused batch tests: 35 passed. Full render-regression tests: 232 passed. CI green. |
| #386 | `1a6a589` | Direct `--cases` generation now requires explicit `capture_method` and `view_contract`; it no longer defaults to `plot-export` / `model-extents`. | Focused batch tests: 36 passed. Full render-regression tests: 233 passed. CI green. |
| #387 | `888a48f` | Single-case helper now requires explicit `--capture-method` and `--view-contract`; no default trust tier is invented by the helper. | Focused case tests: 3 passed. Full render-regression tests: 234 passed. CI green. |
| #388 | `f7f9f54` | Request-run evidence ignores invalid size fields and only prints returned PNG dimensions when they are positive integers. | Focused request-run tests: 14 passed. Full render-regression tests: 235 passed. CI green. |

## Current invariants

- AutoCAD capture trust is caller-declared, not inferred by helper defaults.
- Matched-view assumptions are caller-declared, not inferred from file names or
  returned PNGs.
- Reference image dimensions used as gate evidence must be positive integers.
- Route and compare counts used as artifact-boundary evidence must be
  non-negative integers.
- Diagnostic-only capture methods remain visible as diagnostics and cannot be
  promoted into an AutoCAD equivalence claim.
- Runtime view-space/framing checks remain the content-bearing guard. Manifest
  metadata can prove that required declarations exist; it cannot prove a PNG was
  truly produced by AutoCAD plot/export.

## Final code audit notes

After #383-#388, a targeted audit on `origin/main` checked the current
`tools/render_regression` AutoCAD-reference helpers for the specific false-green
patterns this line has been removing:

- No remaining `plot-export` / `model-extents` defaults exist on the reference
  manifest/request/single-case helper path.
- The remaining capture defaults are on diagnostic comparison tools
  (`compare_vs_acad.py`, `autocad_batch_compare.py`), not on the reference-input
  trust boundary.
- JSON-derived size and count fields on the reference request, compare artifact,
  route summary, and request-run evidence paths now pass through strict integer
  parsing before they affect gate evidence.

## Still deliberately out of scope

- No AutoCAD-equivalence claim is made here. That still requires a clean
  AutoCAD PLOT/EXPORTPNG reference with matched view-space.
- No private drawing was committed.
- No GUI AutoCAD automation was attempted.
- No renderer fidelity fix was made in this closeout; this was input-chain and
  evidence-chain hardening.

## Next real unlock

To resume pixel-fidelity work, provide:

1. one drawing authorized for the private VemCAD reference workflow, and
2. its fresh AutoCAD plot/export PNG with matched model-extents or explicit
   window provenance.

Then the reference-input chain can run without inventing trust: validate the
request, accept returned PNGs only with explicit contract evidence, run
`compare_vs_acad.py`, and route only true matched-view failures to renderer
investigation.
