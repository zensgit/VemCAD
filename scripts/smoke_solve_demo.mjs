#!/usr/bin/env node
import { startStaticServer } from './serve_product_web.mjs';

function assertIncludes(text, needle, label) {
  if (!text.includes(needle)) {
    throw new Error(`${label} missing ${needle}`);
  }
}

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned HTTP ${response.status}`);
  }
  return response.text();
}

function makeElement(tag, ownerDocument, id = '') {
  const children = [];
  const listeners = new Map();
  const attrs = new Map();
  const classes = new Set();
  const el = {
    id,
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
      remove(name) { classes.delete(name); },
      toggle(name, force) {
        if (force === undefined) {
          if (classes.has(name)) classes.delete(name);
          else classes.add(name);
          return classes.has(name);
        }
        if (force) classes.add(name);
        else classes.delete(name);
        return !!force;
      },
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

function installSmokeDom(search) {
  const elements = new Map();
  const document = {
    head: null,
    body: null,
    createElement(tag) {
      return makeElement(tag, document);
    },
    createElementNS(_ns, tag) {
      return makeElement(tag, document);
    },
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, makeElement('div', document, id));
      }
      return elements.get(id);
    },
    querySelector() {
      return null;
    },
  };
  document.head = makeElement('head', document, 'head');
  document.body = makeElement('body', document, 'body');
  globalThis.document = document;
  globalThis.window = { location: { search } };
  return { document, elements };
}

async function smokeBootstrapSolveDemo({
  search = '?mode=solve-demo',
  expectedDemo = 'solvableLine',
  expectedStatus = 'solved',
} = {}) {
  installSmokeDom(search);
  const app = await import(`../apps/web/app.js?smoke=${Date.now()}-${expectedDemo}`);
  try {
    app.resetVemcadWebAppBootstrapState();
    const result = await app.bootstrapVemcadWebApp({
      params: new URLSearchParams(search.startsWith('?') ? search.slice(1) : search),
      previewBootstrap: async () => {
        throw new Error('preview must not start in solve-demo smoke');
      },
      scheduleOfflineCaching: () => ({ ok: true }),
    });
    if (result.mode !== 'solve-demo') {
      throw new Error(`expected solve-demo mode, got ${result.mode}`);
    }
    if (result.demo.selectedKey !== expectedDemo) {
      throw new Error(`expected demo ${expectedDemo}, got ${result.demo.selectedKey}`);
    }
    if (result.demo.getPanelState()?.status !== expectedStatus) {
      throw new Error(`expected auto-solved demo state ${expectedStatus}, got ${result.demo.getPanelState()?.status}`);
    }
  } finally {
    app.resetVemcadWebAppBootstrapState();
    delete globalThis.document;
    delete globalThis.window;
  }
}

const started = await startStaticServer({ host: '127.0.0.1', port: 0 });

try {
  const base = `http://${started.host}:${started.server.address().port}`;
  const indexUrl = `${base}/apps/web/index.html?mode=solve-demo`;
  const indexHtml = await fetchText(indexUrl);
  assertIncludes(indexHtml, 'bootstrapVemcadWebApp', 'index.html');
  assertIncludes(indexHtml, 'cad-editor-root', 'index.html');

  const appJs = await fetchText(`${base}/apps/web/app.js`);
  assertIncludes(appJs, 'solve-demo', 'app.js');
  assertIncludes(appJs, 'mountSolveWorkbenchDemo', 'app.js');

  const demoPageJs = await fetchText(`${base}/apps/web/workbench/solver/demo_page.js`);
  assertIncludes(demoPageJs, 'VemCAD Solve Workbench', 'demo_page.js');
  assertIncludes(demoPageJs, 'renderCadgfPreviewCanvas', 'demo_page.js');
  assertIncludes(demoPageJs, 'Import Project JSON', 'demo_page.js');
  assertIncludes(demoPageJs, 'Export Solve Result JSON', 'demo_page.js');
  assertIncludes(demoPageJs, 'No solve result yet.', 'demo_page.js');
  assertIncludes(demoPageJs, 'Export CADGF Preview JSON', 'demo_page.js');

  const previewCanvasJs = await fetchText(`${base}/apps/web/workbench/solver/preview_canvas.js`);
  assertIncludes(previewCanvasJs, 'Solved geometry preview', 'preview_canvas.js');

  await smokeBootstrapSolveDemo();
  await smokeBootstrapSolveDemo({
    search: '?mode=solve-demo&demo=conflictingLine',
    expectedDemo: 'conflictingLine',
    expectedStatus: 'blocked',
  });

  console.log(`solve-demo smoke PASS: ${indexUrl}`);
} finally {
  await started.stop();
}
