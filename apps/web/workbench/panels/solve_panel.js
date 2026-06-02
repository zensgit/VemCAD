import { createSolveWorkbenchController } from '../solver/solve_workbench.js';

const STATUS_LABELS = {
  idle: 'Ready',
  solving: 'Solving',
  solved: 'Solved',
  blocked: 'Blocked',
  failed: 'Failed',
};

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function appendText(parent, tag, text, className = '') {
  const el = parent.ownerDocument.createElement(tag);
  if (className) el.className = className;
  el.textContent = text;
  parent.appendChild(el);
  return el;
}

function summaryLine(summary) {
  if (!summary) return 'No solve has run yet.';
  const parts = [];
  if (summary.structuralState) parts.push(`state=${summary.structuralState}`);
  if (summary.dofEstimate !== null) parts.push(`dof=${summary.dofEstimate}`);
  if (summary.conflictGroupCount !== null) parts.push(`conflicts=${summary.conflictGroupCount}`);
  if (summary.redundantConstraintEstimate !== null) parts.push(`redundant=${summary.redundantConstraintEstimate}`);
  if (summary.iterations !== null) parts.push(`iters=${summary.iterations}`);
  if (summary.finalError !== null) parts.push(`err=${summary.finalError}`);
  return parts.length ? parts.join(' · ') : 'Solve completed without structural analysis.';
}

// One actionable line for an over-constrained solve: WHICH entities conflict + the solver's hint
// on what to do. Empty string when there is no conflict, so a clean solve shows nothing here.
function conflictLine(summary) {
  const ids = Array.isArray(summary?.conflictEntityIds) ? summary.conflictEntityIds : [];
  if (ids.length === 0) return '';
  const advice = summary?.conflictAdvice ? ` — ${summary.conflictAdvice}` : '';
  return `Conflicting: ${ids.join(', ')}${advice}`;
}

function renderDiagnostics(list, container) {
  clear(container);
  if (!list.length) {
    appendText(container, 'li', 'No diagnostics.');
    return;
  }
  for (const diagnostic of list) {
    const code = diagnostic?.code ? `${diagnostic.code}: ` : '';
    appendText(container, 'li', `${code}${diagnostic?.message ?? JSON.stringify(diagnostic)}`);
  }
}

function renderPreviewMeta(previewDocument, container) {
  clear(container);
  if (!previewDocument) {
    container.textContent = 'No CADGF preview document.';
    return;
  }
  const entityCount = Array.isArray(previewDocument.entities) ? previewDocument.entities.length : 0;
  container.textContent = `CADGF schema ${previewDocument.schema_version ?? '?'} · ${entityCount} entities`;
}

export function createSolveWorkbenchPanel({
  root,
  project,
  controller = createSolveWorkbenchController(),
  labels = {},
} = {}) {
  if (!root || typeof root.appendChild !== 'function') {
    throw new TypeError('root element is required');
  }
  if (!project || typeof project !== 'object') {
    throw new TypeError('project is required');
  }

  clear(root);
  root.classList?.add?.('vemcad-solve-panel');

  const title = appendText(root, 'h2', labels.title ?? 'Solver');
  const status = appendText(root, 'p', '', 'vemcad-solve-panel__status');
  const details = appendText(root, 'p', '', 'vemcad-solve-panel__details');
  const preview = appendText(root, 'p', '', 'vemcad-solve-panel__preview');
  const advice = appendText(root, 'p', '', 'vemcad-solve-panel__advice');
  const runButton = root.ownerDocument.createElement('button');
  runButton.type = 'button';
  runButton.textContent = labels.solve ?? 'Solve';
  root.appendChild(runButton);
  appendText(root, 'h3', labels.diagnostics ?? 'Diagnostics');
  const diagnostics = root.ownerDocument.createElement('ul');
  diagnostics.className = 'vemcad-solve-panel__diagnostics';
  root.appendChild(diagnostics);

  const unsubscribe = controller.subscribe((state) => {
    const label = STATUS_LABELS[state.status] ?? state.status;
    status.textContent = label;
    status.dataset.status = state.status;
    details.textContent = summaryLine(state.summary);
    const conflict = conflictLine(state.summary);
    advice.textContent = conflict;
    advice.dataset.hasConflict = conflict ? 'true' : 'false';
    renderPreviewMeta(state.previewDocument, preview);
    renderDiagnostics(state.diagnostics ?? [], diagnostics);
    runButton.disabled = state.status === 'solving';
  });

  runButton.addEventListener('click', () => {
    controller.solve(project).catch((err) => {
      // Controller errors are normally converted to state, but keep the panel
      // resilient if a caller-supplied implementation throws unexpectedly.
      status.textContent = STATUS_LABELS.failed;
      status.dataset.status = 'failed';
      details.textContent = err?.message ?? String(err);
      runButton.disabled = false;
    });
  });

  return {
    root,
    title,
    runButton,
    getState: () => controller.getState(),
    solve: () => controller.solve(project),
    destroy: unsubscribe,
  };
}
