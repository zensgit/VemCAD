# VemCAD Web Runtime Hardening Phase 4 Development

日期：2026-04-23

## 目标

继续执行 Phase 3 的后续建议：

1. 为 product offline assets 设计独立缓存和 smoke，不把 product assets 混入现有 `cadgf-web-viewer-v3` shell cache。
2. 继续扩大 repo-root `--url-prefix deps/cadgamefusion` browser smoke 覆盖。
3. 保持 desktop packaged path smoke 和既有 product bootstrap 方案不回退。

## 并行执行情况

本轮并行拆成两个只读分析任务，主线程同步实现和验证：

- service worker/product offline 方案分析：确认低风险策略是保留 `cadgf-web-viewer-v3` shell cache，新增独立 `cadgf-product-offline-v1`，由显式 message 触发。
- repo-root smoke 盘点：确认 12 个 Playwright smoke 支持 `--url-prefix`，其中 solver 默认输入缺失，preview 默认 cases 依赖部分当前不存在的 build artifact。

主线程完成 service worker 改造、正向 product offline smoke、cache-version 回归 smoke、repo-root editor smoke 和 product preview smoke。

## 实现内容

### 1. 独立 product offline cache

更新：

- `deps/cadgamefusion/tools/web_viewer/service-worker.js`

新增：

- `PRODUCT_OFFLINE_CACHE_NAME = "cadgf-product-offline-v1"`
- `PRODUCT_OFFLINE_MESSAGE_TYPE = "VEMCAD_CACHE_PRODUCT_OFFLINE_ASSETS"`
- `ACTIVE_CACHE_NAMES = new Set([CACHE_NAME, PRODUCT_OFFLINE_CACHE_NAME])`

行为：

- `cadgf-web-viewer-v3` 的 shell `ASSETS` 保持只包含 web viewer shell。
- product assets 不在 install 阶段 precache，避免 product graph 或远端资源失败影响 shell 离线能力。
- product offline 只能通过 `VEMCAD_CACHE_PRODUCT_OFFLINE_ASSETS` message 显式触发。
- service worker 对传入 asset 去重、校验同源、缓存到 `cadgf-product-offline-v1`。
- activate 阶段保留当前 shell cache 和当前 product offline cache，清理其它旧 cache。

### 2. cache-version smoke 保持默认边界

更新：

- `deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js`

新增断言：

- 读取 `PRODUCT_OFFLINE_CACHE_NAME`。
- 验证默认安装/升级后不会出现 `cadgf-product-offline-v1`。
- 继续验证 shell cache 不包含 `/apps/web/app.js`。
- 继续验证未显式触发 product offline 时，离线读取 `/apps/web/app.js` 必须失败。

### 3. 新增 product offline 正向 smoke

新增：

- `deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js`

验证链路：

1. 调用 `product_bootstrap_import_graph.js` 生成 product bootstrap import graph。
2. 读取 graph 的 `asset_paths`。
3. 启动 repo-root 静态服务。
4. 注册并控制 `tools/web_viewer/service-worker.js`。
5. 通过 `VEMCAD_CACHE_PRODUCT_OFFLINE_ASSETS` message 发送 147 个 asset。
6. 验证 `cadgf-product-offline-v1` 被创建且缓存数量一致。
7. 切换 browser offline，验证 `/apps/web/app.js`、workspace bootstrap 和 shell `./app.js` 均可离线读取。

### 4. repo-root smoke 覆盖

本轮用 repo-root 静态服务和 `--url-prefix deps/cadgamefusion` 补跑：

- `editor_table_smoke.js`
- `editor_mleader_smoke.js`
- `editor_classic_leader_smoke.js`
- `editor_space_layout_smoke.js`
- `editor_selection_summary_smoke.js`
- `editor_current_layer_smoke.js`
- `editor_layer_session_smoke.js`
- `editor_source_group_smoke.js`
- `editor_insert_group_smoke.js`
- `editor_insert_attribute_smoke.js`
- `preview_provenance_smoke.js` 的 product-specific case

未纳入通过项：

- `solver_action_panel_smoke.js`：默认 `/build/solver_action_panels_ui_ranked_probe.out.json` 当前不存在。
- `preview_provenance_smoke.js` 默认 29 cases：首个默认 case 依赖的 `deps/cadgamefusion/build/step186_origin_blocks/manifest.json` 当前不存在，改跑已有 artifact 的 product-specific case。

## 受影响文件

- [deps/cadgamefusion/tools/web_viewer/service-worker.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/service-worker.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js)

## 后续建议

1. 增加 product runtime helper，由 product app 在 manifest 准备好后可选触发 `VEMCAD_CACHE_PRODUCT_OFFLINE_ASSETS`，失败只记录状态，不阻塞 preview/editor。
2. 为 `product_bootstrap_import_graph.js` 增加 manifest hash 或版本字段，便于判断 `cadgf-product-offline-v1` 何时需要升到 v2。
3. 补齐 solver smoke 默认 JSON 和 preview 默认 build artifacts 后，再跑完整 12 个 `--url-prefix` browser smoke。
