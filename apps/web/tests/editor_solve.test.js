import test from 'node:test';
import assert from 'node:assert/strict';

import { mountEditorSolvePanel, translateEvaluatedViewToUpdates, EDITOR_SOLVE_EXPORT_FAILED } from '../workbench/solver/editor_solve.js';
import { bootstrapVemcadWebApp, resetVemcadWebAppBootstrapState } from '../app.js';

// Pure, dependency-injected tests — no editor, no runtime bridge, no solver, no submodule.
const fakeRoot = () => ({ appendChild() {} });

function recorder(returnValue) {
  const calls = [];
  const fn = (...args) => { calls.push(args); return returnValue; };
  fn.calls = calls;
  return fn;
}

// A controller stub that supports subscribe (records the listener, fires once with idle
// state like the real one) + a manual emit, so we can drive solve-result states.
function fakeSolveController() {
  let listener = null;
  return {
    solve() {},
    subscribe(l) { listener = l; l({ status: 'idle', envelope: null }); return () => { listener = null; }; },
    emit(state) { if (listener) listener(state); },
  };
}

// --- editor_solve module: compose (export -> panel) + auto-apply writeback ----

test('mountEditorSolvePanel: exportable document -> mounts panel with the project + wired controller', () => {
  const project = { header: { format: 'VEMCAD-PROJECT' }, entities: [], constraints: [] };
  const exportProject = recorder({ ok: true, value: project });
  const controller = { solve() {} };
  const createController = recorder(controller);
  const panel = { destroy() {} };
  const createPanel = recorder(panel);
  const root = fakeRoot();
  const fetchImpl = () => {};

  const result = mountEditorSolvePanel({
    root,
    documentState: { listEntities() { return []; }, listLayers() { return []; } },
    exportProject,
    createPanel,
    createController,
    endpoint: '/solve',
    fetchImpl,
  });

  assert.equal(result.ok, true);
  assert.equal(result.project, project);
  assert.equal(result.controller, controller);
  assert.equal(result.panel, panel);
  // controller wired with endpoint + fetchImpl
  assert.deepEqual(createController.calls[0][0], { endpoint: '/solve', fetchImpl });
  // panel mounted with root + the exported project + the controller (NOT modifying panel/controller code)
  const panelArgs = createPanel.calls[0][0];
  assert.equal(panelArgs.root, root);
  assert.equal(panelArgs.project, project);
  assert.equal(panelArgs.controller, controller);
});

test('mountEditorSolvePanel: read-only — failed export mounts NO panel and surfaces the reason', () => {
  const exportProject = recorder({ ok: false, error_code: 'INVALID_DOCUMENT_STATE', error: 'nope', diagnostics: [] });
  const createPanel = recorder({});
  const createController = recorder({});

  const result = mountEditorSolvePanel({
    root: fakeRoot(),
    documentState: null,
    exportProject,
    createPanel,
    createController,
  });

  assert.equal(result.ok, false);
  assert.equal(result.error_code, 'INVALID_DOCUMENT_STATE');
  assert.equal(result.panel, null);
  assert.equal(createPanel.calls.length, 0, 'no panel mounted on failed export');
  assert.equal(createController.calls.length, 0);
});

test('mountEditorSolvePanel: ok-but-empty export value -> EDITOR_SOLVE_EXPORT_FAILED, no panel', () => {
  const result = mountEditorSolvePanel({
    root: fakeRoot(),
    documentState: {},
    exportProject: () => ({ ok: true, value: null }),
    createPanel: recorder({}),
    createController: recorder({}),
  });
  assert.equal(result.ok, false);
  assert.equal(result.error_code, EDITOR_SOLVE_EXPORT_FAILED);
  assert.equal(result.panel, null);
});

test('mountEditorSolvePanel: missing root or collaborators throws', () => {
  assert.throws(() => mountEditorSolvePanel({ exportProject() {}, createPanel() {}, createController() {} }), TypeError);
  assert.throws(() => mountEditorSolvePanel({ root: fakeRoot() }), TypeError);
});

// --- translateEvaluatedViewToUpdates: solved view -> editor geometry patches --
// These lock the EXACT editor field names per kind; a wrong key would make updateEntity
// merge a junk field that normalize drops -> geometry silently does not move.

