export function resolveVemcadAppBridge() {
  const bridge = globalThis.window?.__vemcadApp ?? null;
  if (!bridge || typeof bridge.switchToEditor !== 'function') {
    return null;
  }
  return bridge;
}

export async function switchToEditor(documentJson, { bridge = resolveVemcadAppBridge() } = {}) {
  if (!bridge) {
    return false;
  }
  await bridge.switchToEditor(documentJson);
  return true;
}
