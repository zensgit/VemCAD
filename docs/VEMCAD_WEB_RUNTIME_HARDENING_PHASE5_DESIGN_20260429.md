# VemCAD Web Runtime Hardening Phase 5 Design

日期：2026-04-29

## 目标

继续执行 Phase 4 的后续建议：

1. 增加 product runtime helper，让产品层在 bootstrap 后可选触发 product offline cache。
2. 为 product offline import graph 增加 manifest version、asset hash 和内容 digest，后续可据此判断 cache 版本是否需要升级。
3. 补齐 solver/default preview smoke 所需的本地 `build/` artifacts，并把仍未通过的 artifact 质量问题记录清楚。

## 并行处理

本轮并行拆成两个只读任务：

- `apps/web` 单测注入方式分析：确认使用 `node:test`、动态 import query 隔离模块状态，并通过依赖注入模拟 service worker。
- smoke artifact 缺失分析：确认 solver JSON 和 Step186 preview artifacts 都有本地生成入口，缺失的是 `build/` 产物。

主线程完成 runtime helper、graph hash、单测、browser smoke 和 artifact 生成验证。

## 设计方案

### 1. Product Offline Runtime Helper

新增：

- `apps/web/offline/product_offline_cache.js`

职责：

- 读取 `window.__VEMCAD_PRODUCT_OFFLINE_MANIFEST.assets`。
- 兼容旧的 `window.__VEMCAD_PRODUCT_OFFLINE_ASSETS`。
- 对 asset 去重、trim、过滤空值。
- 通过 `VEMCAD_CACHE_PRODUCT_OFFLINE_ASSETS` message 发给 active service worker。
- 将结果写入 `window.__vemcadProductOffline`，便于 smoke 或调试读取。
- service worker 不可用、无 active worker、无 assets 时返回 `skipped` 状态，不抛出到产品启动链路。

### 2. Bootstrap 非阻塞接入

更新：

- `apps/web/app.js`

行为：

- product preview 启动完成后调用 `scheduleProductOfflineCaching({ mode: "preview" })`。
- editor workspace 启动完成后调用 `scheduleProductOfflineCaching({ mode: "editor" })`。
- `triggerProductOfflineCaching()` 捕获同步异常和 Promise rejection，确保 offline cache 失败不阻塞 preview/editor。
- `bootstrapVemcadWebApp()` 增加 `scheduleOfflineCaching` 和 `ensureWorkspaceBootstrappedImpl` 注入点，便于单测隔离真实 service worker 和 workspace 导入。

### 3. Product Offline Manifest

更新：

- `deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js`

输出增强：

- `offline_manifest_schema_version`
- `offline_manifest_version = "product-offline-manifest-v1"`
- `asset_manifest_hash_algorithm = "sha256"`
- `asset_manifest_hash`
- `asset_digests`

hash 规则：

- 每个 asset 先计算文件内容 SHA-256。
- manifest hash 基于 entries、asset paths、asset digests 和 external specifiers 生成。
- 因此产品层代码内容变化会改变 `asset_manifest_hash`，不是只对路径列表敏感。

生成的 `product-offline-assets.js` 同时暴露：

- `self.__VEMCAD_PRODUCT_OFFLINE_MANIFEST`
- `self.__VEMCAD_PRODUCT_OFFLINE_ASSETS`

保留 `__VEMCAD_PRODUCT_OFFLINE_ASSETS` 是为了兼容 Phase 4 helper/smoke 的资产列表读取方式。

### 4. Service Worker 边界

本轮不改变 Phase 4 的 cache 生命周期：

- shell cache 仍是 `cadgf-web-viewer-v3`。
- product offline cache 仍是 `cadgf-product-offline-v1`。
- product assets 仍不进入 install 阶段 shell precache。
- product offline 仍通过显式 message 触发。

`service_worker_product_offline_smoke.js` 增加对 manifest version 和 64 位 SHA-256 hash 的断言。

### 5. Smoke Artifact 策略

补齐：

- `deps/cadgamefusion/build/solver_action_panels_ui_ranked_probe.out.json`
- Step186 默认 preview manifests 所需的 `build/step186_*` 目录。

边界：

- Step186 默认校验模式仍失败在 `mleader_json_only`。
- 使用 `--skip-validate` 可生成 17 个 artifact 目录，并让默认 preview smoke 不再因为 manifest 文件缺失而失败。
- 默认 preview smoke 后续仍需要解决 TinyGLTF/glTF 输出缺失和 status expectation 不一致问题。

## 受影响文件

- [apps/web/app.js](/Users/chouhua/Downloads/Github/VemCAD/apps/web/app.js)
- [apps/web/offline/product_offline_cache.js](/Users/chouhua/Downloads/Github/VemCAD/apps/web/offline/product_offline_cache.js)
- [apps/web/tests/product_offline_cache.test.js](/Users/chouhua/Downloads/Github/VemCAD/apps/web/tests/product_offline_cache.test.js)
- [apps/web/tests/web_bootstrap_entry.test.js](/Users/chouhua/Downloads/Github/VemCAD/apps/web/tests/web_bootstrap_entry.test.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js)

## 后续建议

1. 修复 Step186 `mleader_json_only` 校验失败：`source_type LEADER` 应满足 `proxy_kind='leader'`。
2. 恢复 TinyGLTF/glTF 输出或调整 default preview smoke 的 JSON fallback status expectation。
3. 基于 `asset_manifest_hash` 制定 `cadgf-product-offline-v2` 升级策略，不要和 shell cache 版本绑定。
