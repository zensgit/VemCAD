import test from 'node:test';
import assert from 'node:assert/strict';
import { mountSolveWorkbenchDemo } from '../workbench/solver/demo_page.js';

function makeElement(tag, ownerDocument) {
  const children = [];
  const listeners = new Map();
  const classes = new Set();
  const attrs = new Map();
  const el = {
    tagName: tag.toUpperCase(),
    ownerDocument,
    children,
    firstChild: null,
    parentNode: null,
    className: '',
    textContent: '',
    type: '',
    disabled: false,
    dataset: {},
    classList: {
      add(name) { classes.add(name); },
      contains(name) { return classes.has(name); },
    },
    appendChild(child) {
      child.parentNode = el;
      children.push(child);
      el.firstChild = children[0] ?? null;
      return child;
    },
    removeChild(child) {
      const index = children.indexOf(child);
      if (index >= 0) children.splice(index, 1);
      el.firstChild = children[0] ?? null;
      child.parentNode = null;
      return child;
    },
    addEventListener(type, handler) {
      listeners.set(type, handler);
    },
    click() {
      return listeners.get('click')?.({ type: 'click', target: el });
    },
    setAttribute(name, value) {
      attrs.set(name, String(value));
    },
    removeAttribute(name) {
      attrs.delete(name);
    },
    getAttribute(name) {
      return attrs.get(name) ?? null;
    },
  };
  return el;
}

function makeDocument() {
  const document = {
    defaultView: {
      location: {
        href: 'http://127.0.0.1/apps/web/index.html?mode=solve-demo',
      },
    },
    createElement(tag) {
      return makeElement(tag, document);
    },
    createElementNS(_ns, tag) {
      return makeElement(tag, document);
    },
  };
  return document;
}

function findByTag(root, tag) {
  const stack = [...root.children];
  while (stack.length) {
    const node = stack.shift();
    if (node.tagName === tag.toUpperCase()) return node;
    stack.push(...node.children);
  }
  return null;
}

function findAllByTag(root, tag) {
  const found = [];
  const stack = [...root.children];
  while (stack.length) {
    const node = stack.shift();
    if (node.tagName === tag.toUpperCase()) found.push(node);
    stack.push(...node.children);
  }
  return found;
}

function findByClass(root, className) {
  const stack = [...root.children];
  while (stack.length) {
    const node = stack.shift();
    if (node.className === className) return node;
    stack.push(...node.children);
  }
  return null;
}

function importedLineProject() {
  return {
    header: { format: 'VEMCAD-PROJECT', version: 1 },
    project: {
      id: 'imported-line',
      name: 'Imported line',
      units: 'mm',
      createdAt: '2026-05-25T00:00:00.000Z',
      modifiedAt: '2026-05-25T00:00:00.000Z',
    },
    layers: [{ id: 0, name: 'Default' }],
    entities: [{ id: 'L1', kind: 'line', layerId: 0, line: [[1, 2], [9, 4]] }],
    constraints: [
      { id: 'c-horizontal', type: 'horizontal', refs: [{ entity: 'L1', at: 'start' }, { entity: 'L1', at: 'end' }] },
      { id: 'c-distance', type: 'distance', refs: [{ entity: 'L1', at: 'start' }, { entity: 'L1', at: 'end' }], value: 8 },
    ],
    features: [],
    resources: { cadgfPassthrough: { document: {}, entities: [] } },
    meta: {},
  };
}

