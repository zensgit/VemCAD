import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildSolveEntry,
  ensureEditorSolveStyles,
  EDITOR_SOLVE_DOCK_ID,
  EDITOR_SOLVE_REGION_ID,
  EDITOR_SOLVE_STYLE_ID,
} from '../workbench/solver/editor_solve_entry.js';

// Minimal DOM double — enough for the entry chrome + toggle, no submodule, no real DOM.
function makeDocument() {
  const byId = new Map();
  function makeElement(tag) {
    const attrs = new Map();
    const listeners = new Map();
    const el = {
      tagName: String(tag).toUpperCase(),
      children: [],
      parentNode: null,
      type: '',
      textContent: '',
      hidden: false,
      dataset: {},
      _class: '',
      get className() { return this._class; },
      set className(v) { this._class = v; },
      get id() { return this._id; },
      set id(v) { this._id = v; byId.set(v, el); },
      setAttribute(name, value) { attrs.set(name, String(value)); },
      getAttribute(name) { return attrs.get(name) ?? null; },
      appendChild(child) { child.parentNode = el; el.children.push(child); return child; },
      removeChild(child) { el.children = el.children.filter((c) => c !== child); return child; },
      remove() { el.parentNode?.removeChild(el); },
      replaceChildren() { el.children = []; },
      addEventListener(type, handler) { listeners.set(type, handler); },
      click() { listeners.get('click')?.({ type: 'click', target: el }); },
      querySelector(sel) { return queryOne(el, sel); },
    };
    return el;
  }
  function matches(el, sel) {
    if (sel.startsWith('.')) return String(el._class || '').split(/\s+/).includes(sel.slice(1));
    if (sel.startsWith('#')) return el._id === sel.slice(1);
    return false;
  }
  function queryOne(root, sel) {
    for (const child of root.children) {
      if (matches(child, sel)) return child;
      const deep = queryOne(child, sel);
      if (deep) return deep;
    }
    return null;
  }
  const document = {
    head: null,
    createElement(tag) { return makeElement(tag); },
    getElementById(id) { const el = byId.get(id); return el && !el._detached ? el : null; },
    querySelector(sel) { return document.head ? queryOne(document.head, sel) || queryOne(document.body, sel) : null; },
  };
  document.head = makeElement('head');
  document.body = makeElement('body');
  // a remove() that also de-registers from byId so getElementById reflects teardown
  return document;
}

test('buildSolveEntry: builds launcher + hidden card + region, default CLOSED', () => {
  const document = makeDocument();
  const host = document.createElement('div');
  const entry = buildSolveEntry({ document, host });

  assert.ok(entry, 'entry built');
  assert.equal(host.children[0], entry.dock);
  assert.equal(entry.dock.id, EDITOR_SOLVE_DOCK_ID);
  assert.equal(entry.regionRoot.id, EDITOR_SOLVE_REGION_ID);
  assert.equal(entry.isOpen(), false);
  assert.equal(entry.card.hidden, true);
  assert.equal(entry.dock.dataset.open, 'false');
  assert.equal(entry.launcher.getAttribute('aria-expanded'), 'false');
  // styles injected once
  assert.ok(document.head.children.some((c) => c.id === EDITOR_SOLVE_STYLE_ID));
});

test('buildSolveEntry: launcher toggles the card open/closed; close button closes', () => {
  const document = makeDocument();
  const host = document.createElement('div');
  const entry = buildSolveEntry({ document, host });

  entry.launcher.click();
  assert.equal(entry.isOpen(), true);
  assert.equal(entry.card.hidden, false);
  assert.equal(entry.dock.dataset.open, 'true');
  assert.equal(entry.launcher.getAttribute('aria-expanded'), 'true');

  entry.launcher.click();
  assert.equal(entry.isOpen(), false);
  assert.equal(entry.card.hidden, true);

  entry.open();
  assert.equal(entry.isOpen(), true);
  // the ✕ close button
  entry.card.querySelector('.vemcad-solve-dock__close').click();
  assert.equal(entry.isOpen(), false);
  assert.equal(entry.card.hidden, true);
});

test('buildSolveEntry: idempotent — a second call reuses the existing dock and clears the region', () => {
  const document = makeDocument();
  const host = document.createElement('div');
  const first = buildSolveEntry({ document, host });
  first.regionRoot.appendChild(document.createElement('p')); // pretend a panel mounted

  const second = buildSolveEntry({ document, host });
  assert.equal(second.dock, first.dock, 'same dock reused (no duplicate)');
  assert.equal(host.children.length, 1, 'host still has exactly one dock');
  assert.equal(second.regionRoot.children.length, 0, 'region cleared for a fresh mount');
});

test('buildSolveEntry: returns null when document/host cannot host elements', () => {
  assert.equal(buildSolveEntry({ document: null, host: {} }), null);
  assert.equal(buildSolveEntry({ document: { createElement() {} }, host: null }), null);
  assert.equal(buildSolveEntry(), null);
});

test('ensureEditorSolveStyles: injects once, no-op without a head', () => {
  const document = makeDocument();
  ensureEditorSolveStyles(document);
  ensureEditorSolveStyles(document);
  assert.equal(document.head.children.filter((c) => c.id === EDITOR_SOLVE_STYLE_ID).length, 1);
  assert.doesNotThrow(() => ensureEditorSolveStyles({}));
  assert.doesNotThrow(() => ensureEditorSolveStyles(null));
});
