# VemCAD

VemCAD is the product repo for the CAD application. It consumes CADGameFusion as the geometry/core layer
and keeps routing/preview services separate for licensing and deployment flexibility.

## Repository layout
- `apps/desktop/`: desktop shell (VemCAD.app / Windows builds).
- `apps/web/`: web viewer / lightweight editor.
- `services/router/`: DWG/DXF conversion and preview pipeline (headless).
- `docs/`: architecture and dev notes.
- `deps/`: local dependencies (e.g., CADGameFusion via submodule).

## Core dependency
CADGameFusion is the stable geometry core (C API boundary in `core_c`).
This repo consumes CADGameFusion as a dependency rather than vendoring it.

Recommended options (choose one):
- Git submodule (local or remote).
- vcpkg/CMakelists package reference.

## Quick start (local submodule)
From this repo root:
```
# Example (local path)
# git submodule add /path/to/CADGameFusion deps/cadgamefusion
```

## Build + dev
For now, build the core and tools from the CADGameFusion repo, then point VemCAD apps to the artifacts.
See `docs/ARCHITECTURE.md` for how the pieces connect.

Local build helper:
```
./scripts/dev_build.sh
```

## Design Docs
- `docs/ARCHITECTURE.md`: current top-level layer view.
- `docs/VEMCAD_MODULE_DESIGN.md`: module boundaries and target product architecture.
- `docs/VEMCAD_DEVELOPMENT_PLAN.md`: phased execution plan from current repo state.
- `docs/VEMCAD_PROJECT_RUNTIME.md`: product runtime boundary and `Project -> Document` derivation model.
- `docs/VEMCAD_ROUTER_CONTRACT.md`: minimum product-layer Router HTTP contract.
- `docs/VEMCAD_WORKBENCH_SPLIT_PLAN.md`: Web workbench split and migration plan.
- `docs/VEMCAD_APP_P2_WORKBENCH_SPLIT_TASKBOOK_20260626.md`: current-main execution taskbook for the next safe P2 workbench split slices.
- `docs/VEMCAD_VERIFICATION_PLAN.md`: validation matrix and gate strategy.

## Product-layer Web facades
- `apps/web/app.js`: product-layer Web bootstrap facade for editor/preview mode switching.
- `apps/web/workbench/contracts/index.js`: stable workbench contract exports.
- `apps/web/preview/runtime/contracts/index.js`: stable preview runtime contract exports.
