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

## Launcher (Phase 1 — desktop / local single-user)

`launcher.mjs` + `main.mjs` are a thin **supervised launcher** for the CADGameFusion
reference Python router (`deps/cadgamefusion/tools/plm_router_service.py`). They start it
on a loopback port, poll `/health` for readiness, and manage its lifecycle.

Run it:

```
node services/router/main.mjs        # starts the Python router at http://127.0.0.1:9000
```

Config via env: `ROUTER_HOST` (default `127.0.0.1`), `ROUTER_PORT` (`9000`), `PYTHON`
(`python3`), `ROUTER_PY` (path to `plm_router_service.py`), `ROUTER_AUTH_TOKEN` (optional,
passed through), `ROUTER_EXTRA_ARGS` (extra python flags, e.g. `--out-root … --convert-cli …`),
`ROUTER_START_TIMEOUT_MS` (`15000`).

Programmatic: `startRouterLauncher({ command, args, host, port, ... }) -> { url, ready(), stop() }`.
- `ready()` resolves with the base url once `/health` is reachable, or rejects with a
  `RouterLaunchError` (`ROUTER_START_FAILED` / `ROUTER_START_TIMEOUT` / `ROUTER_START_NOT_CONFIGURED`).
- `stop()` signals the child (SIGTERM, escalating to SIGKILL) and resolves once it exits;
  idempotent.

### Why a launcher, not a `services/solve`-style per-request spawn

The Python router is a **long-lived stateful server** (queue + worker pool + in-memory
tasks across `/convert → /status → /manifest`), so it is started **once** and supervised —
unlike `services/solve`, which is stateless and spawns its CLI per request.

### Scope (deliberate) — what this is NOT

No reverse proxy and no new endpoints (the Python router owns `/convert`, `/status`,
`/manifest`, `/history`, …); no cloud / multi-user / DB / OAuth; no Electron changes; no
router rewrite. The Electron desktop shell already spawns the same Python router with the
same loopback/`/health`/timeout conventions — this launcher is the standalone, testable
product-layer equivalent (a module the shell could later reuse). Actually converting still
requires the router's converter (`convert_cli` + plugins), which is out of scope here.

### Tests

`tests/router_launcher.test.js` exercises start/readiness/timeout/crash/stop against a
pure-node fake router stub (`tests/fixtures/fake_router.mjs`) — no Python, no submodule, no
converter — so it runs in the `product_tests` **core** job (`npm test`).

Repository split note
- [REPO_POINTER.md](./REPO_POINTER.md)
