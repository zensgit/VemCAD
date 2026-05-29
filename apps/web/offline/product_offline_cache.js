export const PRODUCT_OFFLINE_MESSAGE_TYPE = 'VEMCAD_CACHE_PRODUCT_OFFLINE_ASSETS';
export const DEFAULT_PRODUCT_OFFLINE_TIMEOUT_MS = 5000;

function getGlobalScope(scope = globalThis) {
  return scope?.window || scope;
}

function readManifestFromScope(scope) {
  const target = getGlobalScope(scope);
  const manifest = target?.__VEMCAD_PRODUCT_OFFLINE_MANIFEST || null;
  if (manifest && Array.isArray(manifest.assets)) {
    return {
      manifest,
      assets: manifest.assets,
    };
  }

  const assets = target?.__VEMCAD_PRODUCT_OFFLINE_ASSETS || [];
  return {
    manifest: null,
    assets: Array.isArray(assets) ? assets : [],
  };
}

function normalizeAssetList(assets) {
  return [...new Set(
    (Array.isArray(assets) ? assets : [])
      .map((asset) => String(asset || '').trim())
      .filter(Boolean)
  )];
}

function writeProductOfflineState(scope, state) {
  const target = getGlobalScope(scope);
  if (target) {
    target.__vemcadProductOffline = state;
  }
  return state;
}

export function readProductOfflineManifest({ globalScope = globalThis } = {}) {
  const { manifest, assets } = readManifestFromScope(globalScope);
  const normalizedAssets = normalizeAssetList(assets);
  return {
    manifest,
    assets: normalizedAssets,
    assetCount: normalizedAssets.length,
  };
}

export async function cacheProductOfflineAssets({
  assets = null,
  globalScope = globalThis,
  serviceWorkerContainer = globalScope?.navigator?.serviceWorker,
  MessageChannelCtor = globalScope?.MessageChannel,
  setTimeoutFn = globalScope?.setTimeout,
  clearTimeoutFn = globalScope?.clearTimeout,
  timeoutMs = DEFAULT_PRODUCT_OFFLINE_TIMEOUT_MS,
  messageType = PRODUCT_OFFLINE_MESSAGE_TYPE,
} = {}) {
  const manifestInfo = readProductOfflineManifest({ globalScope });
  const assetList = normalizeAssetList(assets || manifestInfo.assets);
  if (assetList.length === 0) {
    return writeProductOfflineState(globalScope, {
      ok: true,
      skipped: true,
      reason: 'no-product-offline-assets',
      assetCount: 0,
    });
  }

  if (!serviceWorkerContainer || !MessageChannelCtor) {
    return writeProductOfflineState(globalScope, {
      ok: true,
      skipped: true,
      reason: 'service-worker-unavailable',
      assetCount: assetList.length,
    });
  }

  try {
    const registration = await serviceWorkerContainer.ready;
    const worker = serviceWorkerContainer.controller || registration?.active;
    if (!worker || typeof worker.postMessage !== 'function') {
      return writeProductOfflineState(globalScope, {
        ok: true,
        skipped: true,
        reason: 'service-worker-controller-unavailable',
        assetCount: assetList.length,
      });
    }

    const reply = await new Promise((resolve, reject) => {
      const channel = new MessageChannelCtor();
      const timer = typeof setTimeoutFn === 'function'
        ? setTimeoutFn(() => reject(new Error('product offline cache message timeout')), timeoutMs)
        : null;
      channel.port1.onmessage = (event) => {
        if (timer && typeof clearTimeoutFn === 'function') {
          clearTimeoutFn(timer);
        }
        resolve(event.data);
      };
      worker.postMessage({ type: messageType, assets: assetList }, [channel.port2]);
    });

    return writeProductOfflineState(globalScope, {
      ok: reply?.ok === true,
      skipped: false,
      assetCount: assetList.length,
      manifestVersion: manifestInfo.manifest?.manifestVersion || '',
      assetManifestHash: manifestInfo.manifest?.assetManifestHash || '',
      ...reply,
    });
  } catch (error) {
    return writeProductOfflineState(globalScope, {
      ok: false,
      skipped: false,
      assetCount: assetList.length,
      error: String(error?.message || error),
    });
  }
}

export function scheduleProductOfflineCaching({
  globalScope = globalThis,
  cacheImpl = cacheProductOfflineAssets,
  enqueue = globalScope?.queueMicrotask,
  ...cacheOptions
} = {}) {
  const run = () => cacheImpl({ globalScope, ...cacheOptions });
  writeProductOfflineState(globalScope, {
    ok: true,
    scheduled: true,
  });

  if (typeof enqueue === 'function') {
    return new Promise((resolve) => {
      enqueue(() => resolve(Promise.resolve().then(run)));
    });
  }
  return Promise.resolve().then(run);
}
