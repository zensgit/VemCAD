#!/usr/bin/env node
// Runnable entry for the VemCAD /solve service. Listens on PORT (default 8787).
// Needs VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH for the real solver (passed through
// to solve_cli). See server.mjs for the full /solve + /health contract.
import { createSolveServer } from './server.mjs';

const port = Number(process.env.PORT) || 8787;
createSolveServer().listen(port, () => {
  process.stdout.write(`vemcad /solve listening on http://127.0.0.1:${port} (POST /solve, GET /health)\n`);
});
