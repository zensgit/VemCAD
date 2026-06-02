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
// CONFLICT HIGHLIGHT: when a solve reports conflicts (an over-constrained/unsatisfied solve,
// so envelope.ok === false), the offending editor entities — resolved server-side from the
// solver's conflicting variable keys via the adapter pointMap, surfaced as
// `summary.conflictEntityIds` — are highlighted through the injected `highlightEntities`
// (app.js routes it to the editor selection). Independent of the auto-apply success gate.
//
// Degrades to READ-ONLY when `applyUpdates` / `highlightEntities` are not injected (solve +
// display only, no mutation), so the module stays useful and testable without the editor.
//
// Pure composition: every collaborator (exportProject / createPanel / createController /
// applyUpdates / highlightEntities) is injected, so this module has no submodule-coupled
// imports and is unit-testable without the editor, the bridge, or the solver. app.js wires them.

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
  highlightEntities,
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

  // React to solve results. Two independent effects, both keyed by object-identity so a notify
  // replay never re-fires within one solve. Guarded on subscribe so a bare/test controller (no
  // subscribe) stays valid.
  //   1. Auto-apply (SUCCESS only): on envelope.ok + a solved view, write the solved geometry back
  //      via applyUpdates (read-only if not injected); guard on the evaluatedView object.
  //   2. Conflict highlight (ANY outcome): conflicts come back as a FAILED/unsatisfied solve
  //      (envelope.ok === false), so this must NOT reuse the auto-apply gate. Keyed off the
  //      curated summary.conflictEntityIds (resolved server-side); highlights only when there are
  //      conflicts (never clears the user's selection on a clean solve); guard on the summary.
  let lastAppliedView = null;
  let lastHighlightSummary = null;
  let unsubscribe = () => {};
  if (typeof controller.subscribe === 'function') {
    unsubscribe = controller.subscribe((state) => {
      const evaluatedView = state?.envelope?.ok === true ? state.envelope?.value?.evaluatedView : null;
      if (evaluatedView && evaluatedView !== lastAppliedView) {
        lastAppliedView = evaluatedView;
        if (typeof applyUpdates === 'function') {
          const updates = translateEvaluatedViewToUpdates(evaluatedView);
          if (updates.length > 0) applyUpdates({ updates });
        }
      }

      const summary = state?.summary ?? null;
      if (summary && summary !== lastHighlightSummary) {
        lastHighlightSummary = summary;
        const conflictIds = Array.isArray(summary.conflictEntityIds) ? summary.conflictEntityIds : [];
        if (conflictIds.length > 0 && typeof highlightEntities === 'function') {
          highlightEntities(conflictIds);
        }
      }
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
