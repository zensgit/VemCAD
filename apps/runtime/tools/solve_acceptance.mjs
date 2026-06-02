#!/usr/bin/env node
// Independent solver acceptance (Tier 1 / C3): run the REAL solve_from_project on
// known fixtures and assert each solution satisfies its constraint (within tol)
// and is reproducible across runs (same machine). Needs the built binary +
// libcore via VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH. NOT part of `node --test`.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createProjectModel } from '../project/index.js';
import { solveProject, solveAndDeriveScene } from '../solver/index.js';
import { createCliSolveRunner } from '../solver/runner.js';

const FIXED = '2026-05-25T00:00:00.000Z';
const TOL = 1e-5;
const runner = createCliSolveRunner(); // reads VEMCAD_SOLVE_BIN / VEMCAD_SOLVE_LIBPATH

function project(entities, constraints) {
  return { ...createProjectModel({ id: 'acc', name: 'acc', units: 'mm', createdAt: FIXED, modifiedAt: FIXED }).value, entities, constraints };
}
const line = (id, a, b) => ({ id, kind: 'line', layerId: 0, line: [a, b] });
const point = (id, xy) => ({ id, kind: 'point', layerId: 0, point: xy });
const endpoints = (id) => [{ entity: id, at: 'start' }, { entity: id, at: 'end' }];
const ent = (view, id) => view.entities.find((e) => e.id === id);

const cases = [
  {
    name: 'horizontal',
    project: project([line('L1', [0, 0], [10, 5])], [{ id: 'h', type: 'horizontal', refs: endpoints('L1') }]),
    satisfied: (v) => { const l = ent(v, 'L1').line; return Math.abs(l[1][1] - l[0][1]) < TOL; },
  },
  {
    name: 'vertical',
    project: project([line('L1', [0, 0], [5, 10])], [{ id: 'v', type: 'vertical', refs: endpoints('L1') }]),
    satisfied: (v) => { const l = ent(v, 'L1').line; return Math.abs(l[1][0] - l[0][0]) < TOL; },
  },
  {
    name: 'distance',
    project: project([point('P1', [0, 0]), point('P2', [3, 0])], [{ id: 'd', type: 'distance', value: 10, refs: [{ entity: 'P1', at: 'self' }, { entity: 'P2', at: 'self' }] }]),
    satisfied: (v) => { const a = ent(v, 'P1').point; const b = ent(v, 'P2').point; return Math.abs(Math.hypot(b[0] - a[0], b[1] - a[1]) - 10) < TOL; },
  },
  {
    name: 'parallel',
    project: project([line('L1', [0, 0], [1, 0]), line('L2', [0, 1], [1, 2])], [{ id: 'pp', type: 'parallel', refs: [...endpoints('L1'), ...endpoints('L2')] }]),
    satisfied: (v) => {
      const l1 = ent(v, 'L1').line; const l2 = ent(v, 'L2').line;
      const v1 = [l1[1][0] - l1[0][0], l1[1][1] - l1[0][1]];
      const v2 = [l2[1][0] - l2[0][0], l2[1][1] - l2[0][1]];
      const cross = v1[0] * v2[1] - v1[1] * v2[0];
      const norm = Math.hypot(...v1) * Math.hypot(...v2);
      return Math.abs(cross / (norm || 1)) < TOL;
    },
  },
  {
    name: 'perpendicular',
    project: project([line('L1', [0, 0], [1, 0]), line('L2', [0, 0], [1, 1])], [{ id: 'pe', type: 'perpendicular', refs: [...endpoints('L1'), ...endpoints('L2')] }]),
    satisfied: (v) => {
      const l1 = ent(v, 'L1').line; const l2 = ent(v, 'L2').line;
      const v1 = [l1[1][0] - l1[0][0], l1[1][1] - l1[0][1]];
      const v2 = [l2[1][0] - l2[0][0], l2[1][1] - l2[0][1]];
      const dot = v1[0] * v2[0] + v1[1] * v2[1];
      const norm = Math.hypot(...v1) * Math.hypot(...v2);
      return Math.abs(dot / (norm || 1)) < TOL;
    },
  },
  {
    name: 'angle',
    project: project([line('L1', [0, 0], [1, 0]), line('L2', [0, 0], [1, 1])], [{ id: 'an', type: 'angle', value: Math.PI / 2, refs: [...endpoints('L1'), ...endpoints('L2')] }]),
    satisfied: (v) => {
      const l1 = ent(v, 'L1').line; const l2 = ent(v, 'L2').line;
      const v1 = [l1[1][0] - l1[0][0], l1[1][1] - l1[0][1]];
      const v2 = [l2[1][0] - l2[0][0], l2[1][1] - l2[0][1]];
      const cos = (v1[0] * v2[0] + v1[1] * v2[1]) / ((Math.hypot(...v1) * Math.hypot(...v2)) || 1);
      const theta = Math.acos(Math.max(-1, Math.min(1, cos)));
      return Math.abs(theta - Math.PI / 2) < TOL;
    },
  },
  {
    name: 'conflict',
    expectFail: true, // two incompatible distances on the same pair -> unsatisfiable
    conflictEntities: ['P1', 'P2'], // the solver's conflicting variable keys must resolve to these
    project: project([point('P1', [0, 0]), point('P2', [3, 0])], [
      { id: 'd10', type: 'distance', value: 10, refs: [{ entity: 'P1', at: 'self' }, { entity: 'P2', at: 'self' }] },
      { id: 'd20', type: 'distance', value: 20, refs: [{ entity: 'P1', at: 'self' }, { entity: 'P2', at: 'self' }] },
    ]),
  },
];