test('mountSolveWorkbenchDemo mounts selectable demos and solves without a live /solve service', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({ root });

  assert.equal(root.classList.contains('vemcad-solve-demo'), true);
  assert.equal(demo.selectedKey, 'solvableLine');
  assert.equal(demo.buttons.solvableLine.disabled, true);
  assert.equal(demo.buttons.conflictingLine.disabled, false);
  assert.match(findByClass(root, 'vemcad-solve-demo__summary').textContent, /id=demo-solvable-line/);
  assert.equal(
    findByClass(root, 'vemcad-solve-demo__share').getAttribute('href'),
    'http://127.0.0.1/apps/web/index.html?mode=solve-demo&demo=solvableLine',
  );
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-summary').textContent, 'No solve has run yet.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__diagnostic-count').textContent, 'diagnostics=0');
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-evidence').textContent, 'No solve result yet.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__export-status').textContent, 'Ready to export project.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__import-status').textContent, 'Ready to import project.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-copy').disabled, true);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-copy-status').textContent, 'Run solve to copy evidence.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-export').disabled, true);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-export-status').textContent, 'Run solve to export result.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__preview-export').disabled, true);
  assert.equal(
    findByClass(root, 'vemcad-solve-demo__preview-export-status').textContent,
    'Run solve to export CADGF preview.',
  );

  await demo.solve();
  assert.equal(demo.getPanelState().status, 'solved');
  assert.equal(demo.getPanelState().previewDocument.document_id, 'demo-solvable-line');
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-export').disabled, false);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-export-status').textContent, 'Ready to export solve result.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__preview-export').disabled, false);
  assert.equal(
    findByClass(root, 'vemcad-solve-demo__preview-export-status').textContent,
    'Ready to export CADGF preview.',
  );
  assert.equal(findByTag(root, 'svg').getAttribute('aria-label'), 'Solved geometry preview');
  assert.match(findByClass(root, 'vemcad-solve-demo__solve-summary').textContent, /state=underconstrained/);
  assert.equal(findByClass(root, 'vemcad-solve-demo__diagnostic-count').textContent, 'diagnostics=1');
  assert.match(findByClass(root, 'vemcad-solve-demo__solve-evidence').textContent, /ok=true\nhttp=200\nstatus=solved/);
  assert.match(findByClass(root, 'vemcad-solve-demo__solve-evidence').textContent, /state=underconstrained/);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-copy').disabled, false);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-copy-status').textContent, 'Ready to copy solve evidence.');

  await demo.select('conflictingLine');
  await demo.solve();
  assert.equal(demo.selectedKey, 'conflictingLine');
  assert.equal(demo.getPanelState().status, 'blocked');
  assert.equal(demo.getPanelState().previewDocument, null);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-export').disabled, false);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-export-status').textContent, 'Ready to export solve result.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__preview-export').disabled, true);
  assert.equal(findByClass(root, 'vemcad-solve-demo__preview-export-status').textContent, 'No CADGF preview to export.');
  assert.equal(
    findByClass(root, 'vemcad-solve-demo__share').getAttribute('href'),
    'http://127.0.0.1/apps/web/index.html?mode=solve-demo&demo=conflictingLine',
  );
  assert.match(findByClass(root, 'vemcad-solve-demo__solve-summary').textContent, /state=overconstrained/);
  assert.match(findByClass(root, 'vemcad-solve-demo__solve-evidence').textContent, /ok=false\nhttp=422\nstatus=blocked\nerror=SOLVE_UNSATISFIED/);
  assert.match(findByClass(root, 'vemcad-solve-demo__solve-evidence').textContent, /state=overconstrained\ndof=0\nconflicts=1/);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-copy').disabled, false);
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-copy-status').textContent, 'Ready to copy solve evidence.');
  assert.match(findByClass(root, 'vemcad-preview-canvas__empty').textContent, /No solved geometry/);
});

test('mountSolveWorkbenchDemo uses the supplied app bridge to mount the panel', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);
  const calls = [];

  await mountSolveWorkbenchDemo({
    root,
    appBridge: {
      async mountSolvePanel(panelRoot, options) {
        calls.push({ panelRoot, options });
        return {
          destroy() {},
          getState() { return { status: 'idle' }; },
          async solve() { return { status: 'solved' }; },
        };
      },
    },
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.project.project.id, 'demo-solvable-line');
  assert.equal(calls[0].options.labels.title, 'Solvable line');
});

