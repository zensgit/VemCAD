import test from 'node:test';
import assert from 'node:assert/strict';

import { mountEditorNativeSolve } from '../workbench/solver/editor_native_solve_panel.js';

function makeElement(tag, ownerDocument) {
  const listeners = {};
  const el = {
    tagName: String(tag).toUpperCase(),
    ownerDocument,
    children: [],
    className: '',
    textContent: '',
    type: '',
    disabled: false,
    appendChild(c) { el.children.push(c); return c; },
    replaceChildren() { el.children = []; },
    setAttribute() {},
    addEventListener(t, h) { (listeners[t] ??= []).push(h); },
    click() { (listeners.click ?? []).forEach((h) => h()); },
  };
  return el;
}
function makeDocument() {
  const document = { createElement(tag) { return makeElement(tag, document); } };
  return document;
}
function recorder(impl) { const calls = []; const fn = (...a) => { calls.push(a); return impl ? impl(...a) : undefined; }; fn.calls = calls; return fn; }
const jsonResp = (obj) => Promise.resolve({ json: async () => obj });
const tick = () => new Promise((r) => setImmediate(r));

function bus({ exportResult, applySpy } = {}) {
  return { execute(id, payload) {
    if (id === 'solver.export-project') return exportResult;
    if (id === 'entity.applyGeometry') { applySpy?.(payload); return { ok: true }; }
    return { ok: false };
  } };
}

function mount({ exportResult, applySpy, fetchImpl } = {}) {
  const document = makeDocument();
  const root = document.createElement('div');
  const handle = mountEditorNativeSolve({ root, document, commandBus: bus({ exportResult, applySpy }), fetchImpl });
  return { handle, root };
}

test('mountEditorNativeSolve: builds title + status + details + Solve button', () => {
  const { handle, root } = mount({ exportResult: { ok: false } });
  assert.equal(handle.button.textContent, 'Solve');
  assert.equal(handle.status.textContent, 'Ready.');
  assert.equal(root.children.map((c) => c.tagName).join(','), 'H2,P,P,BUTTON');
});

test('Solve: a successful native solve writes back and shows Solved + analysis', async () => {
  const apply = recorder();
  const project = { header: { format: 'CADGF-PROJ' }, scene: { entities: [], constraints: [{}] } };
  const fetchImpl = recorder(() => jsonResp({
    ok: true,
    value: { vars: { 'e1_start.x': 0, 'e1_start.y': 2.5, 'e1_end.x': 10, 'e1_end.y': 2.5 } },
    analysis: { structural_state: 'underconstrained', dof_estimate: 1, conflict_group_count: 0 },
  }));
  const { handle } = mount({ exportResult: { ok: true, project }, applySpy: apply, fetchImpl });

  await handle.solve();
  assert.equal(handle.status.textContent, 'Solved');
  assert.match(handle.details.textContent, /state=underconstrained · dof=1 · conflicts=0/);
  assert.equal(apply.calls.length, 1);
  assert.deepEqual(apply.calls[0][0], { updates: [{ id: 1, patch: { start: { x: 0, y: 2.5 }, end: { x: 10, y: 2.5 } } }] });
});

test('Solve: no constraints -> "No constraints to solve", no writeback', async () => {
  const apply = recorder();
  const { handle } = mount({ exportResult: { ok: false, message: 'No constraints to export' }, applySpy: apply, fetchImpl: () => jsonResp({}) });
  await handle.solve();
  assert.equal(handle.status.textContent, 'No constraints to solve');
  assert.equal(apply.calls.length, 0);
});

test('Solve: unsatisfiable -> "Blocked", no writeback', async () => {
  const apply = recorder();
  const fetchImpl = () => jsonResp({ ok: false, error_code: 'SOLVE_UNSATISFIED', error: 'conflict' });
  const { handle } = mount({ exportResult: { ok: true, project: {} }, applySpy: apply, fetchImpl });
  await handle.solve();
  assert.equal(handle.status.textContent, 'Blocked — conflicting constraints');
  assert.equal(apply.calls.length, 0);
});
