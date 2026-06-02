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
    const [bridgeMod, entryMod, exportsMod, nativeSolveMod] = await Promise.all([
      import('./shared/runtime_bridge.js'),
      import('./workbench/solver/editor_solve_entry.js'),
      import('./workbench/solver/editor_solve_exports.js'),
      import('./workbench/solver/editor_native_solve_panel.js'),
    ]);
    // Lightweight floating entry: a launcher that toggles a floating card holding the panel
    // (default closed). The verified panel mounts into the entry's region; not a layout dock.
    // Host it on <body>, NOT inside #cad-editor-root: the dock is position:fixed, and a
    // transform/filter/contain on the editor canvas (or any ancestor) would otherwise make
    // `fixed` resolve against that element instead of the viewport. body has no such ancestor,
    // so placement is correct by construction. (editorRoot existence already gated editor mode.)
    const entry = entryMod.buildSolveEntry({ document: doc, host: doc.body || editorRoot });
    if (!entry) return null;

    // Editor uses the NATIVE solver path: its own (VarRef) constraints (authored via
    // select->constraint) are solved via solver.export-project -> /solve-cadgf -> writeback, since
    // the semantic /solve line carries no editor constraints. The Import/Export I/O row stays
    // (geometry-level Project JSON in/out); a successful import re-mounts so the row re-reads the
    // imported document. (Semantic conflict-highlight / repro / CADGF-preview belong to the
    // semantic line — demo / imported semantic projects — not the editor's native path.)
    const reExportProject = () => {
      const exported = bridgeMod.exportRuntimeProjectFromDocumentState(documentState);
      return exported && exported.ok === true ? exported.value : null;
    };
    let current = null;
    const teardownCurrent = () => {
      if (!current) return;
      current.exportsRow?.destroy?.();
      current.native?.destroy?.();
      current = null;
    };
    const mountInner = () => {
      const native = nativeSolveMod.mountEditorNativeSolve({
        root: entry.regionRoot,
        document: doc,
        // The workspace exposes its command bus as `commands` (not `commandBus`); used for both
        // solver.export-project and the entity.applyGeometry writeback.
        commandBus: workspace?.commands,
      });
      let exportsRow = null;
      try {
        exportsRow = exportsMod.mountEditorSolveExports({
          root: entry.card,
          document: doc,
          getProject: reExportProject,
          // The native path has no semantic solve envelope, so repro / CADGF-preview (semantic
          // artifacts) stay disabled here; Import + Export Project JSON work at the geometry level.
          getSolveState: () => ({}),
          getShareUrl: () => doc.defaultView?.location?.href ?? globalThis.location?.href ?? null,
          loadProject: (project) => bridgeMod.importRuntimeProjectToDocumentState(documentState, project),
          onImported: () => refresh(),
        });
      } catch {
        exportsRow = null;
      }
      return { native, exportsRow };
    };
    const refresh = () => { teardownCurrent(); current = mountInner(); };

    current = mountInner();
    return {
      ok: true,
      entry,
      get native() { return current?.native; },
      get exports() { return current?.exportsRow; },
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
