import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..', '..', '..');
const moduleUrl = pathToFileURL(path.join(repoRoot, 'apps/web/offline/product_offline_cache.js')).href;

function makeMessageChannel() {
  const port1 = { onmessage: null };
  const port2 = {
    postMessage(data) {
      port1.onmessage?.({ data });
    },
  };
  return { port1, port2 };
}

test('readProductOfflineManifest reads generated manifest assets', async () => {
  const offlineModule = await import(`${moduleUrl}?read-manifest`);
  const globalScope = {
    __VEMCAD_PRODUCT_OFFLINE_MANIFEST: {
      manifestVersion: 'product-offline-manifest-v1',
      assetManifestHash: 'a'.repeat(64),
      assets: ['/apps/web/app.js', '/apps/web/app.js', '/apps/web/workbench/bootstrap/workspace_bootstrap.js'],
    },
  };

  const result = offlineModule.readProductOfflineManifest({ globalScope });

  assert.equal(result.assetCount, 2);
  assert.deepEqual(result.assets, [
    '/apps/web/app.js',
    '/apps/web/workbench/bootstrap/workspace_bootstrap.js',
  ]);
});

test('readProductOfflineManifest falls back to legacy assets global', async () => {
  const offlineModule = await import(`${moduleUrl}?read-legacy-assets`);
  const globalScope = {
    __VEMCAD_PRODUCT_OFFLINE_ASSETS: ['/apps/web/app.js', '', ' /apps/web/app.js '],
  };

  const result = offlineModule.readProductOfflineManifest({ globalScope });

  assert.equal(result.manifest, null);
  assert.equal(result.assetCount, 1);
  assert.deepEqual(result.assets, ['/apps/web/app.js']);
});

test('cacheProductOfflineAssets posts assets to active service worker', async () => {
  const offlineModule = await import(`${moduleUrl}?cache-assets`);
  const messages = [];
  const worker = {
    postMessage(message, ports) {
      messages.push(message);
      ports[0].postMessage({
        ok: true,
        cacheName: 'cadgf-product-offline-v1',
        cachedCount: message.assets.length,
      });
    },
  };
  const globalScope = {
    __VEMCAD_PRODUCT_OFFLINE_MANIFEST: {
      manifestVersion: 'product-offline-manifest-v1',
      assetManifestHash: 'b'.repeat(64),
      assets: ['/apps/web/app.js', '/apps/web/app.js'],
    },
    MessageChannel: makeMessageChannel,
    setTimeout,
    clearTimeout,
  };

  const result = await offlineModule.cacheProductOfflineAssets({
    globalScope,
    serviceWorkerContainer: {
      ready: Promise.resolve({ active: worker }),
      controller: null,
    },
  });

  assert.equal(result.ok, true);
  assert.equal(result.skipped, false);
  assert.equal(result.cachedCount, 1);
  assert.equal(result.manifestVersion, 'product-offline-manifest-v1');
  assert.equal(result.assetManifestHash, 'b'.repeat(64));
  assert.equal(globalScope.__vemcadProductOffline.ok, true);
  assert.deepEqual(messages, [{
    type: 'VEMCAD_CACHE_PRODUCT_OFFLINE_ASSETS',
    assets: ['/apps/web/app.js'],
  }]);
});

test('cacheProductOfflineAssets skips cleanly without service worker plumbing', async () => {
  const offlineModule = await import(`${moduleUrl}?skip-service-worker`);
  const globalScope = {
    __VEMCAD_PRODUCT_OFFLINE_ASSETS: ['/apps/web/app.js'],
  };

  const result = await offlineModule.cacheProductOfflineAssets({
    globalScope,
    serviceWorkerContainer: null,
    MessageChannelCtor: null,
  });

  assert.equal(result.ok, true);
  assert.equal(result.skipped, true);
  assert.equal(result.reason, 'service-worker-unavailable');
  assert.equal(result.assetCount, 1);
});

test('cacheProductOfflineAssets skips when no active worker can receive messages', async () => {
  const offlineModule = await import(`${moduleUrl}?skip-controller`);
  const globalScope = {
    __VEMCAD_PRODUCT_OFFLINE_ASSETS: ['/apps/web/app.js'],
    MessageChannel: makeMessageChannel,
  };

  const result = await offlineModule.cacheProductOfflineAssets({
    globalScope,
    serviceWorkerContainer: {
      ready: Promise.resolve({ active: null }),
      controller: null,
    },
  });

  assert.equal(result.ok, true);
  assert.equal(result.skipped, true);
  assert.equal(result.reason, 'service-worker-controller-unavailable');
});

test('cacheProductOfflineAssets returns error state when worker reply times out', async () => {
  const offlineModule = await import(`${moduleUrl}?timeout`);
  const worker = {
    postMessage() {},
  };
  const globalScope = {
    __VEMCAD_PRODUCT_OFFLINE_ASSETS: ['/apps/web/app.js'],
    MessageChannel: makeMessageChannel,
    setTimeout(callback) {
      callback();
      return 1;
    },
    clearTimeout() {},
  };

  const result = await offlineModule.cacheProductOfflineAssets({
    globalScope,
    serviceWorkerContainer: {
      ready: Promise.resolve({ active: worker }),
      controller: null,
    },
  });

  assert.equal(result.ok, false);
  assert.equal(result.skipped, false);
  assert.match(result.error, /timeout/);
});

test('cacheProductOfflineAssets skips cleanly when assets are absent', async () => {
  const offlineModule = await import(`${moduleUrl}?skip-assets`);
  const globalScope = {};

  const result = await offlineModule.cacheProductOfflineAssets({ globalScope });

  assert.equal(result.ok, true);
  assert.equal(result.skipped, true);
  assert.equal(result.reason, 'no-product-offline-assets');
  assert.equal(globalScope.__vemcadProductOffline.reason, 'no-product-offline-assets');
});

test('scheduleProductOfflineCaching records scheduled state and runs asynchronously', async () => {
  const offlineModule = await import(`${moduleUrl}?schedule`);
  const globalScope = {
    queueMicrotask(callback) {
      callback();
    },
  };
  const calls = [];

  const result = await offlineModule.scheduleProductOfflineCaching({
    globalScope,
    cacheImpl: async (options) => {
      calls.push(options);
      return { ok: true, cachedCount: 2 };
    },
  });

  assert.equal(globalScope.__vemcadProductOffline.scheduled, true);
  assert.deepEqual(result, { ok: true, cachedCount: 2 });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].globalScope, globalScope);
});

test('scheduleProductOfflineCaching propagates cacheImpl rejection to caller', async () => {
  const offlineModule = await import(`${moduleUrl}?schedule-reject`);
  const globalScope = {
    queueMicrotask(callback) {
      callback();
    },
  };

  await assert.rejects(
    () => offlineModule.scheduleProductOfflineCaching({
      globalScope,
      cacheImpl: async () => {
        throw new Error('cache failed');
      },
    }),
    /cache failed/
  );
  assert.equal(globalScope.__vemcadProductOffline.scheduled, true);
});