test('mountSolveWorkbenchDemo can auto-run the default solve', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({ root, autoSolve: true });

  assert.equal(demo.selectedKey, 'solvableLine');
  assert.equal(demo.getPanelState().status, 'solved');
  assert.equal(demo.getPanelState().previewDocument.document_id, 'demo-solvable-line');
  assert.equal(findByTag(root, 'svg').getAttribute('aria-label'), 'Solved geometry preview');
});

test('copy link button uses the current demo URL and reports status', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);
  const copied = [];

  const demo = await mountSolveWorkbenchDemo({
    root,
    copyText: async (text) => {
      copied.push(text);
    },
  });
  const copyButton = findByClass(root, 'vemcad-solve-demo__copy');
  const copyStatus = findByClass(root, 'vemcad-solve-demo__copy-status');

  await copyButton.click();
  assert.deepEqual(copied, ['http://127.0.0.1/apps/web/index.html?mode=solve-demo&demo=solvableLine']);
  assert.equal(copyStatus.textContent, 'Link copied.');

  await demo.select('conflictingLine');
  assert.equal(copyStatus.textContent, 'Ready to copy link.');
  await copyButton.click();
  assert.equal(copied.at(-1), 'http://127.0.0.1/apps/web/index.html?mode=solve-demo&demo=conflictingLine');
  assert.equal(copyStatus.textContent, 'Link copied.');
});

test('copy link button reports unavailable when clipboard write fails', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  await mountSolveWorkbenchDemo({
    root,
    copyText: async () => {
      throw new Error('clipboard denied');
    },
  });

  await findByClass(root, 'vemcad-solve-demo__copy').click();
  assert.equal(findByClass(root, 'vemcad-solve-demo__copy-status').textContent, 'Copy unavailable.');
});

test('copy solve evidence button copies solved and blocked evidence text', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);
  const copied = [];

  const demo = await mountSolveWorkbenchDemo({
    root,
    copyText: async (text) => {
      copied.push(text);
    },
  });
  const evidenceCopyButton = findByClass(root, 'vemcad-solve-demo__solve-copy');
  const evidenceCopyStatus = findByClass(root, 'vemcad-solve-demo__solve-copy-status');

  evidenceCopyButton.click();
  assert.equal(evidenceCopyStatus.textContent, 'No solve evidence to copy.');

  await demo.solve();
  await evidenceCopyButton.click();

  await demo.select('conflictingLine');
  await demo.solve();
  await evidenceCopyButton.click();

  assert.match(copied[0], /ok=true\nhttp=200\nstatus=solved/);
  assert.match(copied[1], /ok=false\nhttp=422\nstatus=blocked\nerror=SOLVE_UNSATISFIED/);
  assert.equal(evidenceCopyStatus.textContent, 'Solve evidence copied.');
});

test('copy solve evidence button reports unavailable when clipboard write fails', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    copyText: async () => {
      throw new Error('clipboard denied');
    },
  });

  await demo.solve();
  await findByClass(root, 'vemcad-solve-demo__solve-copy').click();
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-copy-status').textContent, 'Copy evidence unavailable.');
});

test('export project button exports the current demo project and reports status', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);
  const exported = [];

  const demo = await mountSolveWorkbenchDemo({
    root,
    exportProjectJson: async (project, key) => {
      exported.push({
        key,
        id: project.project.id,
        format: project.header.format,
        constraints: project.constraints.length,
      });
    },
  });
  const exportButton = findByClass(root, 'vemcad-solve-demo__export');
  const exportStatus = findByClass(root, 'vemcad-solve-demo__export-status');

  await exportButton.click();
  assert.deepEqual(exported[0], {
    key: 'solvableLine',
    id: 'demo-solvable-line',
    format: 'VEMCAD-PROJECT',
    constraints: 2,
  });
  assert.equal(exportStatus.textContent, 'Project JSON exported.');

  await demo.select('conflictingLine');
  assert.equal(exportStatus.textContent, 'Ready to export project.');
  await exportButton.click();
  assert.deepEqual(exported.at(-1), {
    key: 'conflictingLine',
    id: 'demo-conflicting-line',
    format: 'VEMCAD-PROJECT',
    constraints: 3,
  });
  assert.equal(exportStatus.textContent, 'Project JSON exported.');
});

