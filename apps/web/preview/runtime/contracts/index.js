export const PREVIEW_COMPAT_QUERY_PARAMS = Object.freeze([
  'manifest',
  'gltf',
  'mode',
]);

export const PREVIEW_GLOBAL_CONTRACTS = Object.freeze([
  'window.__vemcadApp.switchToEditor(documentJson)',
  'document fallback',
]);

export { resolveVemcadAppBridge, switchToEditor } from '../editor_handoff.js';
export { bootstrapLegacyPreviewRuntime } from '../preview_bootstrap.js';
