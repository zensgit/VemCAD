import test from 'node:test';
import assert from 'node:assert/strict';
import { createSolveWorkbenchPanel } from '../workbench/panels/solve_panel.js';
import { SOLVE_WORKBENCH_DEMOS } from '../workbench/solver/demo_projects.js';

function makeElement(tag, ownerDocument) {
  const children = [];
  const attrs = new Map();
  const listeners = new Map();
  const classes = new Set();
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
  };
  return document;
}

function findByTag(root, tag) {
  return root.children.find((child) => child.tagName === tag.toUpperCase());
}

function makeController(finalState) {
  let listener = null;
  let state = {
    status: 'idle',
    summary: null,
    envelope: null,
    previewDocument: null,
    diagnostics: [],
  };
  return {
    getState: () => state,
    subscribe(fn) {
      listener = fn;
      fn(state);
      return () => { listener = null; };
    },
    async solve(project) {
      assert.equal(project.project.id, SOLVE_WORKBENCH_DEMOS.solvableLine.project.id);
      state = { ...state, status: 'solving' };
      listener?.(state);
      state = finalState;
      listener?.(state);
      return state;
    },
  };
}

test('createSolveWorkbenchPanel renders idle state and runs the controller on click', async () => {
  const document = makeDocument();
  const root = makeElement('section', document);
  const panel = createSolveWorkbenchPanel({
    root,
    project: SOLVE_WORKBENCH_DEMOS.solvableLine,
    controller: makeController({
      status: 'solved',
      summary: {
        status: 'solved',
        structuralState: 'underconstrained',
        dofEstimate: 1,
        conflictGroupCount: 0,
        redundantConstraintEstimate: 0,
        iterations: 4,
        finalError: 0.000001,
      },
      previewDocument: { schema_version: 1, entities: [{ id: 1 }, { id: 2 }] },
      diagnostics: [{ code: 'SOLVE_ANALYSIS', message: 'ok' }],
    }),
  });

  const button = findByTag(root, 'button');
  assert.equal(root.classList.contains('vemcad-solve-panel'), true);
  assert.equal(root.children[1].textContent, 'Ready');
  assert.equal(root.children[2].textContent, 'No solve has run yet.');

  button.click();
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(panel.getState().status, 'solved');
  assert.equal(root.children[1].textContent, 'Solved');
  assert.equal(root.children[1].dataset.status, 'solved');
  assert.match(root.children[2].textContent, /state=underconstrained/);
  assert.match(root.children[3].textContent, /2 entities/);
  assert.equal(root.children.at(-1).children[0].textContent, 'SOLVE_ANALYSIS: ok');
});

test('panel keeps blocked solve status visible', async () => {
  const document = makeDocument();
  const root = makeElement('section', document);
  createSolveWorkbenchPanel({
    root,
    project: SOLVE_WORKBENCH_DEMOS.solvableLine,
    controller: makeController({
      status: 'blocked',
      summary: {
        status: 'blocked',
        structuralState: 'overconstrained',
        dofEstimate: 0,
        conflictGroupCount: 1,
        redundantConstraintEstimate: 0,
        iterations: 100,
        finalError: 1.2,
      },
      previewDocument: null,
      diagnostics: [{ code: 'SOLVE_UNSATISFIED', message: 'conflict' }],
    }),
  });

  findByTag(root, 'button').click();
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(root.children[1].textContent, 'Blocked');
  assert.match(root.children[2].textContent, /conflicts=1/);
  assert.equal(root.children[3].textContent, 'No CADGF preview document.');
  assert.equal(root.children.at(-1).children[0].textContent, 'SOLVE_UNSATISFIED: conflict');
});

test('panel shows conflicting entities + the solver hint on a conflict', async () => {
  const document = makeDocument();
  const root = makeElement('section', document);
  createSolveWorkbenchPanel({
    root,
    project: SOLVE_WORKBENCH_DEMOS.solvableLine,
    controller: makeController({
      status: 'blocked',
      summary: {
        status: 'blocked', structuralState: 'overconstrained', dofEstimate: 0,
        conflictGroupCount: 1, redundantConstraintEstimate: 0, iterations: 5, finalError: 1,
        conflictEntityIds: [7, 9],
        conflictAdvice: 'Relax or remove one conflicting constraint near the anchor.',
      },
      previewDocument: null,
      diagnostics: [{ code: 'SOLVE_UNSATISFIED', message: 'conflict' }],
    }),
  });

  findByTag(root, 'button').click();
  await new Promise((resolve) => setImmediate(resolve));

  const advice = root.children[4]; // title, status, details, preview, ADVICE, button, h3, diag
  assert.match(advice.textContent, /Conflicting: 7, 9/);
  assert.match(advice.textContent, /Relax or remove one conflicting constraint/);
  assert.equal(advice.dataset.hasConflict, 'true');
});

test('panel shows no advice line on a clean (conflict-free) solve', async () => {
  const document = makeDocument();
  const root = makeElement('section', document);
  createSolveWorkbenchPanel({
    root,
    project: SOLVE_WORKBENCH_DEMOS.solvableLine,
    controller: makeController({
      status: 'solved',
      summary: { status: 'solved', structuralState: 'wellconstrained', conflictGroupCount: 0, conflictEntityIds: [], conflictAdvice: null },
      previewDocument: { schema_version: 1, entities: [] },
      diagnostics: [],
    }),
  });

  findByTag(root, 'button').click();
  await new Promise((resolve) => setImmediate(resolve));

  const advice = root.children[4];
  assert.equal(advice.textContent, '');
  assert.equal(advice.dataset.hasConflict, 'false');
});
