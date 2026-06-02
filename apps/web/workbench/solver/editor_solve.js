// Read-only "solve the current editor sketch" composition for editor mode.
//
// Wires the EXISTING product-layer pieces together WITHOUT modifying the solve panel,
// controller, or demo:
//   editor DocumentState --(runtime bridge export)--> VEMCAD-PROJECT --> solve panel + controller --> /solve
//
// READ-ONLY by design: it solves the current document and DISPLAYS diagnostics + a
// solved-geometry preview in the panel. It does NOT write solved geometry back into the
// editor. Whether solved geometry auto-applies or waits for an explicit user accept is a
// deferred product decision, so this slice deliberately performs no document mutation.
//
// Pure composition: every collaborator (exportProject / createPanel / createController) is
// injected, so this module has no submodule-coupled imports and is unit-testable without
// the editor, the bridge, or the solver. app.js supplies the real collaborators.

export const EDITOR_SOLVE_EXPORT_FAILED = 'EDITOR_SOLVE_EXPORT_FAILED';

// Mount a read-only solve panel that solves the CURRENT editor document.
//   { root, documentState, exportProject, createPanel, createController, endpoint?, fetchImpl?, labels? }
// Returns { ok:true, project, controller, panel } when the document exported to a solvable
// project, or { ok:false, error_code, error, diagnostics, panel:null } when it could not
// (read-only: no panel is mounted, nothing is mutated).
export function mountEditorSolvePanel({
  root,
  documentState,
  exportProject,
  createPanel,
  createController,
  endpoint,
  fetchImpl,
  labels = {},
} = {}) {
  if (!root || typeof root.appendChild !== 'function') {
    throw new TypeError('root element is required');
  }
  if (
    typeof exportProject !== 'function'
    || typeof createPanel !== 'function'
    || typeof createController !== 'function'
  ) {
    throw new TypeError('exportProject, createPanel and createController are required');
  }

  const exported = exportProject(documentState);
  if (!exported || exported.ok !== true || !exported.value) {
    return {
      ok: false,
      error_code: exported?.error_code ?? EDITOR_SOLVE_EXPORT_FAILED,
      error: exported?.error ?? 'could not export the current document to a solvable project',
      diagnostics: exported?.diagnostics ?? [],
      panel: null,
    };
  }

  const project = exported.value;
  const controllerOptions = {};
  if (endpoint !== undefined) controllerOptions.endpoint = endpoint;
  if (fetchImpl !== undefined) controllerOptions.fetchImpl = fetchImpl;
  const controller = createController(controllerOptions);
  const panel = createPanel({ root, project, controller, labels });
  return { ok: true, project, controller, panel };
}
