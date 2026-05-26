import test from 'node:test';
import assert from 'node:assert/strict';
import { createProjectModel } from '../project/index.js';
import { rebuildProject } from '../feature/index.js';

// rebuildProject is the host-facing rebuild seam. For a v1 constraint sketch the
// rebuild IS the constraint solve, so it must carry solveProject's FULL contract —
// success + writeback, unsatisfied propagation, and input-error short-circuit —
// not just the happy path. These mirror runtime_solve_loop's runner fakes.

const FIXED = '2026-05-25T00:00:00.000Z';

function projectWith(overrides = {}) {
  return { ...createProjectModel({ id: 'p', name: 'P', units: 'mm', createdAt: FIXED, modifiedAt: FIXED }).value, ...overrides };
}

// "flatten": set every point's y to 0 — proves the rebuild moves geometry through
// the solver writeback without needing the real binary.
function flattenYRunner(cadgfProject) {
  const vars = {};
  for (const e of cadgfProject.scene.entities) {
    if (e.type === 'point') { vars[`${e.id}.x`] = e.params.x; vars[`${e.id}.y`] = 0; }
  }
  return { ok: true, iterations: 2, final_error: 0, vars, analysis: { dof_estimate: 2, structural_state: 'underconstrained', conflict_group_count: 0, redundant_constraint_estimate: 0 } };
}

test('rebuildProject runs the solve: derived geometry lands in the transient view, seed untouched', () => {
  const project = projectWith({ entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 5], [10, 7]] }] });
  const res = rebuildProject(project, { runner: flattenYRunner });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value.evaluatedView.entities.find((e) => e.id === 'L1').line, [[0, 0], [10, 0]]);
  // the Project truth (seed) is never written back by a rebuild
  assert.deepEqual(project.entities.find((e) => e.id === 'L1').line, [[0, 5], [10, 7]]);
});

test('rebuildProject propagates an unsatisfied solve (ok:false + analysis, no writeback)', () => {
  const failRunner = (cadgfProject) => ({
    ok: false, iterations: 100, final_error: 2, message: 'did not converge',
    vars: Object.fromEntries(cadgfProject.scene.entities.filter((e) => e.type === 'point').flatMap((e) => [[`${e.id}.x`, 9], [`${e.id}.y`, 9]])),
    analysis: { dof_estimate: 0, structural_state: 'overconstrained', conflict_group_count: 1, redundant_constraint_estimate: 0 },
  });
  const res = rebuildProject(projectWith({ entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[0, 0], [1, 1]] }] }), { runner: failRunner });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'SOLVE_UNSATISFIED');
  assert.ok(res.analysis && res.analysis.conflict_group_count === 1);
  assert.equal(res.value, undefined);
});

test('rebuildProject short-circuits on an adapter (input) failure before invoking the runner', () => {
  let invoked = false;
  const bad = createProjectModel({ id: 'u', name: 'U', units: 'league', createdAt: FIXED, modifiedAt: FIXED }).value;
  const res = rebuildProject(bad, { runner: () => { invoked = true; return {}; } });
  assert.equal(res.ok, false);
  assert.equal(res.error_code, 'UNSUPPORTED_PROJECT_UNIT');
  assert.equal(invoked, false);
});