test('translateEvaluatedViewToUpdates: maps each handled kind to its editor field names', () => {
  const evaluatedView = {
    entities: [
      { id: 1, kind: 'line', line: [[1, 2], [9, 8]] },
      { id: 2, kind: 'circle', circle: { c: [3, 4], r: 5 } },
      { id: 3, kind: 'arc', arc: { c: [5, 6] } },
      { id: 4, kind: 'point', point: [7, 8] }, // editor has no point type -> not written back
    ],
  };
  assert.deepEqual(translateEvaluatedViewToUpdates(evaluatedView), [
    { id: 1, patch: { start: { x: 1, y: 2 }, end: { x: 9, y: 8 } } },
    { id: 2, patch: { center: { x: 3, y: 4 } } },
    { id: 3, patch: { center: { x: 5, y: 6 } } },
  ]);
});

test('translateEvaluatedViewToUpdates: skips no-id, unknown kind, malformed coords, and non-views', () => {
  const evaluatedView = {
    entities: [
      { kind: 'line', line: [[0, 0], [1, 1]] },               // no id
      { id: 'x', kind: 'circle', circle: { c: [0, 0] } },     // non-finite id
      { id: 5, kind: 'spline', points: [[0, 0]] },            // unknown kind
      { id: 6, kind: 'line', line: [[0, 0]] },                // malformed (one endpoint)
      { id: 7, kind: 'circle', circle: { c: [Number.NaN, 0] } }, // malformed coord
      { id: 8, kind: 'line', line: [[2, 3], [4, 5]] },        // valid -> kept
    ],
  };
  assert.deepEqual(translateEvaluatedViewToUpdates(evaluatedView), [
    { id: 8, patch: { start: { x: 2, y: 3 }, end: { x: 4, y: 5 } } },
  ]);
  assert.deepEqual(translateEvaluatedViewToUpdates(null), []);
  assert.deepEqual(translateEvaluatedViewToUpdates({}), []);
});

// --- auto-apply: a successful solve writes solved geometry back via applyUpdates ---

function mountWithController(controller, applyUpdates, highlightEntities) {
  const project = { header: { format: 'VEMCAD-PROJECT' }, entities: [], constraints: [] };
  return mountEditorSolvePanel({
    root: fakeRoot(),
    documentState: { listEntities() { return []; }, listLayers() { return []; } },
    exportProject: () => ({ ok: true, value: project }),
    createPanel: () => ({ destroy() {} }),
    createController: () => controller,
    applyUpdates,
    highlightEntities,
  });
}

test('mountEditorSolvePanel: a successful solve auto-applies the translated updates once', () => {
  const controller = fakeSolveController();
  const applyUpdates = recorder();
  const result = mountWithController(controller, applyUpdates);
  assert.equal(result.ok, true);

  // idle subscribe fire (no envelope) -> nothing applied yet
  assert.equal(applyUpdates.calls.length, 0);

  const evaluatedView = { entities: [{ id: 1, kind: 'line', line: [[1, 2], [9, 8]] }] };
  controller.emit({ status: 'satisfied', envelope: { ok: true, value: { evaluatedView } } });

  assert.equal(applyUpdates.calls.length, 1);
  assert.deepEqual(applyUpdates.calls[0][0], {
    updates: [{ id: 1, patch: { start: { x: 1, y: 2 }, end: { x: 9, y: 8 } } }],
  });

  // a notify replay of the SAME view must not re-apply (object-identity guard)
  controller.emit({ status: 'satisfied', envelope: { ok: true, value: { evaluatedView } } });
  assert.equal(applyUpdates.calls.length, 1);
});

test('mountEditorSolvePanel: does NOT apply on a failed solve or an empty solved view', () => {
  const controller = fakeSolveController();
  const applyUpdates = recorder();
  mountWithController(controller, applyUpdates);

  controller.emit({ status: 'error', envelope: { ok: false, value: null } });
  controller.emit({ status: 'solving', envelope: null });
  controller.emit({ status: 'satisfied', envelope: { ok: true, value: { evaluatedView: { entities: [] } } } });

  assert.equal(applyUpdates.calls.length, 0);
});

