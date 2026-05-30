import { createSolveWorkbenchPanel } from '../panels/solve_panel.js';
import { createSolveDemoFetch } from './demo_fetch.js';
import { SOLVE_WORKBENCH_DEMOS } from './demo_projects.js';
import { renderCadgfPreviewCanvas } from './preview_canvas.js';
import { createSolveWorkbenchController } from './solve_workbench.js';

const STYLE_ID = 'vemcad-solve-demo-styles';
const DEMO_ORDER = ['solvableLine', 'conflictingLine', 'passthroughUnsupported'];

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
  demos = SOLVE_WORKBENCH_DEMOS,
  fetchImpl = createSolveDemoFetch(),
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
  append(meta, 'h2', { text: 'Preview' });
  const previewRoot = append(meta, 'div', { className: 'vemcad-solve-demo__visual' });

  let selectedKey = null;
  let panelHandle = null;
  let controller = null;
  let previewUnsubscribe = null;

  async function select(key) {
    if (!demos[key]) {
      throw new Error(`unknown solve demo: ${key}`);
    }
    panelHandle?.destroy?.();
    previewUnsubscribe?.();
    selectedKey = key;
    setActiveButton(buttons, key);
    const project = demos[key];
    projectSummary.textContent = summarizeProject(project);
    controller = createSolveWorkbenchController({ fetchImpl });
    previewUnsubscribe = controller.subscribe((state) => {
      renderCadgfPreviewCanvas({ root: previewRoot, cadgfDocument: state.previewDocument });
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

  await select(DEMO_ORDER[0]);
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