test('export project button reports unavailable when export fails', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  await mountSolveWorkbenchDemo({
    root,
    exportProjectJson: async () => {
      throw new Error('download denied');
    },
  });

  await findByClass(root, 'vemcad-solve-demo__export').click();
  assert.equal(findByClass(root, 'vemcad-solve-demo__export-status').textContent, 'Export unavailable.');
});

test('export solve result button exports blocked and solved solver envelopes', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);
  const exported = [];

  const demo = await mountSolveWorkbenchDemo({
    root,
    exportSolveResultJson: async (envelope, project, key) => {
      exported.push({
        key,
        projectId: project.project.id,
        ok: envelope.ok,
        errorCode: envelope.error_code ?? null,
        state: envelope.summary?.structuralState ?? null,
      });
    },
  });
  const solveExportButton = findByClass(root, 'vemcad-solve-demo__solve-export');
  const solveExportStatus = findByClass(root, 'vemcad-solve-demo__solve-export-status');

  solveExportButton.click();
  assert.equal(solveExportStatus.textContent, 'No solve result to export.');

  await demo.solve();
  await solveExportButton.click();

  await demo.select('conflictingLine');
  await demo.solve();
  await solveExportButton.click();

  assert.deepEqual(exported, [
    {
      key: 'solvableLine',
      projectId: 'demo-solvable-line',
      ok: true,
      errorCode: null,
      state: 'underconstrained',
    },
    {
      key: 'conflictingLine',
      projectId: 'demo-conflicting-line',
      ok: false,
      errorCode: 'SOLVE_UNSATISFIED',
      state: 'overconstrained',
    },
  ]);
  assert.equal(solveExportStatus.textContent, 'Solve result JSON exported.');
});

test('export solve result button reports unavailable when result export fails', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    exportSolveResultJson: async () => {
      throw new Error('download denied');
    },
  });

  await demo.solve();
  await findByClass(root, 'vemcad-solve-demo__solve-export').click();
  assert.equal(findByClass(root, 'vemcad-solve-demo__solve-export-status').textContent, 'Solve result export unavailable.');
});

test('export preview button exports the solved CADGF preview document', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);
  const exported = [];

  const demo = await mountSolveWorkbenchDemo({
    root,
    exportPreviewJson: async (previewDocument, key) => {
      exported.push({
        key,
        documentId: previewDocument.document_id,
        schemaVersion: previewDocument.schema_version,
        entities: previewDocument.entities.length,
      });
    },
  });
  const previewExportButton = findByClass(root, 'vemcad-solve-demo__preview-export');
  const previewExportStatus = findByClass(root, 'vemcad-solve-demo__preview-export-status');

  previewExportButton.click();
  assert.equal(previewExportStatus.textContent, 'No CADGF preview to export.');

  await demo.solve();
  await previewExportButton.click();

  assert.deepEqual(exported, [{
    key: 'solvableLine',
    documentId: 'demo-solvable-line',
    schemaVersion: 1,
    entities: 1,
  }]);
  assert.equal(previewExportStatus.textContent, 'CADGF preview JSON exported.');
});

test('export preview button reports unavailable when preview export fails', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    exportPreviewJson: async () => {
      throw new Error('download denied');
    },
  });

  await demo.solve();
  await findByClass(root, 'vemcad-solve-demo__preview-export').click();
  assert.equal(findByClass(root, 'vemcad-solve-demo__preview-export-status').textContent, 'Preview export unavailable.');
});

