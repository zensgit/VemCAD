// "Solve the current editor sketch" composition for editor mode — solves the
// current document and AUTO-APPLIES the solved geometry back into the editor.
//
// Wires the EXISTING product-layer pieces together WITHOUT modifying the solve panel,
// controller, or demo:
//   editor DocumentState --(runtime bridge export)--> VEMCAD-PROJECT --> solve panel + controller --> /solve
//   /solve envelope.value.evaluatedView --(translate)--> editor geometry patches --(applyUpdates)--> editor
//
// WRITEBACK model = auto-apply + native undo (the owner-chosen model): on a successful
// solve the solved geometry is translated into editor-native patches and applied through the
// injected `applyUpdates`. app.js routes `applyUpdates` to the editor's `entity.applyGeometry`
// command, which is undoable via the command bus (one native Ctrl-Z step). It is keyed by
// entity id — export coerces the editor's numeric id into the project id and import keeps it
// numeric, so `evaluatedView` entities come back keyed by the editor's own ids.
//
// Degrades to READ-ONLY when `applyUpdates` is not injected (solve + display only, no
// mutation), so the module stays useful and testable without the editor command bus.
//
// Pure composition: every collaborator (exportProject / createPanel / createController /
// applyUpdates) is injected, so this module has no submodule-coupled imports and is
// unit-testable without the editor, the bridge, or the solver. app.js supplies the real ones.

export const EDITOR_SOLVE_EXPORT_FAILED = 'EDITOR_SOLVE_EXPORT_FAILED';

function xyOf(pair) {
  return Array.isArray(pair) && Number.isFinite(pair[0]) && Number.isFinite(pair[1])
    ? { x: pair[0], y: pair[1] }
    : null;
}

// Translate a solved evaluatedView (VEMCAD-PROJECT entities, `kind`/`line|circle|arc`
// geometry) into editor geometry patches keyed by entity id ({ id, patch } with the editor's
// OWN field names: line->{start,end}, circle/arc->{center}). Only solved point-roles are
// written, so this never touches fillet/chamfer or other derived geometry. Limited to the
// kinds the editor actually models (it has no standalone `point` entity type) and the solver
// solves; entities without a finite id, an unhandled kind, or malformed coords are skipped —
// a partial solve writes back the parts it can and leaves the rest untouched.
export function translateEvaluatedViewToUpdates(evaluatedView) {
  const entities = Array.isArray(evaluatedView?.entities) ? evaluatedView.entities : [];
  const updates = [];
  for (const entity of entities) {
    if (!entity || !Number.isFinite(entity.id)) continue;
    let patch = null;
    if (entity.kind === 'line' && Array.isArray(entity.line) && entity.line.length === 2) {
      const start = xyOf(entity.line[0]);
      const end = xyOf(entity.line[1]);
      if (start && end) patch = { start, end };
    } else if (entity.kind === 'circle' && entity.circle) {
      const center = xyOf(entity.circle.c);
      if (center) patch = { center };
    } else if (entity.kind === 'arc' && entity.arc) {
      const center = xyOf(entity.arc.c);
      if (center) patch = { center };
    }
    if (patch) updates.push({ id: entity.id, patch });
  }
  return updates;
}

// Mount the solve panel for the CURRENT editor document and auto-apply solved geometry.
//   { root, documentState, exportProject, createPanel, createController,
//     applyUpdates?, endpoint?, fetchImpl?, labels? }
// Returns { ok:true, project, controller, panel, destroy } when the document exported to a
// solvable project, or { ok:false, error_code, error, diagnostics, panel:null } when it could
// not (no panel is mounted, nothing is mutated).
export function mountEditorSolvePanel({
  root,
  documentState,
  exportProject,
  createPanel,
  createController,
  applyUpdates,
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

  // Auto-apply: when a solve SUCCEEDS (envelope.ok + a solved view), write the solved geometry
  // back into the editor through the injected applyUpdates. The object-identity guard makes it
  // apply once per solved view (a fresh evaluatedView per solve), so a notify replay never
  // double-applies. Guarded on subscribe so a bare/test controller (no subscribe) stays valid;
  // guarded on applyUpdates so the panel degrades to read-only when no writeback is wired.
  let lastAppliedView = null;
  let unsubscribe = () => {};
  if (typeof controller.subscribe === 'function') {
    unsubscribe = controller.subscribe((state) => {
      const evaluatedView = state?.envelope?.ok === true ? state.envelope?.value?.evaluatedView : null;
      if (!evaluatedView || evaluatedView === lastAppliedView) return;
      lastAppliedView = evaluatedView;
      if (typeof applyUpdates !== 'function') return;
      const updates = translateEvaluatedViewToUpdates(evaluatedView);
      if (updates.length > 0) applyUpdates({ updates });
    });
  }

  return {
    ok: true,
    project,
    controller,
    panel,
    destroy() {
      unsubscribe();
      if (panel && typeof panel.destroy === 'function') panel.destroy();
    },
  };
}
