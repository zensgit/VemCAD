import { createSolveWorkbenchPanel } from '../panels/solve_panel.js';
import { normalizeProjectModel } from '../../../runtime/project/index.js';
import { createSolveDemoFetch } from './demo_fetch.js';
import { SOLVE_WORKBENCH_DEMOS } from './demo_projects.js';
import { renderCadgfPreviewCanvas } from './preview_canvas.js';
import { createSolveWorkbenchController } from './solve_workbench.js';

const STYLE_ID = 'vemcad-solve-demo-styles';
const DEMO_ORDER = ['solvableLine', 'conflictingLine', 'passthroughUnsupported'];
const DEFAULT_DEMO_ID = DEMO_ORDER[0];
const IMPORTED_DEMO_ID = 'importedProject';

const DEMO_LABELS = Object.freeze({
  solvableLine: 'Solvable',
  conflictingLine: 'Conflict',
  passthroughUnsupported: 'Passthrough',
});

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function ensureSolveDemoStyles(document) {
  if (!document?.head || typeof document.createElement !== 'function') return;
  if (typeof document.querySelector === 'function' && document.querySelector(`#${STYLE_ID}`)) return;

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    .vemcad-solve-demo{width:min(1120px,calc(100vw - 32px));margin:0 auto;padding:28px 0;color:#1d2433;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .vemcad-solve-demo *{box-sizing:border-box}
    .vemcad-solve-demo__header h1{margin:0 0 18px;font-size:28px;font-weight:720;letter-spacing:0}
    .vemcad-solve-demo__nav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
    .vemcad-solve-demo__tab,.vemcad-solve-panel button{min-height:38px;border:1px solid #c9d3e5;border-radius:6px;background:#fff;color:#1f2937;padding:8px 12px;font:inherit;cursor:pointer}
    .vemcad-solve-demo__tab[data-active="true"],.vemcad-solve-panel button{background:#114d7a;border-color:#114d7a;color:#fff}
    .vemcad-solve-panel button:disabled{cursor:progress;opacity:.65}
    .vemcad-solve-demo__content{display:grid;grid-template-columns:minmax(0,1fr) minmax(240px,320px);gap:16px;align-items:start}
    .vemcad-solve-demo__panel,.vemcad-solve-demo__meta{background:#fff;border:1px solid #d8e0ee;border-radius:8px;padding:18px;box-shadow:0 8px 22px rgb(15 23 42 / .06)}
    .vemcad-solve-panel h2,.vemcad-solve-demo__meta h2{margin:0 0 12px;font-size:18px;letter-spacing:0}
    .vemcad-solve-panel h3{margin:18px 0 8px;font-size:15px;letter-spacing:0}
    .vemcad-solve-panel__status{display:inline-flex;min-height:30px;align-items:center;border-radius:6px;padding:4px 10px;margin:0 0 10px;background:#eef6ed;color:#255a2e;font-weight:650}
    .vemcad-solve-panel__status[data-status="blocked"],.vemcad-solve-panel__status[data-status="failed"]{background:#fff3df;color:#8a4b00}
    .vemcad-solve-panel__status[data-status="solving"]{background:#eaf1ff;color:#1f4f91}
    .vemcad-solve-panel__details,.vemcad-solve-panel__preview,.vemcad-solve-demo__summary{margin:0 0 12px;color:#3d485c;line-height:1.45}
    .vemcad-solve-demo__export,.vemcad-solve-demo__project-copy,.vemcad-solve-demo__import,.vemcad-solve-demo__solve-copy,.vemcad-solve-demo__solve-export,.vemcad-solve-demo__preview-export{min-height:34px;margin:0 0 6px;border:1px solid #c9d3e5;border-radius:6px;background:#fff;color:#1f2937;padding:6px 10px;font:inherit;cursor:pointer}
    .vemcad-solve-demo__export:disabled,.vemcad-solve-demo__project-copy:disabled,.vemcad-solve-demo__import:disabled,.vemcad-solve-demo__solve-copy:disabled,.vemcad-solve-demo__solve-export:disabled,.vemcad-solve-demo__preview-export:disabled{cursor:progress;opacity:.65}
    .vemcad-solve-demo__export-status,.vemcad-solve-demo__project-copy-status,.vemcad-solve-demo__import-status,.vemcad-solve-demo__solve-copy-status,.vemcad-solve-demo__solve-export-status,.vemcad-solve-demo__preview-export-status{min-height:22px;margin:0 0 12px;color:#5b6679;line-height:1.45}
    .vemcad-solve-demo__share{display:block;margin:0 0 8px;color:#114d7a;line-height:1.35;overflow-wrap:anywhere}
    .vemcad-solve-demo__copy{min-height:34px;border:1px solid #c9d3e5;border-radius:6px;background:#fff;color:#1f2937;padding:6px 10px;font:inherit;cursor:pointer}
    .vemcad-solve-demo__copy:disabled{cursor:progress;opacity:.65}
    .vemcad-solve-demo__copy-status{min-height:22px;margin:0 0 12px;color:#5b6679;line-height:1.45}
    .vemcad-solve-demo__solve-summary{margin:0 0 6px;color:#3d485c;line-height:1.45}
    .vemcad-solve-demo__diagnostic-count{margin:0 0 10px;color:#5b6679;line-height:1.45}
    .vemcad-solve-demo__solve-evidence{min-height:38px;margin:0 0 12px;padding:8px;border:1px solid #e1e7f2;border-radius:6px;background:#f8fafc;color:#334155;font:12px/1.45 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;white-space:pre-wrap;overflow-wrap:anywhere}
    .vemcad-solve-demo__visual{min-height:180px;border:1px solid #e1e7f2;border-radius:6px;background:#f8fafc;overflow:hidden}
    .vemcad-preview-canvas{display:block;width:100%;height:180px}
    .vemcad-preview-canvas__line{stroke:#114d7a;stroke-width:.22;stroke-linecap:round;vector-effect:non-scaling-stroke}
    .vemcad-preview-canvas__point{fill:#d14f3f;stroke:#fff;stroke-width:.08;vector-effect:non-scaling-stroke}
    .vemcad-preview-canvas__circle{fill:none;stroke:#547f37;stroke-width:.18;vector-effect:non-scaling-stroke}
    .vemcad-preview-canvas__empty{display:flex;min-height:180px;margin:0;align-items:center;justify-content:center;color:#6b7280}
    .vemcad-solve-panel__diagnostics{margin:0;padding-left:20px;color:#354258;line-height:1.5}
    @media (max-width:760px){.vemcad-solve-demo{width:min(100vw - 20px,1120px);padding:18px 0}.vemcad-solve-demo__content{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);
}

function append(parent, tag, options = {}) {
  const el = parent.ownerDocument.createElement(tag);
  if (options.className) el.className = options.className;
  if (options.text !== undefined) el.textContent = options.text;
  if (options.type) el.type = options.type;
  parent.appendChild(el);
  return el;
}

function setActiveButton(buttons, selectedKey) {
  for (const [key, button] of Object.entries(buttons)) {
    const active = key === selectedKey;
    button.disabled = active;
    button.dataset.active = active ? 'true' : 'false';
    if (active) button.setAttribute?.('aria-current', 'true');
    else button.removeAttribute?.('aria-current');
  }
}

function summarizeProject(project) {
  return [
    `id=${project.project.id}`,
    `entities=${project.entities.length}`,
    `constraints=${project.constraints.length}`,
  ].join(' | ');
}

function summarizeSolveState(state) {
  if (!state?.summary) return 'No solve has run yet.';
  const parts = [];
  if (state.summary.structuralState) parts.push(`state=${state.summary.structuralState}`);
  if (state.summary.dofEstimate !== null) parts.push(`dof=${state.summary.dofEstimate}`);
  if (state.summary.conflictGroupCount !== null) parts.push(`conflicts=${state.summary.conflictGroupCount}`);
  if (state.summary.iterations !== null) parts.push(`iters=${state.summary.iterations}`);
  if (state.summary.finalError !== null) parts.push(`err=${state.summary.finalError}`);
  return parts.length ? parts.join(' | ') : `status=${state.status}`;
}

function diagnosticCountText(state) {
  const count = Array.isArray(state?.diagnostics) ? state.diagnostics.length : 0;
  return `diagnostics=${count}`;
}

function solveEvidenceText(envelope, summary) {
  if (!envelope || !summary) return 'No solve result yet.';
  const lines = [
    `ok=${envelope.ok === true ? 'true' : 'false'}`,
    Number.isFinite(summary.httpStatus) ? `http=${summary.httpStatus}` : null,
    summary.status ? `status=${summary.status}` : null,
    summary.errorCode ? `error=${summary.errorCode}` : null,
    summary.structuralState ? `state=${summary.structuralState}` : null,
    Number.isFinite(summary.dofEstimate) ? `dof=${summary.dofEstimate}` : null,
    Number.isFinite(summary.conflictGroupCount) ? `conflicts=${summary.conflictGroupCount}` : null,
    Number.isFinite(summary.redundantConstraintEstimate) ? `redundant=${summary.redundantConstraintEstimate}` : null,
    Number.isFinite(summary.iterations) ? `iters=${summary.iterations}` : null,
    Number.isFinite(summary.finalError) ? `err=${summary.finalError}` : null,
    Number.isFinite(summary.diagnosticCount) ? `diagnostics=${summary.diagnosticCount}` : null,
  ].filter(Boolean);
  return lines.join('\n') || 'Solve result has no summary.';
}

function demoUrlFor(root, key) {
  const href = root.ownerDocument?.defaultView?.location?.href
    ?? globalThis.window?.location?.href
    ?? '';
  if (!href) return `?mode=solve-demo&demo=${encodeURIComponent(key)}`;
  try {
    const url = new URL(href);
    url.searchParams.set('mode', 'solve-demo');
    url.searchParams.set('demo', key);
    return url.href;
  } catch {
    return `?mode=solve-demo&demo=${encodeURIComponent(key)}`;
  }
}

async function defaultCopyText(text, root) {
  const doc = root.ownerDocument;
  const clipboard = root.ownerDocument?.defaultView?.navigator?.clipboard ?? globalThis.navigator?.clipboard;
  if (clipboard && typeof clipboard.writeText === 'function') {
    try {
      await clipboard.writeText(text);
      return;
    } catch {
      // Fall through to the textarea path for browsers that expose the API
      // but deny it in local or embedded contexts.
    }
  }
  if (doc?.body && typeof doc.createElement === 'function' && typeof doc.execCommand === 'function') {
    const textarea = doc.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    doc.body.appendChild(textarea);
    textarea.select();
    const copied = doc.execCommand('copy');
    doc.body.removeChild(textarea);
    if (copied) return;
  }
  throw new Error('clipboard is unavailable');
}

function filenameForProject(project, key) {
  const raw = project?.project?.id || key || 'vemcad-project';
  const safe = String(raw).replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'vemcad-project';
  return `${safe}.vemcad-project.json`;
}

function projectJsonText(project) {
  return `${JSON.stringify(project, null, 2)}\n`;
}

function filenameForPreviewDocument(document, key) {
  const raw = document?.document_id || key || 'vemcad-preview';
  const safe = String(raw).replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'vemcad-preview';
  return `${safe}.cadgf-document.json`;
}

function filenameForSolveResult(envelope, project, key) {
  const raw = project?.project?.id || envelope?.value?.evaluatedView?.project?.id || key || 'vemcad-solve-result';
  const safe = String(raw).replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'vemcad-solve-result';
  return `${safe}.solve-result.json`;
}

async function downloadJson(value, filename, root) {
  const doc = root.ownerDocument;
  const win = doc?.defaultView ?? globalThis.window;
  if (!doc?.body || typeof doc.createElement !== 'function' || !win?.Blob || !win?.URL?.createObjectURL) {
    throw new Error('download is unavailable');
  }
  const blob = new win.Blob([`${JSON.stringify(value, null, 2)}\n`], {
    type: 'application/json',
  });
  const url = win.URL.createObjectURL(blob);
  const link = doc.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noreferrer';
  doc.body.appendChild(link);
  try {
    link.click();
  } finally {
    doc.body.removeChild(link);
    win.setTimeout?.(() => win.URL.revokeObjectURL(url), 0);
  }
}

async function defaultExportProjectJson(project, key, root) {
  await downloadJson(project, filenameForProject(project, key), root);
}

async function defaultExportPreviewJson(previewDocument, key, root) {
  await downloadJson(previewDocument, filenameForPreviewDocument(previewDocument, key), root);
}

async function defaultExportSolveResultJson(envelope, project, key, root) {
  await downloadJson(envelope, filenameForSolveResult(envelope, project, key), root);
}

async function defaultImportProjectJson(root) {
  const doc = root.ownerDocument;
  if (!doc?.body || typeof doc.createElement !== 'function') {
    throw new Error('file picker is unavailable');
  }
  return new Promise((resolve, reject) => {
    const input = doc.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';
    input.style.position = 'fixed';
    input.style.opacity = '0';
    input.style.pointerEvents = 'none';
    let settled = false;

    function cleanup() {
      if (input.parentNode) input.parentNode.removeChild(input);
    }

    function finish(fn, value) {
      if (settled) return;
      settled = true;
      cleanup();
      fn(value);
    }

    input.addEventListener('change', async () => {
      try {
        const file = input.files?.[0];
        if (!file || typeof file.text !== 'function') {
          throw new Error('no project file selected');
        }
        finish(resolve, JSON.parse(await file.text()));
      } catch (err) {
        finish(reject, err);
      }
    });
    input.addEventListener?.('cancel', () => {
      finish(reject, new Error('project import canceled'));
    });
    doc.body.appendChild(input);
    input.click();
  });
}

function resolveInitialDemo(initialDemo, demos) {
  if (initialDemo && Object.prototype.hasOwnProperty.call(demos, initialDemo)) {
    return initialDemo;
  }
  return DEFAULT_DEMO_ID;
}

async function mountPanel({ appBridge, panelRoot, project, controller }) {
  if (appBridge && typeof appBridge.mountSolvePanel === 'function') {
    return appBridge.mountSolvePanel(panelRoot, {
      project,
      controller,
      labels: { title: project.project.name, solve: 'Solve' },
    });
  }
  return createSolveWorkbenchPanel({
    root: panelRoot,
    project,
    controller,
    labels: { title: project.project.name, solve: 'Solve' },
  });
}

export async function mountSolveWorkbenchDemo({
  root,
  appBridge = null,
  autoSolve = false,
  initialDemo = DEFAULT_DEMO_ID,
  demos = SOLVE_WORKBENCH_DEMOS,
  fetchImpl = createSolveDemoFetch(),
  copyText = defaultCopyText,
  exportProjectJson = defaultExportProjectJson,
  exportPreviewJson = defaultExportPreviewJson,
  exportSolveResultJson = defaultExportSolveResultJson,
  importProjectJson = defaultImportProjectJson,
} = {}) {
  if (!root || typeof root.appendChild !== 'function') {
    throw new TypeError('root element is required');
  }

  clear(root);
  ensureSolveDemoStyles(root.ownerDocument);
  root.classList?.add?.('vemcad-solve-demo');

  const header = append(root, 'header', { className: 'vemcad-solve-demo__header' });
  append(header, 'h1', { text: 'VemCAD Solve Workbench' });

  const nav = append(root, 'nav', { className: 'vemcad-solve-demo__nav' });
  nav.setAttribute?.('aria-label', 'Solve demos');
  const buttons = {};
  for (const key of DEMO_ORDER) {
    const button = append(nav, 'button', {
      type: 'button',
      text: DEMO_LABELS[key] ?? key,
      className: 'vemcad-solve-demo__tab',
    });
    button.dataset.demoId = key;
    buttons[key] = button;
  }

  const content = append(root, 'main', { className: 'vemcad-solve-demo__content' });
  const panelRoot = append(content, 'section', { className: 'vemcad-solve-demo__panel' });
  const meta = append(content, 'aside', { className: 'vemcad-solve-demo__meta' });
  append(meta, 'h2', { text: 'Project' });
  const projectSummary = append(meta, 'p', { className: 'vemcad-solve-demo__summary' });
  const exportButton = append(meta, 'button', {
    type: 'button',
    text: 'Export Project JSON',
    className: 'vemcad-solve-demo__export',
  });
  const exportStatus = append(meta, 'p', {
    className: 'vemcad-solve-demo__export-status',
    text: 'Ready to export project.',
  });
  exportStatus.setAttribute?.('aria-live', 'polite');
  const projectCopyButton = append(meta, 'button', {
    type: 'button',
    text: 'Copy Project JSON',
    className: 'vemcad-solve-demo__project-copy',
  });
  const projectCopyStatus = append(meta, 'p', {
    className: 'vemcad-solve-demo__project-copy-status',
    text: 'Ready to copy project.',
  });
  projectCopyStatus.setAttribute?.('aria-live', 'polite');
  const importButton = append(meta, 'button', {
    type: 'button',
    text: 'Import Project JSON',
    className: 'vemcad-solve-demo__import',
  });
  const importStatus = append(meta, 'p', {
    className: 'vemcad-solve-demo__import-status',
    text: 'Ready to import project.',
  });
  importStatus.setAttribute?.('aria-live', 'polite');
  append(meta, 'h2', { text: 'Share' });
  const shareLink = append(meta, 'a', { className: 'vemcad-solve-demo__share' });
  shareLink.target = '_blank';
  shareLink.rel = 'noreferrer';
  const copyButton = append(meta, 'button', {
    type: 'button',
    text: 'Copy link',
    className: 'vemcad-solve-demo__copy',
  });
  const copyStatus = append(meta, 'p', {
    className: 'vemcad-solve-demo__copy-status',
    text: 'Ready to copy link.',
  });
  copyStatus.setAttribute?.('aria-live', 'polite');
  append(meta, 'h2', { text: 'Solve summary' });
  const solveSummary = append(meta, 'p', { className: 'vemcad-solve-demo__solve-summary' });
  const diagnosticsSummary = append(meta, 'p', { className: 'vemcad-solve-demo__diagnostic-count' });
  const solveEvidence = append(meta, 'pre', {
    className: 'vemcad-solve-demo__solve-evidence',
    text: 'No solve result yet.',
  });
  const solveCopyButton = append(meta, 'button', {
    type: 'button',
    text: 'Copy Solve Evidence',
    className: 'vemcad-solve-demo__solve-copy',
  });
  const solveCopyStatus = append(meta, 'p', {
    className: 'vemcad-solve-demo__solve-copy-status',
    text: 'Run solve to copy evidence.',
  });
  solveCopyStatus.setAttribute?.('aria-live', 'polite');
  const solveExportButton = append(meta, 'button', {
    type: 'button',
    text: 'Export Solve Result JSON',
    className: 'vemcad-solve-demo__solve-export',
  });
  const solveExportStatus = append(meta, 'p', {
    className: 'vemcad-solve-demo__solve-export-status',
    text: 'Run solve to export result.',
  });
  solveExportStatus.setAttribute?.('aria-live', 'polite');
  append(meta, 'h2', { text: 'Preview' });
  const previewExportButton = append(meta, 'button', {
    type: 'button',
    text: 'Export CADGF Preview JSON',
    className: 'vemcad-solve-demo__preview-export',
  });
  const previewExportStatus = append(meta, 'p', {
    className: 'vemcad-solve-demo__preview-export-status',
    text: 'Run solve to export CADGF preview.',
  });
  previewExportStatus.setAttribute?.('aria-live', 'polite');
  const previewRoot = append(meta, 'div', { className: 'vemcad-solve-demo__visual' });

  let selectedKey = null;
  let panelHandle = null;
  let controller = null;
  let previewUnsubscribe = null;
  let currentShareUrl = '';
  let currentProject = null;
  let currentSolveEnvelope = null;
  let currentSolveEvidenceText = '';
  let currentPreviewDocument = null;
  const projectsByKey = { ...demos };

  function ensureImportedButton() {
    if (buttons[IMPORTED_DEMO_ID]) return buttons[IMPORTED_DEMO_ID];
    const button = append(nav, 'button', {
      type: 'button',
      text: 'Imported',
      className: 'vemcad-solve-demo__tab',
    });
    button.dataset.demoId = IMPORTED_DEMO_ID;
    button.addEventListener('click', () => {
      select(IMPORTED_DEMO_ID).catch((err) => {
        projectSummary.textContent = err?.message ?? String(err);
      });
    });
    buttons[IMPORTED_DEMO_ID] = button;
    return button;
  }

  function updateShare(key) {
    if (key === IMPORTED_DEMO_ID) {
      currentShareUrl = '';
      shareLink.removeAttribute?.('href');
      shareLink.href = '';
      shareLink.textContent = 'Imported project is local. Export JSON to share.';
      copyButton.disabled = true;
      copyStatus.textContent = 'No share link for imported project.';
      return;
    }
    const demoUrl = demoUrlFor(root, key);
    currentShareUrl = demoUrl;
    shareLink.href = demoUrl;
    shareLink.setAttribute?.('href', demoUrl);
    shareLink.textContent = demoUrl;
    copyButton.disabled = false;
    copyStatus.textContent = 'Ready to copy link.';
  }

  async function select(key) {
    if (!projectsByKey[key]) {
      throw new Error(`unknown solve demo: ${key}`);
    }
    panelHandle?.destroy?.();
    previewUnsubscribe?.();
    selectedKey = key;
    setActiveButton(buttons, key);
    const project = projectsByKey[key];
    currentProject = project;
    currentSolveEnvelope = null;
    currentSolveEvidenceText = '';
    currentPreviewDocument = null;
    projectSummary.textContent = summarizeProject(project);
    exportStatus.textContent = 'Ready to export project.';
    projectCopyButton.disabled = false;
    projectCopyStatus.textContent = 'Ready to copy project.';
    importStatus.textContent = 'Ready to import project.';
    solveCopyButton.disabled = true;
    solveCopyStatus.textContent = 'Run solve to copy evidence.';
    solveExportButton.disabled = true;
    solveExportStatus.textContent = 'Run solve to export result.';
    solveEvidence.textContent = 'No solve result yet.';
    previewExportButton.disabled = true;
    previewExportStatus.textContent = 'Run solve to export CADGF preview.';
    updateShare(key);
    controller = createSolveWorkbenchController({ fetchImpl });
    previewUnsubscribe = controller.subscribe((state) => {
      currentSolveEnvelope = state.envelope ?? null;
      currentPreviewDocument = state.previewDocument ?? null;
      renderCadgfPreviewCanvas({ root: previewRoot, cadgfDocument: state.previewDocument });
      solveSummary.textContent = summarizeSolveState(state);
      diagnosticsSummary.textContent = diagnosticCountText(state);
      const evidenceText = solveEvidenceText(currentSolveEnvelope, state.summary);
      currentSolveEvidenceText = currentSolveEnvelope ? evidenceText : '';
      solveEvidence.textContent = evidenceText;
      solveCopyButton.disabled = !currentSolveEvidenceText;
      solveCopyStatus.textContent = currentSolveEvidenceText
        ? 'Ready to copy solve evidence.'
        : state.status === 'solving'
          ? 'Solving before evidence copy.'
          : 'Run solve to copy evidence.';
      solveExportButton.disabled = !currentSolveEnvelope;
      solveExportStatus.textContent = currentSolveEnvelope
        ? 'Ready to export solve result.'
        : state.status === 'solving'
          ? 'Solving before export.'
          : 'Run solve to export result.';
      previewExportButton.disabled = !currentPreviewDocument;
      previewExportStatus.textContent = currentPreviewDocument
        ? 'Ready to export CADGF preview.'
        : state.status === 'idle'
          ? 'Run solve to export CADGF preview.'
          : 'No CADGF preview to export.';
    });
    panelHandle = await mountPanel({ appBridge, panelRoot, project, controller });
    return panelHandle;
  }

  for (const [key, button] of Object.entries(buttons)) {
    button.addEventListener('click', () => {
      select(key).catch((err) => {
        projectSummary.textContent = err?.message ?? String(err);
      });
    });
  }

  copyButton.addEventListener('click', async () => {
    if (!currentShareUrl) {
      copyStatus.textContent = 'No share link for imported project.';
      return;
    }
    copyButton.disabled = true;
    try {
      await copyText(currentShareUrl, root);
      copyStatus.textContent = 'Link copied.';
    } catch {
      copyStatus.textContent = 'Copy unavailable.';
    } finally {
      copyButton.disabled = false;
    }
  });

  exportButton.addEventListener('click', async () => {
    exportButton.disabled = true;
    try {
      await exportProjectJson(currentProject, selectedKey, root);
      exportStatus.textContent = 'Project JSON exported.';
    } catch {
      exportStatus.textContent = 'Export unavailable.';
    } finally {
      exportButton.disabled = false;
    }
  });

  projectCopyButton.addEventListener('click', async () => {
    if (!currentProject) {
      projectCopyStatus.textContent = 'No project to copy.';
      return;
    }
    projectCopyButton.disabled = true;
    try {
      await copyText(projectJsonText(currentProject), root);
      projectCopyStatus.textContent = 'Project JSON copied.';
    } catch {
      projectCopyStatus.textContent = 'Copy project unavailable.';
    } finally {
      projectCopyButton.disabled = false;
    }
  });

  importButton.addEventListener('click', async () => {
    importButton.disabled = true;
    try {
      const rawProject = await importProjectJson(root);
      const normalized = normalizeProjectModel(rawProject);
      if (!normalized.ok) {
        throw new Error(normalized.error ?? normalized.error_code ?? 'invalid project');
      }
      projectsByKey[IMPORTED_DEMO_ID] = normalized.value;
      ensureImportedButton();
      await select(IMPORTED_DEMO_ID);
      importStatus.textContent = 'Project JSON imported.';
      if (autoSolve) {
        try {
          await panelHandle.solve();
        } catch {
          // Import has already succeeded. The panel owns solve failure state,
          // so do not re-label a valid file import as an import failure.
        }
      }
    } catch {
      importStatus.textContent = 'Import failed.';
    } finally {
      importButton.disabled = false;
    }
  });

  solveCopyButton.addEventListener('click', async () => {
    if (!currentSolveEvidenceText) {
      solveCopyStatus.textContent = 'No solve evidence to copy.';
      return;
    }
    solveCopyButton.disabled = true;
    try {
      await copyText(currentSolveEvidenceText, root);
      solveCopyStatus.textContent = 'Solve evidence copied.';
    } catch {
      solveCopyStatus.textContent = 'Copy evidence unavailable.';
    } finally {
      solveCopyButton.disabled = false;
    }
  });

  solveExportButton.addEventListener('click', async () => {
    if (!currentSolveEnvelope) {
      solveExportStatus.textContent = 'No solve result to export.';
      return;
    }
    solveExportButton.disabled = true;
    try {
      await exportSolveResultJson(currentSolveEnvelope, currentProject, selectedKey, root);
      solveExportStatus.textContent = 'Solve result JSON exported.';
    } catch {
      solveExportStatus.textContent = 'Solve result export unavailable.';
    } finally {
      solveExportButton.disabled = false;
    }
  });

  previewExportButton.addEventListener('click', async () => {
    if (!currentPreviewDocument) {
      previewExportStatus.textContent = 'No CADGF preview to export.';
      return;
    }
    previewExportButton.disabled = true;
    try {
      await exportPreviewJson(currentPreviewDocument, selectedKey, root);
      previewExportStatus.textContent = 'CADGF preview JSON exported.';
    } catch {
      previewExportStatus.textContent = 'Preview export unavailable.';
    } finally {
      previewExportButton.disabled = false;
    }
  });

  await select(resolveInitialDemo(initialDemo, demos));
  if (autoSolve) {
    await panelHandle.solve();
  }

  return {
    root,
    buttons,
    get selectedKey() {
      return selectedKey;
    },
    getPanelState() {
      return panelHandle?.getState?.() ?? controller?.getState?.() ?? null;
    },
    async select(key) {
      return select(key);
    },
    async solve() {
      return panelHandle.solve();
    },
    destroy() {
      panelHandle?.destroy?.();
      previewUnsubscribe?.();
    },
  };
}
