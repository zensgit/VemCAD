import { bootstrapLegacyPreviewRuntime } from './preview/runtime/preview_bootstrap.js';
import { scheduleProductOfflineCaching } from './offline/product_offline_cache.js';

const EDITOR_MODES = new Set(['editor', 'cad', 'draft']);
const SOLVE_DEMO_MODES = new Set(['solve-demo', 'solver-demo']);

function resolveSearchParams(params = null) {
  if (params instanceof URLSearchParams) {
    return params;
  }
  if (typeof params === 'string') {
    return new URLSearchParams(params);
  }
  return new URLSearchParams(globalThis.window?.location?.search || '');
}

function setModeVisibility(editorVisible) {
  const doc = globalThis.document;
  if (!doc) return;

  const previewRoot = doc.getElementById('preview-root');
  const editorRoot = doc.getElementById('cad-editor-root');

  if (previewRoot) {
    previewRoot.classList.toggle('is-hidden', editorVisible);
    if (editorVisible) {
      previewRoot.setAttribute('aria-hidden', 'true');
    } else {
      previewRoot.removeAttribute('aria-hidden');
    }
  }

  if (editorRoot) {
    editorRoot.classList.toggle('is-hidden', !editorVisible);
    if (editorVisible) {
      editorRoot.removeAttribute('aria-hidden');
    } else {
      editorRoot.setAttribute('aria-hidden', 'true');
    }
  }
}

export function setPreviewMode() {
  setModeVisibility(false);
}

export function setEditorMode() {
  setModeVisibility(true);
}

let workspaceInstance = null;
let workspaceBootstrapPromise = null;

async function loadWorkbenchBootstrapModule() {
  return import('./workbench/bootstrap/workspace_bootstrap.js');
}

async function loadSolvePanelModule() {
  return import('./workbench/panels/solve_panel.js');
}

async function loadSolveDemoModule() {
  return import('./workbench/solver/demo_page.js');
}

function resolveSolveDemoRoot() {
  const doc = globalThis.document;
  if (!doc) return null;
  return doc.getElementById('cad-editor-root')
    || doc.getElementById('app')
    || doc.body
    || null;
}

export async function ensureWorkspaceBootstrapped({
  params = null,
  loadModule = loadWorkbenchBootstrapModule,
} = {}) {
  const resolvedParams = resolveSearchParams(params);
  if (workspaceInstance) return workspaceInstance;
  if (workspaceBootstrapPromise) return workspaceBootstrapPromise;

  workspaceBootstrapPromise = (async () => {
    try {
      const workbench = await loadModule();
      workspaceInstance = workbench.bootstrapCadWorkspace({ params: resolvedParams });
      return workspaceInstance;
    } catch (error) {
      workspaceBootstrapPromise = null;
      throw error;
    }
  })();

  return workspaceBootstrapPromise;
}

export function installVemcadAppBridge({
  params = null,
  loadSolvePanelModule: loadSolvePanel = loadSolvePanelModule,
} = {}) {
  const resolvedParams = resolveSearchParams(params);
  const bridge = {
    async switchToEditor(documentJson, { fitView = true } = {}) {
      setEditorMode();
      const workspace = await ensureWorkspaceBootstrapped({ params: resolvedParams });
      if (workspace && typeof workspace.importPayload === 'function') {
        workspace.importPayload(documentJson, { fitView });
      }
      return workspace;
    },
    async mountSolvePanel(root, options = {}) {
      const panel = await loadSolvePanel();
      return panel.createSolveWorkbenchPanel({ root, ...options });
    },
  };

  if (globalThis.window) {
    globalThis.window.__vemcadApp = bridge;
  }

  return bridge;
}

function triggerProductOfflineCaching(scheduleOfflineCaching, context) {
  try {
    const result = scheduleOfflineCaching(context);
    if (result && typeof result.catch === 'function') {
      result.catch(() => {});
    }
  } catch {
    // Product offline caching is opportunistic and must not block app startup.
  }
}

