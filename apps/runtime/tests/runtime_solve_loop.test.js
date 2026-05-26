import test from 'node:test';
import assert from 'node:assert/strict';
import { createProjectModel } from '../project/index.js';
import { solveProject, solveAndDeriveScene, applySolvedVars, buildEvaluatedProjectView } from '../solver/index.js';

const FIXED = '2026-05-25T00:00:00.000Z';
const CLOCK = { now: () => '2026-09-09T09:09:09.000Z' };

function projectWith(overrides = {}) {
  return { ...createProjectModel({ id: 'p', name: 'P', units: 'mm', createdAt: FIXED, modifiedAt: FIXED }).value, ...overrides };
}

// Fake solver: "flatten" — set every point's y to 0, keep x. Proves the writeback
// path actually moves geometry (and is reproducible) without the real binary.
function flattenYRunner(cadgfProject) {
  const vars = {};
  for (const e of cadgfProject.scene.entities) {
    if (e.type === 'point') {
      vars[`${e.id}.x`] = e.params.x;
      vars[`${e.id}.y`] = 0;
    }
  }
  return { ok: true, iterations: 3, final_error: 0, vars, analysis: { dof_estimate: 2, structural_state: 'underconstrained', conflict_group_count: 0, redundant_constraint_estimate: 0 } };
}

test('solveProject writes solved vars to a transient view; seed (input) is untouched', () => {
  const project = projectWith({
    entities: [
      { id: 'L1', kind: 'line', layerId: 0, line: [[0, 5], [10, 7]] },
      { id: 'C1', kind: 'circle', layerId: 0, circle: { c: [3, 3], r: 2 } },
    ],
  });
  const res = solveProject(project, { runner: flattenYRunner, clock: CLOCK });
  assert.equal(res.ok, true);

  const view = res.value.evaluatedView;
  assert.deepEqual(view.entities.find((e) => e.id === 'L1').line, [[0, 0], [10, 0]]);
  const vcircle = view.entities.find((e) => e.id === 'C1');
  assert.deepEqual(vcircle.circle.c, [3, 0]);
  assert.equal(vcircle.circle.r, 2); // non-solved radius preserved

  // seed unchanged
  assert.deepEqual(project.entities.find((e) => e.id === 'L1').line, [[0, 5], [10, 7]]);
  assert.deepEqual(project.entities.find((e) => e.id === 'C1').circle.c, [3, 3]);
});

test('solveProject surfaces solver analysis as a diagnostic + solve status', () => {
  const res = solveProject(projectWith({ entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 1], [2, 3]] }] }), { runner: flattenYRunner });
  assert.equal(res.value.solve.ok, true);
  assert.equal(res.value.solve.iterations, 3);
  assert.ok(res.diagnostics.some((d) => d.code === 'SOLVE_ANALYSIS'));
});

test('solveProject converts a runner throw into SOLVE_FAILED (single contract)', () => {
  const res = solveProject(projectWith({ entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]] }] }), {
    runner: () => { throw new Error('boom'); },
  });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'SOLVE_FAILED');
});

test('solveProject propagates an adapter failure (bad unit) before invoking the runner', () => {
  let invoked = false;
  const bad = createProjectModel({ id: 'u', name: 'U', units: 'league', createdAt: FIXED, modifiedAt: FIXED }).value;
  const res = solveProject(bad, { runner: () => { invoked = true; return {}; } });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'UNSUPPORTED_PROJECT_UNIT');
  assert.equal(invoked, false);
});

test('solveAndDeriveScene runs the full local loop -> CADGF Document with evaluated geometry', () => {
  const res = solveAndDeriveScene(projectWith({ entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 5], [10, 7]] }] }), { runner: flattenYRunner, clock: CLOCK });
  assert.equal(res.ok, true);
  const doc = res.value.cadgfDocument;
  assert.equal(doc.schema_version, 1); // it is a CADGF Document (S4 output)
  const line = doc.entities.find((e) => e.type === 2);
  assert.deepEqual(line.line, [[0, 0], [10, 0]]); // flattened (evaluated) geometry, not the seed
});

test('applySolvedVars maps minted vars back through the point map (ignoring junk)', () => {
  const pointMap = { __p0: { entity: 'L1', role: 'start' }, __p1: { entity: 'L1', role: 'end' } };
  const evaluated = applySolvedVars(pointMap, { '__p0.x': 0, '__p0.y': 0, '__p1.x': 10, '__p1.y': 0, 'unknown.x': 9 });
  assert.deepEqual(evaluated, { L1: { start: { x: 0, y: 0 }, end: { x: 10, y: 0 } } });
});

test('an unsatisfied solve returns ok:false with analysis preserved, no writeback/derive', () => {
  const failRunner = (cadgfProject) => ({
    ok: false,
    iterations: 100,
    final_error: 1.5,
    message: 'did not converge',
    vars: Object.fromEntries(
      cadgfProject.scene.entities.filter((e) => e.type === 'point').flatMap((e) => [[`${e.id}.x`, 999], [`${e.id}.y`, 999]]),
    ),
    analysis: { dof_estimate: 0, structural_state: 'overconstrained', conflict_group_count: 1, redundant_constraint_estimate: 0 },
  });
  const project = projectWith({ entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]] }] });

  const res = solveProject(project, { runner: failRunner });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'SOLVE_UNSATISFIED');
  assert.equal(res.error, 'did not converge');
  assert.ok(res.analysis, 'structured analysis is preserved on failure');
  assert.equal(res.analysis.conflict_group_count, 1);
  assert.equal(res.value, undefined); // no evaluated view (no writeback)

  // solveAndDeriveScene must NOT derive an unsatisfied solve
  const sd = solveAndDeriveScene(project, { runner: failRunner });
  assert.equal(sd.ok, false);
  assert.equal(sd.error_code, 'SOLVE_UNSATISFIED');
});

test('buildEvaluatedProjectView overlays evaluated coords without mutating the input', () => {
  const project = projectWith({ entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 5], [1, 5]] }] });
  const view = buildEvaluatedProjectView(project, { L1: { start: { x: 0, y: 9 }, end: { x: 1, y: 9 } } });
  assert.equal(view.ok, true);
  assert.deepEqual(view.value.entities[0].line, [[0, 9], [1, 9]]);
  assert.deepEqual(project.entities.find((e) => e.id === 'L1').line, [[0, 5], [1, 5]]); // unchanged
});
