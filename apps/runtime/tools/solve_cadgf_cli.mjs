#!/usr/bin/env node
// solve_cadgf_cli.mjs — solve a CADGF-PROJ (the editor's NATIVE solver-input format) DIRECTLY,
// skipping the VEMCAD-PROJECT semantic adapter that solve_cli.mjs runs.
//
// This is the editor "Solve" path (the short, native route): the editor's `solver.export-project`
// command produces a CADGF-PROJ (point entities `e<id>_<role>` + VarRef constraints); this runs the
// real solver on it and returns the solved variable values (`value.vars`, keyed by "<pointId>.x|y")
// for the editor to write back. Use solve_cli.mjs for SEMANTIC VEMCAD-PROJECT input; this one for
// already-expanded CADGF-PROJ. Needs VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH for the real binary.
//   exit 0 — solved   ·   1 — solve ran but failed   ·   2 — bad input
import fs from 'node:fs';
import { createCliSolveRunner } from '../solver/runner.js';

function readInput() {
  const arg = process.argv[2];
  const raw = arg && arg !== '-' ? fs.readFileSync(arg, 'utf8') : fs.readFileSync(0, 'utf8');
  return JSON.parse(raw);
}

function isCadgfProject(p) {
  return !!p && typeof p === 'object'
    && p.header && p.header.format === 'CADGF-PROJ'
    && p.scene && Array.isArray(p.scene.entities) && Array.isArray(p.scene.constraints);
}

let project;
try {
  project = readInput();
} catch (err) {
  process.stdout.write(`${JSON.stringify({ ok: false, error_code: 'INVALID_INPUT', error: err?.message ?? String(err) })}\n`);
  process.exit(2);
}
if (!isCadgfProject(project)) {
  process.stdout.write(`${JSON.stringify({ ok: false, error_code: 'INVALID_CADGF_PROJECT', error: 'expected a CADGF-PROJ with scene.entities and scene.constraints' })}\n`);
  process.exit(2);
}

let out;
try {
  out = createCliSolveRunner()(project);
} catch (err) {
  // binary missing / runner threw — the client can't fix it.
  process.stdout.write(`${JSON.stringify({ ok: false, error_code: 'SOLVE_FAILED', error: err?.message ?? String(err) })}\n`);
  process.exit(1);
}

const solve = { ok: out?.ok === true, iterations: out?.iterations ?? null, finalError: out?.final_error ?? null };
if (out?.ok === true) {
  process.stdout.write(`${JSON.stringify({ ok: true, value: { vars: out.vars ?? {}, solve }, analysis: out.analysis ?? null })}\n`);
  process.exit(0);
}
// Unsatisfiable / non-converged: preserve vars + analysis (conflicts) so the client can still
// triage; ok:false, exit 1.
process.stdout.write(`${JSON.stringify({ ok: false, error_code: 'SOLVE_UNSATISFIED', error: out?.message || 'solver did not converge / constraints unsatisfiable', value: { vars: out?.vars ?? {}, solve }, analysis: out?.analysis ?? null })}\n`);
process.exit(1);
