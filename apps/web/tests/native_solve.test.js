import test from 'node:test';
import assert from 'node:assert/strict';

import { parseSolvedVarsToUpdates, solveEditorNative, NATIVE_SOLVE_ENDPOINT } from '../workbench/solver/native_solve.js';

test('parseSolvedVarsToUpdates: maps e<id>_<role>.x|y vars to editor entity patches', () => {
  const updates = parseSolvedVarsToUpdates({
    'e1_start.x': 0, 'e1_start.y': 2.5, 'e1_end.x': 10, 'e1_end.y': 2.5, // line 1
    'e2_center.x': 3, 'e2_center.y': 4, // circle 2
    'e3_start.x': 1, // incomplete (no y) -> skipped
    'junk.x': 9, 'e4_self.x': 1, // non-point / unknown role -> skipped
  }).sort((a, b) => a.id - b.id);
  assert.deepEqual(updates, [
    { id: 1, patch: { start: { x: 0, y: 2.5 }, end: { x: 10, y: 2.5 } } },
    { id: 2, patch: { center: { x: 3, y: 4 } } },
  ]);
});

test('parseSolvedVarsToUpdates: tolerant of empty / non-finite', () => {
  assert.deepEqual(parseSolvedVarsToUpdates(null), []);
  assert.deepEqual(parseSolvedVarsToUpdates({}), []);
  assert.deepEqual(parseSolvedVarsToUpdates({ 'e1_start.x': Number.NaN, 'e1_start.y': 1 }), []);
});

function recorder(impl) {
  const calls = [];
  const fn = (...a) => { calls.push(a); return impl ? impl(...a) : undefined; };
  fn.calls = calls;
  return fn;
}
const jsonResp = (obj) => Promise.resolve({ json: async () => obj });

function makeBus({ exportResult, applySpy } = {}) {
  return {
    execute(id, payload) {
      if (id === 'solver.export-project') return exportResult;
      if (id === 'entity.applyGeometry') { applySpy?.(payload); return { ok: true }; }
      return { ok: false };
    },
  };
}

test('solveEditorNative: export-project -> POST /solve-cadgf -> writeback on a successful solve', async () => {
  const apply = recorder();
  const project = { header: { format: 'CADGF-PROJ' }, scene: { entities: [], constraints: [{}] } };
  const fetchImpl = recorder(() => jsonResp({ ok: true, value: { vars: { 'e1_start.x': 0, 'e1_start.y': 2.5, 'e1_end.x': 10, 'e1_end.y': 2.5 } } }));
  const res = await solveEditorNative({ commandBus: makeBus({ exportResult: { ok: true, project }, applySpy: apply }), fetchImpl });

  assert.equal(res.ok, true);
  assert.equal(res.status, 'solved');
  assert.equal(fetchImpl.calls[0][0], NATIVE_SOLVE_ENDPOINT);
  assert.equal(JSON.parse(fetchImpl.calls[0][1].body).header.format, 'CADGF-PROJ');
  assert.equal(apply.calls.length, 1);
  assert.deepEqual(apply.calls[0][0], { updates: [{ id: 1, patch: { start: { x: 0, y: 2.5 }, end: { x: 10, y: 2.5 } } }] });
});

test('solveEditorNative: no constraints -> no-constraints status, never POSTs', async () => {
  const fetchImpl = recorder(() => jsonResp({}));
  const res = await solveEditorNative({ commandBus: makeBus({ exportResult: { ok: false, message: 'No constraints to export' } }), fetchImpl });
  assert.equal(res.status, 'no-constraints');
  assert.equal(fetchImpl.calls.length, 0);
});

test('solveEditorNative: unsatisfied solve -> blocked, NO writeback', async () => {
  const apply = recorder();
  const fetchImpl = recorder(() => jsonResp({ ok: false, error_code: 'SOLVE_UNSATISFIED', error: 'conflict', value: { vars: { 'e1_start.x': 0 } } }));
  const res = await solveEditorNative({ commandBus: makeBus({ exportResult: { ok: true, project: {} }, applySpy: apply }), fetchImpl });
  assert.equal(res.ok, false);
  assert.equal(res.status, 'blocked');
  assert.equal(apply.calls.length, 0);
});

test('solveEditorNative: fetch/network failure -> failed, no throw', async () => {
  const apply = recorder();
  const fetchImpl = () => { throw new Error('network down'); };
  const res = await solveEditorNative({ commandBus: makeBus({ exportResult: { ok: true, project: {} }, applySpy: apply }), fetchImpl });
  assert.equal(res.ok, false);
  assert.equal(res.status, 'failed');
  assert.equal(apply.calls.length, 0);
});
