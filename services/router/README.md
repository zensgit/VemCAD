# VemCAD Router Service

Product-facing entrypoint for the Router service boundary.

Canonical contract
- [Router HTTP contract](../../docs/VEMCAD_ROUTER_CONTRACT.md)
- [Folder-local contract entry](./CONTRACT.md)

This folder represents the product-layer service contract for:
- health / readiness
- convert task submit
- task status and manifest retrieval
- project / document / version history listing

Intentionally out of contract here:
- importer plugin shared-library paths
- `convert_cli` selection
- output directory naming
- current storage layout in the reference implementation

Repository split note
- [REPO_POINTER.md](./REPO_POINTER.md)