test('mountEditorSolvePanel: read-only when applyUpdates is not injected (no throw on solve)', () => {
  const controller = fakeSolveController();
  const result = mountWithController(controller, undefined);
  assert.equal(result.ok, true);
  const evaluatedView = { entities: [{ id: 1, kind: 'line', line: [[1, 2], [9, 8]] }] };
  assert.doesNotThrow(() => controller.emit({ status: 'satisfied', envelope: { ok: true, value: { evaluatedView } } }));
});

// --- conflict highlight: a conflicting solve highlights the offending entities ---
// Independent of envelope.ok (conflicts come back as a FAILED solve), keyed off the curated
// summary.conflictEntityIds.

test('mountEditorSolvePanel: highlights conflicting entities on a failed (conflict) solve', () => {
  const controller = fakeSolveController();
  const highlight = recorder();
  mountWithController(controller, undefined, highlight);

  // conflict => envelope.ok false, summary carries the resolved ids
  controller.emit({ status: 'blocked', envelope: { ok: false, value: null }, summary: { conflictEntityIds: ['L1', 'C1'] } });

  assert.equal(highlight.calls.length, 1);
  assert.deepEqual(highlight.calls[0][0], ['L1', 'C1']);

  // a notify replay of the SAME summary must not re-highlight (object-identity guard)
  const summary = { conflictEntityIds: ['L2'] };
  controller.emit({ status: 'blocked', envelope: { ok: false }, summary });
  controller.emit({ status: 'blocked', envelope: { ok: false }, summary });
  assert.equal(highlight.calls.length, 2);
  assert.deepEqual(highlight.calls[1][0], ['L2']);
});

test('mountEditorSolvePanel: does NOT highlight when there are no conflicts (never disturbs selection)', () => {
  const controller = fakeSolveController();
  const highlight = recorder();
  mountWithController(controller, undefined, highlight);

  controller.emit({ status: 'satisfied', envelope: { ok: true, value: { evaluatedView: { entities: [] } } }, summary: { conflictEntityIds: [] } });
  controller.emit({ status: 'failed', envelope: { ok: false }, summary: { conflictEntityIds: [] } });
  controller.emit({ status: 'solving', envelope: null, summary: null });

  assert.equal(highlight.calls.length, 0);
});

test('mountEditorSolvePanel: no highlightEntities injected -> no throw on a conflict solve', () => {
  const controller = fakeSolveController();
  const result = mountWithController(controller, undefined, undefined);
  assert.equal(result.ok, true);
  assert.doesNotThrow(() => controller.emit({ status: 'blocked', envelope: { ok: false }, summary: { conflictEntityIds: ['L1'] } }));
});

// --- app.js wiring: editor mode invokes the (injectable) editor-solve mounter -

function installMinimalDom() {
  const el = () => ({
    classList: { toggle() {}, add() {}, remove() {} },
    setAttribute() {}, removeAttribute() {}, appendChild() {},
  });
  globalThis.window = { location: { search: '' } };
  globalThis.document = { getElementById: () => el(), createElement: () => el(), body: el() };
}
function cleanupDom() { delete globalThis.window; delete globalThis.document; }

test('bootstrapVemcadWebApp editor mode invokes mountEditorSolveImpl and returns its result', async () => {
  installMinimalDom();
  resetVemcadWebAppBootstrapState();
  try {
    const workspace = { importPayload() {}, state: { document: {} } };
    const solveResult = { ok: true, panel: { tag: 'solve-panel' } };
    const mountEditorSolveImpl = recorder(solveResult);

    const result = await bootstrapVemcadWebApp({
      params: new URLSearchParams('mode=editor'),
      ensureWorkspaceBootstrappedImpl: async () => workspace,
      mountEditorSolveImpl,
      scheduleOfflineCaching: () => ({ catch() {} }),
    });

    assert.equal(result.mode, 'editor');
    assert.equal(result.workspace, workspace);
    assert.equal(result.solve, solveResult);
    assert.equal(mountEditorSolveImpl.calls.length, 1);
    assert.equal(mountEditorSolveImpl.calls[0][0].workspace, workspace);
  } finally {
    resetVemcadWebAppBootstrapState();
    cleanupDom();
  }
});
