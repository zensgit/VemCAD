#!/usr/bin/env node
// Runnable entry for the VemCAD router launcher: start the CADGameFusion Python router
// locally on LOOPBACK and keep it alive until SIGINT/SIGTERM. Desktop / local single-user
// only. This is a thin supervisor — it does NOT proxy or add endpoints; clients talk to
// the Python router directly at the printed url (default http://127.0.0.1:9000).
//
// Config via env:
//   ROUTER_HOST            bind host           (default 127.0.0.1 — loopback)
//   ROUTER_PORT            bind port           (default 9000)
//   PYTHON                 interpreter         (default python3)
//   ROUTER_PY              plm_router_service.py path
//                          (default deps/cadgamefusion/tools/plm_router_service.py)
//   ROUTER_AUTH_TOKEN      optional Bearer token (passed through; empty = no auth)
//   ROUTER_EXTRA_ARGS      optional extra flags, space-split, appended verbatim
//                          (e.g. "--out-root /tmp/out --convert-cli /path/to/convert_cli")
//   ROUTER_START_TIMEOUT_MS  readiness timeout (default 15000)
//
// Requires the deps/cadgamefusion submodule to be checked out (it owns the Python router)
// and python3 on PATH. To actually CONVERT, the router additionally needs its converter
// (convert_cli + plugins) — out of scope for this launcher.
import { fileURLToPath } from 'node:url';
import { startRouterLauncher } from './launcher.mjs';

const host = process.env.ROUTER_HOST || '127.0.0.1';
const port = Number(process.env.ROUTER_PORT) || 9000;
const python = process.env.PYTHON || 'python3';
const routerPy =
  process.env.ROUTER_PY ||
  fileURLToPath(new URL('../../deps/cadgamefusion/tools/plm_router_service.py', import.meta.url));

const args = [routerPy, '--host', host, '--port', String(port)];
if (process.env.ROUTER_AUTH_TOKEN) args.push('--auth-token', process.env.ROUTER_AUTH_TOKEN);
if (process.env.ROUTER_EXTRA_ARGS) args.push(...process.env.ROUTER_EXTRA_ARGS.split(/\s+/).filter(Boolean));

const launcher = startRouterLauncher({
  command: python,
  args,
  host,
  port,
  startTimeoutMs: Number(process.env.ROUTER_START_TIMEOUT_MS) || 15000,
});

let stopping = false;
async function shutdown(signal) {
  if (stopping) return;
  stopping = true;
  process.stderr.write(`\nvemcad router: ${signal} -> stopping python router (pid ${launcher.pid ?? '?'})...\n`);
  await launcher.stop();
  process.exit(0);
}
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

launcher.ready().then(
  (url) => process.stdout.write(`vemcad router: python router ready at ${url} (loopback). Ctrl-C to stop.\n`),
  async (err) => {
    process.stderr.write(`vemcad router: failed to start (${err.code}): ${err.message}\n`);
    await launcher.stop();
    process.exit(1);
  },
);
