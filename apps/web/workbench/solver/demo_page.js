import { createSolveWorkbenchPanel } from '../panels/solve_panel.js';
import { createSolveDemoFetch } from './demo_fetch.js';
import { SOLVE_WORKBENCH_DEMOS } from './demo_projects.js';
import { createSolveWorkbenchController } from './solve_workbench.js';

const DEMO_ORDER = ['solvableLine', 'conflictingLine', 'passthroughUnsupported'];

const DEMO_LABELS = Object.freeze({
  solvableLine: 'Solvable',
  conflictingLine: 'Conflict',
  passthroughUnsupported: 'Passthrough',
});

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
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
  demos = SOLVE_WORKBENCH_DEMOS,
  fetchImpl = createSolveDemoFetch(),
} = {}) {
  if (!root || typeof root.appendChild !== 'function') {
    throw new TypeError('root element is required');
  }

  clear(root);
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

  let selectedKey = null;
  let panelHandle = null;
  let controller = null;

  async function select(key) {
    if (!demos[key]) {
      throw new Error(`unknown solve demo: ${key}`);
    }
    panelHandle?.destroy?.();
    selectedKey = key;
    setActiveButton(buttons, key);
    const project = demos[key];
    projectSummary.textContent = summarizeProject(project);
    controller = createSolveWorkbenchController({ fetchImpl });
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
    },
  };
}