// Default editor-solve mounter: in editor mode, mount a READ-ONLY solve panel (solve the
// current document → diagnostics + preview; no geometry writeback) into a dedicated region
// of the editor root. Opportunistic + resilient — any failure (no DOM, no document, modules
// unavailable) returns null and never blocks editor startup. Real collaborators are imported
// lazily here so app.js itself stays free of submodule-coupled static imports.
async function mountEditorSolveRegion({ workspace, params = null } = {}) {
  void params;
  try {
    const doc = globalThis.document;
    const documentState = workspace?.state?.document;
    if (!doc || !documentState) return null;
    const editorRoot = doc.getElementById('cad-editor-root');
    if (!editorRoot) return null;
    const [bridgeMod, panelMod, controllerMod, editorSolveMod, entryMod, exportsMod] = await Promise.all([
      import('./shared/runtime_bridge.js'),
      import('./workbench/panels/solve_panel.js'),
      import('./workbench/solver/solve_workbench.js'),
      import('./workbench/solver/editor_solve.js'),
      import('./workbench/solver/editor_solve_entry.js'),
      import('./workbench/solver/editor_solve_exports.js'),
    ]);
    // Lightweight floating entry: a launcher that toggles a floating card holding the panel
    // (default closed). The verified panel mounts into the entry's region; not a layout dock.
    // Host it on <body>, NOT inside #cad-editor-root: the dock is position:fixed, and a
    // transform/filter/contain on the editor canvas (or any ancestor) would otherwise make
    // `fixed` resolve against that element instead of the viewport. body has no such ancestor,
    // so placement is correct by construction. (editorRoot existence already gated editor mode.)
    const entry = entryMod.buildSolveEntry({ document: doc, host: doc.body || editorRoot });
    if (!entry) return null;

    // Panel collaborators are stable across re-mounts (workspace is fixed); only the document
    // snapshot changes (e.g. after an import).
    const panelDeps = {
      documentState,
      exportProject: bridgeMod.exportRuntimeProjectFromDocumentState,
      createPanel: panelMod.createSolveWorkbenchPanel,
      createController: controllerMod.createSolveWorkbenchController,
      // Auto-apply solved geometry back into the editor via the undoable command bus.
      // Guarded: no commandBus -> editor_solve degrades to read-only (solve + display only).
      applyUpdates: ({ updates }) => workspace?.commandBus?.execute('entity.applyGeometry', { updates }),
      // Highlight conflicting entities (over-constrained solve) by selecting them in the editor.
      highlightEntities: (ids) => workspace?.selection?.setSelection?.(ids, ids?.[0] ?? null),
      // Clear a conflict highlight on a later conflict-free solve, but ONLY if the selection is
      // still the ids we set (the user did not change it since) -> never wipes a user selection.
      clearHighlight: (ids) => {
        const selection = workspace?.selection;
        if (!selection || typeof selection.setSelection !== 'function') return;
        if (editorSolveMod.shouldClearHighlight(selection.entityIds, ids)) selection.setSelection([], null);
      },
    };

    // current = { mounted, exportsRow, unsubExports }. A successful import re-mounts (refresh) so
    // the panel + exports snapshot the freshly-imported document; teardown disposes EVERY old
    // handle (the exports subscription, the row DOM, and editor_solve's own subscription/panel)
    // so a re-mount never leaves a stale subscriber updating a detached row.
    let current = null;
    const teardownCurrent = () => {
      if (!current) return;
      try { current.unsubExports?.(); } catch { /* ignore */ }
      current.exportsRow?.destroy?.();
      current.mounted?.destroy?.();
      current = null;
    };
    const mountInner = () => {
      const mounted = editorSolveMod.mountEditorSolvePanel({ root: entry.regionRoot, ...panelDeps });
      if (mounted?.ok !== true) return { mounted, ok: false };
      let exportsRow = null;
      let unsubExports = null;
      try {
        exportsRow = exportsMod.mountEditorSolveExports({
          root: entry.card,
          document: doc,
          getProject: () => mounted.project,
          getSolveState: () => mounted.controller?.getState?.() ?? {},
          getShareUrl: () => doc.defaultView?.location?.href ?? globalThis.location?.href ?? null,
          // Load a project (or repro bundle) into the editor document. Returns the bridge's
          // {ok,...}; the row only re-mounts on ok === true.
          loadProject: (project) => bridgeMod.importRuntimeProjectToDocumentState(documentState, project),
          onImported: () => refresh(),
        });
        const unsub = mounted.controller?.subscribe?.(() => exportsRow?.update?.());
        unsubExports = typeof unsub === 'function' ? unsub : null;
      } catch {
        exportsRow = null;
        unsubExports = null;
      }
      return { mounted, exportsRow, unsubExports, ok: true };
    };
    const refresh = () => { teardownCurrent(); current = mountInner(); };

    current = mountInner();
    // If the document could not be exported to a solvable project, don't leave a launcher that
    // opens an empty card — tear the entry back down and surface the same failure result.
    if (!current.ok) {
      entry.dock?.remove?.();
      return current.mounted;
    }
    return {
      get ok() { return current?.mounted?.ok ?? false; },
      get project() { return current?.mounted?.project; },
      get controller() { return current?.mounted?.controller; },
      get panel() { return current?.mounted?.panel; },
      get exports() { return current?.exportsRow; },
      entry,
      refresh,
      destroy() { teardownCurrent(); entry.dock?.remove?.(); },
    };
  } catch {
    return null;
  }
}

export async function bootstrapVemcadWebApp({
  params = null,
  previewBootstrap = bootstrapLegacyPreviewRuntime,
  scheduleOfflineCaching = scheduleProductOfflineCaching,
  ensureWorkspaceBootstrappedImpl = ensureWorkspaceBootstrapped,
  loadSolveDemoModule: loadSolveDemo = loadSolveDemoModule,
  mountEditorSolveImpl = mountEditorSolveRegion,
} = {}) {
  const resolvedParams = resolveSearchParams(params);
  const mode = (resolvedParams.get('mode') || '').trim().toLowerCase();
  const bridge = installVemcadAppBridge({ params: resolvedParams });

  if (SOLVE_DEMO_MODES.has(mode)) {
    setEditorMode();
    const demoRoot = resolveSolveDemoRoot();
    const demoModule = await loadSolveDemo();
    const demo = await demoModule.mountSolveWorkbenchDemo({
      root: demoRoot,
      appBridge: bridge,
      autoSolve: true,
      initialDemo: resolvedParams.get('demo'),
    });
    triggerProductOfflineCaching(scheduleOfflineCaching, { mode: 'solve-demo' });
    return { mode: 'solve-demo', bridge, demo };
  }

  if (EDITOR_MODES.has(mode)) {
    setEditorMode();
    const workspace = await ensureWorkspaceBootstrappedImpl({ params: resolvedParams });
    const solve = await mountEditorSolveImpl({ workspace, params: resolvedParams });
    triggerProductOfflineCaching(scheduleOfflineCaching, { mode: 'editor' });
    return { mode: 'editor', bridge, workspace, solve };
  }

  setPreviewMode();
  await previewBootstrap();
  triggerProductOfflineCaching(scheduleOfflineCaching, { mode: 'preview' });
  return { mode: 'preview', bridge };
}

export function resetVemcadWebAppBootstrapState() {
  workspaceInstance = null;
  workspaceBootstrapPromise = null;
}
