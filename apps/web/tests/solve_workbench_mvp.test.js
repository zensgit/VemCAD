import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createSolveWorkbenchController,
  deriveCadgfPreviewDocument,
  solveRuntimeProject,
  summarizeSolveEnvelope,
} from '../workbench/solver/solve_workbench.js';
import { createSolveDemoFetch } from '../workbench/solver/demo_fetch.js';
import { SOLVE_WORKBENCH_DEMOS } from '../workbench/solver/demo_projects.js';

function jsonResponse(status, body) {
  return {
    status,
    async json() {
      return body;
    },
  };
}

const SOLVED_ENVELOPE = {
  ok: true,
  value: {
    evaluatedView: SOLVE_WORKBENCH_DEMOS.solvableLine,
    evaluatedGeometry: { L1: { start: { x: 0, y: 0 }, end: { x: 10, y: 0 } } },
    solve: { ok: true, iterations: 4, finalError: 0.000001 },
  },
  diagnostics: [{
    level: 'info',
    code: 'SOLVE_ANALYSIS',
    message: 'dof=1 state=underconstrained conflicts=0 redundant=0',
    analysis: {
      dof_estimate: 1,
      structural_state: 'underconstrained',
      conflict_group_count: 0,
      redundant_constraint_estimate: 0,
    },
  }],
};

test('solveRuntimeProject POSTs a VEMCAD-PROJECT to /solve and attaches a product summary', async () => {
  const calls = [];
  const result = await solveRuntimeProject(SOLVE_WORKBENCH_DEMOS.solvableLine, {
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return jsonResponse(200, SOLVED_ENVELOPE);
    },
  });

  assert.equal(result.ok, true);
  assert.equal(result.httpStatus, 200);
  assert.equal(result.summary.status, 'solved');
  assert.equal(result.summary.iterations, 4);
  assert.equal(result.summary.dofEstimate, 1);
  assert.equal(calls[0].url, '/solve');
  assert.equal(calls[0].init.method, 'POST');
  assert.equal(calls[0].init.headers['content-type'], 'application/json');
  assert.deepEqual(JSON.parse(calls[0].init.body).project.id, 'demo-solvable-line');
});