test('import project button selects an imported VEMCAD-PROJECT and keeps it local-only', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    importProjectJson: async () => importedLineProject(),
    fetchImpl: async (_url, init) => {
      const project = JSON.parse(init.body);
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            ok: true,
            value: {
              evaluatedView: project,
              evaluatedGeometry: {},
              solve: { ok: true, iterations: 1, finalError: 0 },
            },
            diagnostics: [],
          };
        },
      };
    },
  });
  const importButton = findByClass(root, 'vemcad-solve-demo__import');
  const importStatus = findByClass(root, 'vemcad-solve-demo__import-status');
  const copyButton = findByClass(root, 'vemcad-solve-demo__copy');

  await importButton.click();

  assert.equal(demo.selectedKey, 'importedProject');
  assert.equal(demo.buttons.importedProject.disabled, true);
  assert.equal(demo.buttons.importedProject.textContent, 'Imported');
  assert.match(findByClass(root, 'vemcad-solve-demo__summary').textContent, /id=imported-line/);
  assert.equal(findByClass(root, 'vemcad-solve-demo__share').textContent, 'Imported project is local. Export JSON to share.');
  assert.equal(findByClass(root, 'vemcad-solve-demo__copy-status').textContent, 'No share link for imported project.');
  assert.equal(copyButton.disabled, true);
  assert.equal(importStatus.textContent, 'Project JSON imported.');

  await demo.solve();
  assert.equal(demo.getPanelState().status, 'solved');
  assert.equal(demo.getPanelState().previewDocument.document_id, 'imported-line');
});

test('import project button reports failure for an invalid project', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    importProjectJson: async () => ({ header: { format: 'NOT-VEMCAD', version: 1 }, project: { id: 'bad' } }),
  });

  await findByClass(root, 'vemcad-solve-demo__import').click();

  assert.equal(demo.selectedKey, 'solvableLine');
  assert.equal(demo.buttons.importedProject, undefined);
  assert.equal(findByClass(root, 'vemcad-solve-demo__import-status').textContent, 'Import failed.');
  assert.match(findByClass(root, 'vemcad-solve-demo__summary').textContent, /id=demo-solvable-line/);
});

test('import success is not relabeled as import failure when auto-solve fails', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    autoSolve: true,
    importProjectJson: async () => importedLineProject(),
  });

  await findByClass(root, 'vemcad-solve-demo__import').click();

  assert.equal(demo.selectedKey, 'importedProject');
  assert.equal(findByClass(root, 'vemcad-solve-demo__import-status').textContent, 'Project JSON imported.');
  assert.equal(demo.getPanelState().status, 'failed');
  assert.match(findByClass(root, 'vemcad-solve-demo__summary').textContent, /id=imported-line/);
});

test('mountSolveWorkbenchDemo can select and auto-run a requested initial demo', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    autoSolve: true,
    initialDemo: 'conflictingLine',
  });

  assert.equal(demo.selectedKey, 'conflictingLine');
  assert.equal(demo.getPanelState().status, 'blocked');
  assert.equal(demo.getPanelState().previewDocument, null);
  assert.equal(demo.buttons.conflictingLine.disabled, true);
  assert.match(findByClass(root, 'vemcad-preview-canvas__empty').textContent, /No solved geometry/);
});

test('mountSolveWorkbenchDemo falls back to the default demo for an unknown initial demo', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({
    root,
    initialDemo: 'unknown-demo',
  });

  assert.equal(demo.selectedKey, 'solvableLine');
  assert.match(findByClass(root, 'vemcad-solve-demo__summary').textContent, /id=demo-solvable-line/);
});

test('demo buttons switch the mounted project', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);
  const demo = await mountSolveWorkbenchDemo({ root });
  const buttons = findAllByTag(root, 'button');
  const conflictButton = buttons.find((button) => button.dataset.demoId === 'conflictingLine');

  conflictButton.click();
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(demo.selectedKey, 'conflictingLine');
  assert.equal(demo.buttons.conflictingLine.disabled, true);
  assert.match(findByClass(root, 'vemcad-solve-demo__summary').textContent, /id=demo-conflicting-line/);
});
