const LEGACY_PREVIEW_RUNTIME_MODULE =
  '../../../../deps/cadgamefusion/tools/web_viewer/preview_app.js';

export async function bootstrapLegacyPreviewRuntime() {
  return import(LEGACY_PREVIEW_RUNTIME_MODULE);
}