test('solveRuntimeProject keeps a single result contract when request serialization fails', async () => {
  const circular = {};
  circular.self = circular;
  const result = await solveRuntimeProject(circular, {
    fetchImpl: async () => {
      throw new Error('fetch should not run');
    },
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, 'SOLVE_REQUEST_SERIALIZE_FAILED');
});

test('summarizeSolveEnvelope treats unsatisfied solves as blocked user-fixable state', () => {
  const summary = summarizeSolveEnvelope({
    ok: false,
    error_code: 'SOLVE_UNSATISFIED',
    error: 'did not converge',
    solve: { ok: false, iterations: 100, finalError: 1.2 },
    analysis: {
      dof_estimate: 0,
      structural_state: 'overconstrained',
      conflict_group_count: 1,
      redundant_constraint_estimate: 0,
      conflict_entity_ids: ['L1', 'C1'],
    },
    diagnostics: [],
  }, { httpStatus: 422 });

  assert.equal(summary.status, 'blocked');
  assert.equal(summary.httpStatus, 422);
  assert.equal(summary.errorCode, 'SOLVE_UNSATISFIED');
  assert.equal(summary.conflictGroupCount, 1);
  assert.equal(summary.structuralState, 'overconstrained');
  assert.deepEqual(summary.conflictEntityIds, ['L1', 'C1']); // surfaced from analysis for the editor to highlight
});

test('summarizeSolveEnvelope defaults conflictEntityIds to [] when analysis omits them', () => {
  const summary = summarizeSolveEnvelope({ ok: true, value: { solve: { ok: true } }, diagnostics: [] });
  assert.deepEqual(summary.conflictEntityIds, []);
});

test('deriveCadgfPreviewDocument derives from the evaluated view, not from failed envelopes', () => {
  const derived = deriveCadgfPreviewDocument(SOLVED_ENVELOPE, {
    deriveCadgfDocumentImpl(project) {
      assert.equal(project.project.id, 'demo-solvable-line');
      return { ok: true, value: { schema_version: 1, entities: [] }, diagnostics: [{ code: 'DERIVED' }] };
    },
  });
  assert.equal(derived.ok, true);
  assert.equal(derived.value.schema_version, 1);
  assert.equal(derived.diagnostics.some((d) => d.code === 'SOLVE_ANALYSIS'), true);
  assert.equal(derived.diagnostics.some((d) => d.code === 'DERIVED'), true);

  const failed = deriveCadgfPreviewDocument({ ok: false, error_code: 'SOLVE_UNSATISFIED', diagnostics: [] });
  assert.equal(failed.ok, false);
  assert.equal(failed.error_code, 'SOLVE_RESULT_REQUIRED');
});

test('createSolveWorkbenchController exposes idle -> solving -> solved state and preview document', async () => {
  const states = [];
  const controller = createSolveWorkbenchController({
    fetchImpl: async () => jsonResponse(200, SOLVED_ENVELOPE),
    deriveCadgfDocumentImpl: () => ({ ok: true, value: { schema_version: 1, document_id: 'preview' }, diagnostics: [] }),
  });
  controller.subscribe((state) => states.push(state.status));

  const finalState = await controller.solve(SOLVE_WORKBENCH_DEMOS.solvableLine);
  assert.deepEqual(states, ['idle', 'solving', 'solved']);
  assert.equal(finalState.previewDocument.document_id, 'preview');
  assert.equal(finalState.summary.status, 'solved');
});

test('controller keeps failed solve envelopes visible and does not derive a preview', async () => {
  const controller = createSolveWorkbenchController({
    fetchImpl: async () => jsonResponse(422, {
      ok: false,
      error_code: 'SOLVE_UNSATISFIED',
      error: 'conflict',
      analysis: { dof_estimate: 0, structural_state: 'overconstrained', conflict_group_count: 1, redundant_constraint_estimate: 0 },
      diagnostics: [],
    }),
    deriveCadgfDocumentImpl: () => {
      throw new Error('should not derive a failed solve');
    },
  });

  const finalState = await controller.solve(SOLVE_WORKBENCH_DEMOS.conflictingLine);
  assert.equal(finalState.status, 'blocked');
  assert.equal(finalState.previewDocument, null);
  assert.equal(finalState.envelope.error_code, 'SOLVE_UNSATISFIED');
});

test('demo fixtures cover solved, conflict, and unsupported-passthrough workbench examples', () => {
  assert.deepEqual(Object.keys(SOLVE_WORKBENCH_DEMOS).sort(), ['conflictingLine', 'passthroughUnsupported', 'solvableLine']);
  assert.equal(SOLVE_WORKBENCH_DEMOS.solvableLine.constraints.some((c) => c.type === 'distance'), true);
  assert.equal(SOLVE_WORKBENCH_DEMOS.conflictingLine.constraints.some((c) => c.type === 'vertical'), true);
  assert.deepEqual(SOLVE_WORKBENCH_DEMOS.passthroughUnsupported.entities.map((e) => e.kind).sort(), ['polyline', 'text']);
});

test('createSolveDemoFetch drives the controller to a solved preview without a live /solve service', async () => {
  const controller = createSolveWorkbenchController({
    fetchImpl: createSolveDemoFetch(),
  });

  const state = await controller.solve(SOLVE_WORKBENCH_DEMOS.solvableLine);

  assert.equal(state.status, 'solved');
  assert.equal(state.summary.httpStatus, 200);
  assert.equal(state.summary.iterations, 4);
  assert.equal(state.previewDocument.document_id, 'demo-solvable-line');
  const line = state.envelope.value.evaluatedView.entities.find((entity) => entity.id === 'L1');
  assert.deepEqual(line.line, [[0, 3], [10, 3]]);
});

test('createSolveDemoFetch exposes the blocked conflict path as a user-fixable solve result', async () => {
  const controller = createSolveWorkbenchController({
    fetchImpl: createSolveDemoFetch(),
  });

  const state = await controller.solve(SOLVE_WORKBENCH_DEMOS.conflictingLine);

  assert.equal(state.status, 'blocked');
  assert.equal(state.summary.httpStatus, 422);
  assert.equal(state.summary.conflictGroupCount, 1);
  assert.equal(state.previewDocument, null);
  assert.equal(state.envelope.error_code, 'SOLVE_UNSATISFIED');
});

test('createSolveDemoFetch fails unknown projects explicitly', async () => {
  const result = await solveRuntimeProject({
    ...SOLVE_WORKBENCH_DEMOS.solvableLine,
    project: { ...SOLVE_WORKBENCH_DEMOS.solvableLine.project, id: 'unknown-demo' },
  }, {
    fetchImpl: createSolveDemoFetch(),
  });

  assert.equal(result.ok, false);
  assert.equal(result.httpStatus, 400);
  assert.equal(result.error_code, 'SOLVE_DEMO_PROJECT_NOT_FOUND');
  assert.equal(result.summary.status, 'failed');
});
