import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..', '..');

// The cases below that import the CADGameFusion web_viewer bootstrap entry
// (deps/.../web_viewer/app.js `bootstrapWebViewerEntry`/`isDesktopRuntime` and
// `legacy_app_bootstrap.js`) exercise the web-runtime-hardening work that is NOT
// yet landed on the pinned submodule (ba5f882) — those symbols/files do not exist
// there. Skip them until that hardening lands in CADGameFusion + a VemCAD pointer
// bump (A→C). The product-side cases (apps/web/app.js) below run unconditionally.
const SUBMODULE_ENTRY_SKIP =
  'pending CADGameFusion web_viewer bootstrap entry API on the pinned submodule (A→C)';

function installDomStubs({ search = '' } = {}) {
  const elements = new Map();

  function makeElement(id) {
    const classes = new Set();
    const attrs = new Map();
    return {
      id,
      classList: {
        add(name) {
          classes.add(name);
        },
        remove(name) {
          classes.delete(name);
        },
        toggle(name, force) {
          if (force === undefined) {
            if (classes.has(name)) classes.delete(name);
            else classes.add(name);
            return;
          }
          if (force) classes.add(name);
          else classes.delete(name);
        },
        contains(name) {
          return classes.has(name);
        },
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
      textContent: '',
    };
  }

  const documentStub = {
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, makeElement(id));
      }
      return elements.get(id);
    },
  };

  globalThis.window = { location: { search } };
  globalThis.document = documentStub;
  return { elements, documentStub };
}

function cleanupDomStubs() {
  delete globalThis.window;
  delete globalThis.document;
}

test('bootstrapWebViewerEntry prefers product bootstrap when reachable', { skip: SUBMODULE_ENTRY_SKIP }, async () => {
  installDomStubs();
  globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP = true;

  const moduleUrl = pathToFileURL(path.join(repoRoot, 'deps/cadgamefusion/tools/web_viewer/app.js')).href;
  const entryModule = await import(moduleUrl);

  let productCalls = 0;
  let legacyCalls = 0;
  const result = await entryModule.bootstrapWebViewerEntry({
    canLoadProductBootstrapImpl: async () => true,
    bootstrapProductWebAppImpl: async () => {
      productCalls += 1;
      return { mode: 'product' };
    },
    bootstrapLegacyWebViewerAppImpl: async () => {
      legacyCalls += 1;
      return { mode: 'legacy' };
    },
  });

  assert.deepEqual(result, { mode: 'product' });
  assert.equal(productCalls, 1);
  assert.equal(legacyCalls, 0);

  delete globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP;
  cleanupDomStubs();
});

test('bootstrapWebViewerEntry falls back to legacy bootstrap when product module is unreachable', { skip: SUBMODULE_ENTRY_SKIP }, async () => {
  installDomStubs();
  globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP = true;

  const moduleUrl = pathToFileURL(path.join(repoRoot, 'deps/cadgamefusion/tools/web_viewer/app.js')).href;
  const entryModule = await import(`${moduleUrl}?legacy-fallback`);

  let legacyCalls = 0;
  const result = await entryModule.bootstrapWebViewerEntry({
    canLoadProductBootstrapImpl: async () => false,
    bootstrapProductWebAppImpl: async () => {
      throw new Error('product bootstrap should not run');
    },
    bootstrapLegacyWebViewerAppImpl: async () => {
      legacyCalls += 1;
      return { mode: 'legacy' };
    },
  });

  assert.deepEqual(result, { mode: 'legacy' });
  assert.equal(legacyCalls, 1);
  assert.equal(globalThis.window.__vemcadBootstrap.source, 'legacy-fallback');
  assert.equal(globalThis.window.__vemcadBootstrap.fallbackReason, 'product-bootstrap-unreachable');

  delete globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP;
  cleanupDomStubs();
});

test('canLoadProductBootstrap disables product probing in desktop runtime', { skip: SUBMODULE_ENTRY_SKIP }, async () => {
  installDomStubs();
  globalThis.window.vemcadDesktop = {};
  globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP = true;
  globalThis.fetch = async () => {
    throw new Error('desktop product probe should not fetch');
  };

  const moduleUrl = pathToFileURL(path.join(repoRoot, 'deps/cadgamefusion/tools/web_viewer/app.js')).href;
  const entryModule = await import(`${moduleUrl}?desktop-skip`);

  assert.equal(entryModule.isDesktopRuntime(), true);
  assert.equal(entryModule.getProductBootstrapFallbackReason(), 'desktop-runtime-product-bootstrap-disabled');
  assert.equal(await entryModule.canLoadProductBootstrap(), false);

  let legacyCalls = 0;
  const result = await entryModule.bootstrapWebViewerEntry({
    bootstrapProductWebAppImpl: async () => {
      throw new Error('desktop product bootstrap should not run');
    },
    bootstrapLegacyWebViewerAppImpl: async () => {
      legacyCalls += 1;
      return { mode: 'legacy' };
    },
  });

  assert.deepEqual(result, { mode: 'legacy' });
  assert.equal(legacyCalls, 1);
  assert.equal(globalThis.window.__vemcadBootstrap.fallbackReason, 'desktop-runtime-product-bootstrap-disabled');

  delete globalThis.fetch;
  delete globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP;
  cleanupDomStubs();
});

