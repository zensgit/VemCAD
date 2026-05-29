# VemCAD Web Runtime Hardening Phase 2 Development

日期：2026-04-23

## 目标

继续执行上一轮 hardening 的后续建议：

1. 把剩余基础 editor browser smoke 收敛到 repo-root server 可运行模式。
2. 为 product offline 建立生成式 import graph 基础，避免手写大清单。
3. 执行 packaged build 验证，确认 staged viewer 资源进入 Electron 包。

## 并行开发拆分

本轮并行拆成三条线：

- Worker A：改造 `classic_leader`、`mleader`、`table`、`source_group` 四个 editor smoke。
- Worker B：改造 `current_layer`、`layer_session`、`space_layout`、`insert_group`、`insert_attribute` 五个 editor smoke。
- 主线程：实现 product bootstrap import graph 脚本，执行 repo-root browser smoke 与 packaged build 验证。

所有 worker 只改各自指定文件，未回退既有脏改动。

## 实现内容

### 1. 批量补齐 editor smoke `--url-prefix`

新增支持：

- `--url-prefix deps/cadgamefusion`

覆盖文件：

- `deps/cadgamefusion/tools/web_viewer/scripts/editor_classic_leader_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_current_layer_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_attribute_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_group_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_layer_session_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_mleader_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_source_group_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_space_layout_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js`

行为：

- 默认空 prefix，保持原 deps-root server 行为。
- 指定 `deps/cadgamefusion` 时，页面 URL 从 `tools/web_viewer/index.html` 改为 `deps/cadgamefusion/tools/web_viewer/index.html`。
- 默认 `/tools/web_viewer/tests/fixtures/...` fixture 同步改写为 `/deps/cadgamefusion/tools/web_viewer/tests/fixtures/...`。
- summary 记录 `url_prefix` 和改写后的 `fixture`。

### 2. 新增 product bootstrap import graph 生成脚本

新增：

- `deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js`

职责：

- 从 product bootstrap entry 出发扫描 literal relative `import` / `export from` / dynamic `import()`。
- 支持常量字符串 dynamic import。
- 支持 `new URL("./module.js", import.meta.url).toString()` 常量 dynamic import。
- 输出人读 JSON graph 和 service-worker 可消费的 JS asset module。

默认 entries：

- `apps/web/app.js`
- `apps/web/preview/runtime/preview_bootstrap.js`
- `apps/web/workbench/bootstrap/workspace_bootstrap.js`

输出文件：

- `summary.json`
- `product-offline-import-graph.json`
- `product-offline-assets.js`

本轮只生成清单，不让 `service-worker.js` 直接消费该清单。原因是 product offline 还需要单独设计缓存版本、artifact 策略和 smoke 断言。

### 3. packaged build 验证准备

沿用上一轮改动：

- `web_viewer_desktop/main.js` packaged 优先加载 staged `cad_resources/tools/web_viewer/index.html`。
- 旧 `Resources/web_viewer/index.html` 仍保留为 fallback。

本轮执行 `npm run pack`，确认 Electron 包中同时存在：

- staged viewer：`Resources/cad_resources/tools/web_viewer/index.html`
- fallback viewer：`Resources/web_viewer/index.html`
- staged live entry：`Resources/cad_resources/tools/web_viewer/app.js`
- staged legacy entry：`Resources/cad_resources/tools/web_viewer/legacy_app_bootstrap.js`

## 受影响文件

- [deps/cadgamefusion/tools/web_viewer/scripts/editor_classic_leader_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_classic_leader_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_current_layer_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_current_layer_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_attribute_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_attribute_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_group_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_group_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_layer_session_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_layer_session_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_mleader_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_mleader_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_source_group_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_source_group_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_space_layout_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_space_layout_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js)

## 后续建议

1. 把 `--url-prefix` helper 抽成共享 smoke utility，减少脚本间重复。
2. 下一轮让 service worker 选择性消费 `product-offline-assets.js`，但必须同步更新 cache smoke。
3. 增加 packaged app runtime smoke，验证实际启动 URL 来自 `cad_resources/tools/web_viewer/index.html`，而不只是文件存在。
