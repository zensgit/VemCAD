export const WORKBENCH_STABLE_EXPORTS = Object.freeze([
  'registerCadCommands(commandBus, context)',
  'computeRotatePayload(center, referencePoint, targetPoint)',
  'computeScalePayload(center, referencePoint, targetPoint)',
  'bootstrapCadWorkspace({ params })',
]);

export const WORKBENCH_GLOBAL_CONTRACTS = Object.freeze([
  'window.__vemcadApp.switchToEditor(documentJson)',
  'window.__cadDebug',
]);

export { bootstrapCadWorkspace } from '../bootstrap/workspace_bootstrap.js';
export {
  computeRotatePayload,
  computeScalePayload,
  registerCadCommands,
} from '../commands/registry.js';