test('installVemcadAppBridge imports payload into bootstrapped workspace', async () => {
  const { elements } = installDomStubs({ search: '?mode=preview' });
  const moduleUrl = pathToFileURL(path.join(repoRoot, 'apps/web/app.js')).href;
  const appModule = await import(`${moduleUrl}?bridge-test`);

  appModule.resetVemcadWebAppBootstrapState();

  const imported = [];
  const bridge = appModule.installVemcadAppBridge({ params: new URLSearchParams('mode=preview') });
  const workspace = {
    importPayload(payload, options) {
      imported.push({ payload, options });
    },
  };

  await appModule.ensureWorkspaceBootstrapped({
    params: new URLSearchParams('mode=preview'),
    loadModule: async () => ({
      bootstrapCadWorkspace() {
        return workspace;
      },
    }),
  });

  const payload = { entities: [{ id: 1 }] };
  await bridge.switchToEditor(payload, {
    fitView: false,
  });

  assert.equal(elements.get('preview-root').classList.contains('is-hidden'), true);
  assert.equal(elements.get('cad-editor-root').classList.contains('is-hidden'), false);

  assert.equal(typeof globalThis.window.__vemcadApp.switchToEditor, 'function');
  assert.deepEqual(imported, [{ payload, options: { fitView: false } }]);

  appModule.resetVemcadWebAppBootstrapState();
  cleanupDomStubs();
});

test('installVemcadAppBridge exposes a lazy solve panel mount hook', async () => {
  installDomStubs({ search: '?mode=editor' });
  const moduleUrl = pathToFileURL(path.join(repoRoot, 'apps/web/app.js')).href;
  const appModule = await import(`${moduleUrl}?solve-panel-bridge`);

  let loadCount = 0;
  let mounted = null;
  const root = { appendChild() {} };
  const project = { project: { id: 'p1' } };
  const controller = { getState() { return { status: 'idle' }; } };

  const bridge = appModule.installVemcadAppBridge({
    params: new URLSearchParams('mode=editor'),
    loadSolvePanelModule: async () => {
      loadCount += 1;
      return {
        createSolveWorkbenchPanel(args) {
          mounted = args;
          return { kind: 'panel-handle', args };
        },
      };
    },
  });

  const result = await bridge.mountSolvePanel(root, { project, controller, labels: { title: 'Solve' } });

  assert.equal(typeof globalThis.window.__vemcadApp.mountSolvePanel, 'function');
  assert.equal(loadCount, 1);
  assert.equal(result.kind, 'panel-handle');
  assert.deepEqual(mounted, { root, project, controller, labels: { title: 'Solve' } });

  cleanupDomStubs();
});

test('bootstrapVemcadWebApp schedules product offline cache after preview bootstrap', async () => {
  installDomStubs({ search: '' });
  const moduleUrl = pathToFileURL(path.join(repoRoot, 'apps/web/app.js')).href;
  const appModule = await import(`${moduleUrl}?preview-offline-cache`);

  appModule.resetVemcadWebAppBootstrapState();
  const scheduled = [];
  let previewLoads = 0;

  const result = await appModule.bootstrapVemcadWebApp({
    params: new URLSearchParams(''),
    previewBootstrap: async () => {
      previewLoads += 1;
    },
    scheduleOfflineCaching: (context) => {
      scheduled.push(context);
      return Promise.resolve({ ok: true });
    },
  });

  assert.equal(result.mode, 'preview');
  assert.equal(previewLoads, 1);
  assert.deepEqual(scheduled, [{ mode: 'preview' }]);

  appModule.resetVemcadWebAppBootstrapState();
  cleanupDomStubs();
});

