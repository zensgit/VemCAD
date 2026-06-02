import test from 'node:test';
import assert from 'node:assert/strict';

import { mountEditorSolvePanel, EDITOR_SOLVE_EXPORT_FAILED } from '../workbench/solver/editor_solve.js';
import { bootstrapVemcadWebApp, resetVemcadWebAppBootstrapState } from '../app.js';

// Pure, dependency-injected tests — no editor, no runtime bridge, no solver, no submodule.
const fakeRoot = () => ({ appendChild() {} });

function recorder(returnValue) {
  const calls = [];
  const fn = (...args) => { calls.push(args); return returnValue; };
  fn.calls = calls;
  return fn;
}

// --- editor_solve module: read-only compose (export -> panel) ----------------

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
