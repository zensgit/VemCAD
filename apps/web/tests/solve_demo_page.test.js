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
      listeners.get('click')?.({ type: 'click', target: el });
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

test('mountSolveWorkbenchDemo mounts selectable demos and solves without a live /solve service', async () => {
  const document = makeDocument();
  const root = makeElement('div', document);

  const demo = await mountSolveWorkbenchDemo({ root });

  assert.equal(root.classList.contains('vemcad-solve-demo'), true);
  assert.equal(demo.selectedKey, 'solvableLine');
  assert.equal(demo.buttons.solvableLine.disabled, true);
  assert.equal(demo.buttons.conflictingLine.disabled, false);
  assert.match(findByClass(root, 'vemcad-solve-demo__summary').textContent, /id=demo-solvable-line/);

  await demo.solve();
  assert.equal(demo.getPanelState().status, 'solved');
  assert.equal(demo.getPanelState().previewDocument.document_id, 'demo-solvable-line');
  assert.equal(findByTag(root, 'svg').getAttribute('aria-label'), 'Solved geometry preview');

  await demo.select('conflictingLine');
  await demo.solve();
  assert.equal(demo.selectedKey, 'conflictingLine');
  assert.equal(demo.getPanelState().status, 'blocked');
  assert.equal(demo.getPanelState().previewDocument, null);
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