test('bootstrapVemcadWebApp does not block preview startup when offline scheduling fails', async () => {
  installDomStubs({ search: '' });
  const moduleUrl = pathToFileURL(path.join(repoRoot, 'apps/web/app.js')).href;
  const appModule = await import(`${moduleUrl}?preview-offline-cache-fails`);

  appModule.resetVemcadWebAppBootstrapState();
  const result = await appModule.bootstrapVemcadWebApp({
    params: new URLSearchParams(''),
    previewBootstrap: async () => {},
    scheduleOfflineCaching: () => {
      throw new Error('offline cache unavailable');
    },
  });

  assert.equal(result.mode, 'preview');

  appModule.resetVemcadWebAppBootstrapState();
  cleanupDomStubs();
});

test('bootstrapVemcadWebApp schedules product offline cache after editor bootstrap', async () => {
  installDomStubs({ search: '?mode=editor' });
  const moduleUrl = pathToFileURL(path.join(repoRoot, 'apps/web/app.js')).href;
  const appModule = await import(`${moduleUrl}?editor-offline-cache`);

  appModule.resetVemcadWebAppBootstrapState();
  const scheduled = [];
  const workspace = {
    importPayload() {},
  };

  const result = await appModule.bootstrapVemcadWebApp({
    params: new URLSearchParams('mode=editor'),
    ensureWorkspaceBootstrappedImpl: async () => workspace,
    scheduleOfflineCaching: (context) => {
      scheduled.push(context);
      return Promise.resolve({ ok: true });
    },
  });

  assert.equal(result.mode, 'editor');
  assert.equal(typeof result.workspace.importPayload, typeof workspace.importPayload);
  assert.deepEqual(scheduled, [{ mode: 'editor' }]);

  appModule.resetVemcadWebAppBootstrapState();
  cleanupDomStubs();
});

test('bootstrapVemcadWebApp mounts solve demo mode without starting preview or workspace', async () => {
  const { elements } = installDomStubs({ search: '?mode=solve-demo' });
  const moduleUrl = pathToFileURL(path.join(repoRoot, 'apps/web/app.js')).href;
  const appModule = await import(`${moduleUrl}?solve-demo-mode`);

  appModule.resetVemcadWebAppBootstrapState();
  const scheduled = [];
  let mounted = null;

  const result = await appModule.bootstrapVemcadWebApp({
    params: new URLSearchParams('mode=solve-demo'),
    previewBootstrap: async () => {
      throw new Error('preview should not start in solve-demo mode');
    },
    ensureWorkspaceBootstrappedImpl: async () => {
      throw new Error('workspace should not start in solve-demo mode');
    },
    scheduleOfflineCaching: (context) => {
      scheduled.push(context);
      return Promise.resolve({ ok: true });
    },
    loadSolveDemoModule: async () => ({
      async mountSolveWorkbenchDemo(args) {
        mounted = args;
        return { kind: 'solve-demo-handle' };
      },
    }),
  });

  assert.equal(result.mode, 'solve-demo');
  assert.deepEqual(result.demo, { kind: 'solve-demo-handle' });
  assert.equal(mounted.root.id, 'cad-editor-root');
  assert.equal(mounted.autoSolve, true);
  assert.equal(typeof mounted.appBridge.mountSolvePanel, 'function');
  assert.equal(elements.get('preview-root').classList.contains('is-hidden'), true);
  assert.equal(elements.get('cad-editor-root').classList.contains('is-hidden'), false);
  assert.deepEqual(scheduled, [{ mode: 'solve-demo' }]);

  appModule.resetVemcadWebAppBootstrapState();
  cleanupDomStubs();
});

test('bootstrapLegacyWebViewerApp wires preview mode and editor handoff contract', { skip: SUBMODULE_ENTRY_SKIP }, async () => {
  installDomStubs({ search: '' });
  const moduleUrl = pathToFileURL(path.join(repoRoot, 'deps/cadgamefusion/tools/web_viewer/legacy_app_bootstrap.js')).href;
  const legacyModule = await import(`${moduleUrl}?preview-test`);

  let previewLoads = 0;
  let workspaceImports = 0;
  const workspace = {
    importPayload() {
      workspaceImports += 1;
    },
  };

  const result = await legacyModule.bootstrapLegacyWebViewerApp({
    params: new URLSearchParams(''),
    loadPreviewModule: async () => {
      previewLoads += 1;
      return {};
    },
    loadWorkspaceModule: async () => ({
      bootstrapCadWorkspace() {
        return workspace;
      },
    }),
  });

  assert.deepEqual(result, { mode: 'preview' });
  assert.equal(previewLoads, 1);
  assert.equal(typeof globalThis.window.__vemcadApp.switchToEditor, 'function');

  await globalThis.window.__vemcadApp.switchToEditor({ entities: [] });
  assert.equal(workspaceImports, 1);

  cleanupDomStubs();
});
