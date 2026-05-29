# Router Contract Entry

This directory owns the product-layer Router HTTP boundary.

Normative document
- [docs/VEMCAD_ROUTER_CONTRACT.md](../../docs/VEMCAD_ROUTER_CONTRACT.md)

Stabilized surface
- `GET /health`
- `POST /convert`
- `GET /status/{task_id}`
- `GET /manifest/{task_id}`
- `GET /history`
- `GET /projects`
- `GET /projects/{project_id}/documents`
- `GET /documents/{document_id}/versions`
- common JSON error model

The contract is intentionally higher level than the current reference implementation under `deps/cadgamefusion/tools/plm_router_service.py`.

Not fixed by this contract
- plugin path transport
- converter binary path transport
- on-disk artifact layout
- temporary implementation-specific response fields