const outDir = process.argv[2] || fs.mkdtempSync(path.join(os.tmpdir(), 'vemcad-solve-acc-'));
fs.mkdirSync(outDir, { recursive: true });

let failed = 0;
for (const c of cases) {
  if (c.expectFail) {
    const r = solveProject(c.project, { runner });
    const rejected = !r.ok && r.error_code === 'SOLVE_UNSATISFIED' && r.analysis;
    // Conflict-entity resolution against the REAL solver: the conflicting variable keys must
    // resolve (via the adapter pointMap) to exactly the expected editor entities. This validates
    // the variable_key format that the unit fixtures only assume.
    let entitiesOk = true;
    if (rejected && c.conflictEntities) {
      const got = [...(r.analysis.conflict_entity_ids ?? [])].sort();
      const want = [...c.conflictEntities].sort();
      entitiesOk = JSON.stringify(got) === JSON.stringify(want);
      if (!entitiesOk) console.error(`FAIL ${c.name}: conflict_entity_ids = ${JSON.stringify(got)}, expected ${JSON.stringify(want)}`);
    }
    if (rejected && entitiesOk) {
      console.log(`OK   ${c.name} (correctly rejected; state=${r.analysis.structural_state}${c.conflictEntities ? `; conflict entities=${JSON.stringify(r.analysis.conflict_entity_ids)}` : ''})`);
    } else {
      if (!rejected) console.error(`FAIL ${c.name}: expected SOLVE_UNSATISFIED + analysis, got ${JSON.stringify({ ok: r.ok, code: r.error_code, hasAnalysis: !!r.analysis })}`);
      failed += 1;
    }
    continue;
  }

  const r1 = solveProject(c.project, { runner });
  const r2 = solveProject(c.project, { runner });
  if (!r1.ok || !r2.ok) {
    console.error(`FAIL ${c.name}: ${r1.error ?? r2.error}`);
    failed += 1;
    continue;
  }
  const solved = r1.value.solve.ok;
  const sat = c.satisfied(r1.value.evaluatedView);
  const reproducible = JSON.stringify(r1.value.evaluatedGeometry) === JSON.stringify(r2.value.evaluatedGeometry);

  // Full local loop incl. the derive leg; write the derived CADGF Document so the
  // shell can validate it against document.schema.json (closes the last leg).
  const sd = solveAndDeriveScene(c.project, { runner });
  const derived = sd.ok && sd.value.cadgfDocument && sd.value.cadgfDocument.schema_version === 1;
  if (sd.ok) fs.writeFileSync(path.join(outDir, `${c.name}.cadgf.json`), `${JSON.stringify(sd.value.cadgfDocument, null, 2)}\n`);

  if (solved && sat && reproducible && derived) {
    console.log(`OK   ${c.name} (iters=${r1.value.solve.iterations}, err=${Number(r1.value.solve.finalError).toExponential(2)}, solve->derive written)`);
  } else {
    console.error(`FAIL ${c.name}: solved=${solved} satisfied=${sat} reproducible=${reproducible} derived=${derived}`);
    failed += 1;
  }
}

// --- exit-code contract via the solve_cli.mjs subprocess (input error vs solve failure) ---
const cliPath = path.join(path.dirname(fileURLToPath(import.meta.url)), 'solve_cli.mjs');
const cliExit = (input) => spawnSync(process.execPath, [cliPath, '-'], {
  input: typeof input === 'string' ? input : JSON.stringify(input),
  env: process.env,
  encoding: 'utf8',
}).status;
const badUnit = createProjectModel({ id: 'u', name: 'u', units: 'league', createdAt: FIXED, modifiedAt: FIXED }).value;
const exitCases = [
  { name: 'solve_cli exit 0 (solved)', input: project([line('L1', [0, 0], [10, 5])], [{ id: 'h', type: 'horizontal', refs: endpoints('L1') }]), expect: 0 },
  {
    name: 'solve_cli exit 1 (unsatisfied)',
    input: project([point('P1', [0, 0]), point('P2', [3, 0])], [
      { id: 'a', type: 'distance', value: 10, refs: [{ entity: 'P1', at: 'self' }, { entity: 'P2', at: 'self' }] },
      { id: 'b', type: 'distance', value: 20, refs: [{ entity: 'P1', at: 'self' }, { entity: 'P2', at: 'self' }] },
    ]),
    expect: 1,
  },
  { name: 'solve_cli exit 2 (bad unit)', input: badUnit, expect: 2 },
  { name: 'solve_cli exit 2 (invalid envelope)', input: { hello: 'world' }, expect: 2 },
  { name: 'solve_cli exit 2 (malformed json)', input: 'not json at all', expect: 2 },
];
for (const ec of exitCases) {
  const code = cliExit(ec.input);
  if (code === ec.expect) console.log(`OK   ${ec.name}`);
  else { console.error(`FAIL ${ec.name}: expected exit ${ec.expect}, got ${code}`); failed += 1; }
}

console.log(`output dir: ${outDir}`);
console.log(`solver acceptance: ${(cases.length + exitCases.length) - failed}/${cases.length + exitCases.length} ok`);
process.exit(failed ? 1 : 0);
