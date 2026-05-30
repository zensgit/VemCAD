export const WORKBENCH_STABLE_EXPORTS = Object.freeze([
  'registerCadCommands(commandBus, context)',
  'computeRotatePayload(center, referencePoint, targetPoint)',
  'computeScalePayload(center, referencePoint, targetPoint)',
  'bootstrapCadWorkspace({ params })',
  'createSolveWorkbenchController({ endpoint, fetchImpl })',
  'createSolveWorkbenchPanel({ root, project, controller })',
  'mountSolveWorkbenchDemo({ root, appBridge })',
]);

export const WORKBENCH_GLOBAL_CONTRACTS = Object.freeze([
  'window.__vemcadApp.switchToEditor(documentJson)',
  'window.__vemcadApp.mountSolvePanel(root, { project, controller })',
  'window.__cadDebug',
]);

export { bootstrapCadWorkspace } from '../bootstrap/workspace_bootstrap.js';
export {
  computeRotatePayload,
  computeScalePayload,
  registerCadCommands,
} from '../commands/registry.js';
export {
  DEFAULT_SOLVE_ENDPOINT,
  createSolveWorkbenchController,
  deriveCadgfPreviewDocument,
  solveRuntimeProject,
  summarizeSolveEnvelope,
} from '../solver/solve_workbench.js';
export { createSolveDemoFetch } from '../solver/demo_fetch.js';
export { SOLVE_WORKBENCH_DEMOS } from '../solver/demo_projects.js';
export { mountSolveWorkbenchDemo } from '../solver/demo_page.js';
export { createSolveWorkbenchPanel } from '../panels/solve_panel.js';
