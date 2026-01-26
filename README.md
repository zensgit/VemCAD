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
