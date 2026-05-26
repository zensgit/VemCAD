#!/usr/bin/env node
// solve_cli.mjs — service entry for the v1 solver (Tier 1 / Router /solve prototype).
//
// Reads a VEMCAD-PROJECT JSON (file arg, or stdin when arg is omitted / "-"),
// runs the full local loop via solveProject with the REAL CLI solve runner, and
// writes a stable result envelope as JSON to stdout. Exit codes let a host tell
// input errors from solve failures apart:
//   0 — solved
//   1 — solve ran but failed (SOLVE_UNSATISFIED / SOLVE_FAILED)
//   2 — bad input (malformed JSON, or an invalid / unsupported VEMCAD-PROJECT)
//
// This is the unit any /solve host (the python Router, the Electron shell, or a
// direct CLI) shells out to — it reuses the JS adapter / writeback, so no solver
// logic is re-implemented across the language boundary. Needs VEMCAD_SOLVE_BIN /
// VEMCAD_SOLVE_LIBPATH for the real solver binary.
import fs from 'node:fs';
import { solveProject } from '../solver/index.js';
import { createCliSolveRunner } from '../solver/runner.js';

function readInput() {
  const arg = process.argv[2];
  const raw = arg && arg !== '-' ? fs.readFileSync(arg, 'utf8') : fs.readFileSync(0, 'utf8');
  return JSON.parse(raw);
}

let project;
try {
  project = readInput();
} catch (err) {
  process.stdout.write(`${JSON.stringify({ ok: false, error_code: 'INVALID_INPUT', error: err?.message ?? String(err), diagnostics: [] })}\n`);
  process.exit(2);
}

// Input-validation failures (bad/old/unknown-unit project) are input errors
// (exit 2), like a JSON parse error; only an actual solve failure is exit 1.
const INPUT_ERROR_CODES = new Set(['INVALID_PROJECT_FORMAT', 'UNSUPPORTED_PROJECT_VERSION', 'UNSUPPORTED_PROJECT_UNIT']);

const result = solveProject(project, { runner: createCliSolveRunner() });
process.stdout.write(`${JSON.stringify(result)}\n`);
if (result.ok) process.exit(0);
process.exit(INPUT_ERROR_CODES.has(result.error_code) ? 2 : 1);
