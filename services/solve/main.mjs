#!/usr/bin/env node
// Runnable entry for the VemCAD /solve service. Listens on HOST:PORT (default
// 127.0.0.1:8787). Binds LOOPBACK by default on purpose — this prototype has no
// auth / size limit / timeout / concurrency cap and spawns the solver per request,
// so exposing it must be an explicit opt-in: set HOST=0.0.0.0 to bind all NICs.
// Needs VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH for the real solver (passed through
// to solve_cli). See server.mjs for the full /solve + /health contract.
import { createSolveServer } from './server.mjs';

const port = Number(process.env.PORT) || 8787;
const host = process.env.HOST || '127.0.0.1';
createSolveServer().listen(port, host, () => {
  process.stdout.write(`vemcad /solve listening on http://${host}:${port} (POST /solve, GET /health)\n`);
});
