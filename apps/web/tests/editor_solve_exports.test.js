import test from 'node:test';
import assert from 'node:assert/strict';

import { mountEditorSolveExports } from '../workbench/solver/editor_solve_exports.js';

// Minimal DOM double — enough for the export row, no real DOM.
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
    appendChild(child) { el.children.push(child); return child; },
    setAttribute() {},
    addEventListener(type, handler) { (listeners[type] ??= []).push(handler); },
    click() { (listeners.click ?? []).forEach((h) => h()); },
    remove() { el._removed = true; },
  };
  return el;
}
function makeDocument() {
  const document = { createElement(tag) { return makeElement(tag, document); } };
  return document;
}
function recorder(impl) {
  const calls = [];
  const fn = (...args) => { calls.push(args); return impl ? impl(...args) : Promise.resolve(); };
  fn.calls = calls;
  return fn;
}
const tick = () => new Promise((resolve) => setImmediate(resolve));

const PROJECT = { project: { id: 'editor-doc-7' }, entities: [], constraints: [] };
const SOLVED = {
  envelope: { ok: false, error_code: 'SOLVE_UNSATISFIED', analysis: { conflict_entity_ids: [1] } },
  summary: { status: 'blocked', structuralState: 'overconstrained', conflictGroupCount: 1 },
  previewDocument: { schema_version: 1, document_id: 'prev-7', entities: [] },
};

function mount({ project = PROJECT, state = {}, shareUrl = null, copyText, downloadJson } = {}) {
  const document = makeDocument();
  const root = document.createElement('div');
  const handle = mountEditorSolveExports({
    root,
    document,
    getProject: () => project,
    getSolveState: () => state,
    getShareUrl: () => shareUrl,
    copyText: copyText ?? recorder(),
    downloadJson: downloadJson ?? recorder(),
  });
  return { document, root, handle };
}

test('mountEditorSolveExports: builds the row; repro/preview disabled until a solve, project always enabled', () => {
  const { handle } = mount({ state: {} });
  assert.equal(handle.projectButton.disabled, false);
  assert.equal(handle.reproButton.disabled, true);
  assert.equal(handle.previewButton.disabled, true);
});

test('mountEditorSolveExports: update() enables repro (envelope) and preview (preview document) after a solve', () => {
  let state = {};
  const document = makeDocument();
  const root = document.createElement('div');
  const handle = mountEditorSolveExports({ root, document, getProject: () => PROJECT, getSolveState: () => state, copyText: recorder(), downloadJson: recorder() });
  assert.equal(handle.reproButton.disabled, true);
  state = SOLVED;
  handle.update();
  assert.equal(handle.reproButton.disabled, false);
  assert.equal(handle.previewButton.disabled, false);
});

test('Export Project JSON: downloads the project object under its project-id filename', async () => {
  const downloadJson = recorder();
  const { handle } = mount({ downloadJson });
  handle.projectButton.click();
  await tick();
  assert.equal(downloadJson.calls.length, 1);
  assert.equal(downloadJson.calls[0][0].value, PROJECT);
  assert.equal(downloadJson.calls[0][0].filename, 'editor-doc-7.vemcad-project.json');
  assert.equal(handle.status.textContent, 'Project JSON downloaded.');
});

test('Copy Repro Bundle: copies a bundle pairing the project with the solve result (source=editor)', async () => {
  const copyText = recorder();
  const { handle } = mount({ state: SOLVED, shareUrl: 'http://x/?mode=editor', copyText });
  handle.reproButton.click();
  await tick();
  assert.equal(copyText.calls.length, 1);
  const bundle = JSON.parse(copyText.calls[0][0].text);
  assert.equal(bundle.demo, 'editor');
  assert.equal(bundle.share_url, 'http://x/?mode=editor');
  assert.deepEqual(bundle.project, PROJECT);
  assert.equal(bundle.solve_result.error_code, 'SOLVE_UNSATISFIED');
  assert.match(bundle.solve_evidence, /state=overconstrained/);
  assert.equal(handle.status.textContent, 'Repro bundle copied.');
});

test('Copy Repro Bundle: guarded no-op before any solve', async () => {
  const copyText = recorder();
  const { handle } = mount({ state: {}, copyText });
  handle.reproButton.click();
  await tick();
  assert.equal(copyText.calls.length, 0);
  assert.equal(handle.status.textContent, 'Run solve to copy a repro bundle.');
});

test('Export CADGF Preview: downloads the solved preview document; guarded before a solve', async () => {
  const downloadJson = recorder();
  const { handle } = mount({ state: SOLVED, downloadJson });
  handle.previewButton.click();
  await tick();
  assert.equal(downloadJson.calls[0][0].value, SOLVED.previewDocument);
  assert.equal(downloadJson.calls[0][0].filename, 'prev-7.cadgf-document.json');
  assert.equal(handle.status.textContent, 'CADGF preview downloaded.');

  const dl2 = recorder();
  const { handle: h2 } = mount({ state: {}, downloadJson: dl2 });
  h2.previewButton.click();
  await tick();
  assert.equal(dl2.calls.length, 0);
  assert.equal(h2.status.textContent, 'Run solve to export a preview.');
});

test('export actions surface an unavailable status when the IO throws', async () => {
  const copyText = recorder(() => Promise.reject(new Error('denied')));
  const { handle } = mount({ state: SOLVED, copyText });
  handle.reproButton.click();
  await tick();
  assert.equal(handle.status.textContent, 'Copy repro bundle unavailable.');
});
