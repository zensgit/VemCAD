# VemCAD Architecture

## Goals
- CADGameFusion is the geometry core with a stable C API boundary (`core_c`).
- VemCAD focuses on product UX, storage, collaboration, and deployment.
- Heavy conversion (DWG) stays server-side for reliability and licensing clarity.

## Layers
1. Core (CADGameFusion)
   - Stable ABI: `core_c`.
   - Document is the single source of truth.
2. Services
   - Router/preview service accepts DWG/DXF and emits Document + preview formats (JSON/glTF).
3. Clients
   - Web: light preview, measure, annotate, diff.
   - Desktop: heavier workflows, file integration, local cache.

## Data flow
DWG/DXF -> Router -> Document JSON + preview (glTF) -> Web/desktop viewer

## Licensing boundary
- CADGameFusion remains internal/proprietary.
- Any GPL-only converters (e.g., LibreDWG) live in a separate service repository if used.
