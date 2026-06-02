// Export row for the editor's CURRENT solve: Export Project JSON · Copy Repro Bundle · Export
// CADGF Preview — the same exports the demo offers, built from the SAME shared builders
// (solve_exports.js) and the SAME copy/download IO (solve_export_io.js), so there is one export
// path across the product. Pure composition: every collaborator is injected (getProject /
// getSolveState / getShareUrl / copyText / downloadJson), so it is unit-testable without the
// editor, the bridge, or a real DOM.
//
// `getProject` returns the project the panel actually solves (the mount-time snapshot), so the
// repro bundle's `project` always matches its `solve_result` (no live-vs-solved mismatch). Repro
// and Preview need a solve to have run; Project JSON is always available. app.js calls `update()`
// on each controller state so the disabled states track the latest solve.

import {
  projectJsonText,
  reproBundleJsonText,
  solveEvidenceText,
  filenameForProject,
  filenameForPreviewDocument,
  extractImportedProject,
} from '../../shared/solve_exports.js';
import { copyText as defaultCopyText, downloadJson as defaultDownloadJson, readJsonFile as defaultReadJsonFile } from '../../shared/solve_export_io.js';

function appendEl(parent, tag, { className, text, type } = {}) {
  const el = parent.ownerDocument.createElement(tag);
  if (className) el.className = className;
  if (type) el.type = type;
  if (text !== undefined) el.textContent = text;
  parent.appendChild(el);
  return el;
}

export function mountEditorSolveExports({
  root,
  document: doc,
  getProject,
  getSolveState,
  getShareUrl,
  copyText = defaultCopyText,
  downloadJson = defaultDownloadJson,
  readJsonFile = defaultReadJsonFile,
  loadProject,
  onImported,
  labels = {},
} = {}) {
  if (!root || typeof root.appendChild !== 'function' || !root.ownerDocument) {
    throw new TypeError('root element (with ownerDocument) is required');
  }
  const document = doc ?? root.ownerDocument;
  const projectOf = () => { const ex = getProject?.(); return ex && typeof ex === 'object' ? ex : null; };
  const stateOf = () => getSolveState?.() ?? {};

  const container = appendEl(root, 'section', { className: 'vemcad-solve-exports' });
  appendEl(container, 'h3', { text: labels.title ?? 'Import / Export' });

  const importButton = appendEl(container, 'button', { type: 'button', text: 'Import Project JSON', className: 'vemcad-solve-exports__import' });
  const projectButton = appendEl(container, 'button', { type: 'button', text: 'Export Project JSON', className: 'vemcad-solve-exports__project' });
  const reproButton = appendEl(container, 'button', { type: 'button', text: 'Copy Repro Bundle', className: 'vemcad-solve-exports__repro' });
  const previewButton = appendEl(container, 'button', { type: 'button', text: 'Export CADGF Preview', className: 'vemcad-solve-exports__preview' });
  const status = appendEl(container, 'p', { className: 'vemcad-solve-exports__status', text: '' });
  status.setAttribute?.('aria-live', 'polite');
  const setStatus = (text) => { status.textContent = text; };

  // Import Project JSON (or a Repro Bundle — unwrapped). SAFETY: only a SUCCESSFUL load triggers
  // onImported (the re-mount). A bad file / wrong shape / failed load / user-cancel leaves the
  // current document + panel intact and just reports an error — a bad file must never cost the
  // user their working session. onImported replaces this row, so nothing touches it afterward.
  importButton.addEventListener('click', async () => {
    if (typeof loadProject !== 'function') { setStatus('Import is unavailable.'); return; }
    setStatus('Importing…');
    let parsed;
    try {
      parsed = await readJsonFile({ document });
    } catch (err) {
      setStatus(err?.message === 'project import canceled' ? 'Import canceled.' : 'Could not read the file.');
      return;
    }
    const project = extractImportedProject(parsed);
    if (!project) { setStatus('Not a VemCAD project or repro bundle.'); return; }
    let result;
    try {
      result = await loadProject(project);
    } catch (err) {
      setStatus(`Import failed: ${err?.message ?? String(err)}`);
      return;
    }
    if (!result || result.ok !== true) {
      setStatus(result?.error ? `Import failed: ${result.error}` : 'Import failed.');
      return;
    }
    onImported?.();
  });

  // Project JSON — always available; exports the project the panel solves.
  projectButton.addEventListener('click', async () => {
    const project = projectOf();
    if (!project) { setStatus('No project to export.'); return; }
    try {
      await downloadJson({ document, value: project, filename: filenameForProject(project) });
      setStatus('Project JSON downloaded.');
    } catch { setStatus('Export project unavailable.'); }
  });

  // Repro Bundle — project INPUT + solve OUTPUT + evidence; needs a solve (a conflict counts).
  reproButton.addEventListener('click', async () => {
    const state = stateOf();
    if (!state.envelope) { setStatus('Run solve to copy a repro bundle.'); return; }
    const text = reproBundleJsonText({
      project: projectOf(),
      solveEnvelope: state.envelope,
      solveEvidence: solveEvidenceText(state.envelope, state.summary),
      demoKey: 'editor',
      shareUrl: getShareUrl?.() ?? null,
    });
    try { await copyText({ document, text }); setStatus('Repro bundle copied.'); }
    catch { setStatus('Copy repro bundle unavailable.'); }
  });

  // CADGF Preview — the solved preview document; needs a successful solve.
  previewButton.addEventListener('click', async () => {
    const previewDocument = stateOf().previewDocument;
    if (!previewDocument) { setStatus('Run solve to export a preview.'); return; }
    try {
      await downloadJson({ document, value: previewDocument, filename: filenameForPreviewDocument(previewDocument) });
      setStatus('CADGF preview downloaded.');
    } catch { setStatus('Export preview unavailable.'); }
  });

  // Reflect the latest solve: repro needs an envelope, preview needs a preview document.
  const update = () => {
    const state = stateOf();
    reproButton.disabled = !state.envelope;
    previewButton.disabled = !state.previewDocument;
  };
  update();

  return {
    root: container,
    importButton,
    projectButton,
    reproButton,
    previewButton,
    status,
    update,
    destroy() { container.remove?.(); },
  };
}
