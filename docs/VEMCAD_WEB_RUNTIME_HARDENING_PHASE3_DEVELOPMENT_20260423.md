# VemCAD Web Runtime Hardening Phase 3 Development

日期：2026-04-23

## 目标

继续执行 Phase 2 的后续建议：

1. 把重复的 `--url-prefix` helper 抽成共享 utility。
2. 增加 packaged runtime smoke，验证真实启动 URL 来自 `cad_resources/tools/web_viewer/index.html`。
3. 评估 service worker 是否直接消费 `product-offline-assets.js`。

## 并行执行情况

本轮先并行拆成四个任务：

- URL helper 抽取第一组脚本。
- URL helper 抽取第二组脚本。
- packaged runtime smoke 方案分析。
- service worker product offline 接入风险分析。

子任务连接中断后，主线程接管并完成实现、验证和文档。没有回退既有脏改动。

## 实现内容

### 1. 新增 shared smoke URL utility

新增：

- `deps/cadgamefusion/tools/web_viewer/scripts/smoke_url_utils.js`

导出：

- `trimSlashes()`
- `prefixRelativePath()`
- `prefixAbsolutePath()`

职责：

- 统一处理 repo-root server 下的 URL prefix。
- 保持空 prefix 时的 legacy deps-root 行为。
- 避免每个 smoke 重复维护相同 helper。

### 2. 重构已支持 `--url-prefix` 的 smoke

改为 import shared utility：

- `editor_classic_leader_smoke.js`
- `editor_current_layer_smoke.js`
- `editor_insert_attribute_smoke.js`
- `editor_insert_group_smoke.js`
- `editor_layer_session_smoke.js`
- `editor_mleader_smoke.js`
- `editor_selection_summary_smoke.js`
- `editor_source_group_smoke.js`
- `editor_space_layout_smoke.js`
- `editor_table_smoke.js`
- `solver_action_panel_smoke.js`

行为保持不变：

- 页面 URL 仍通过 `prefixRelativePath('tools/web_viewer/index.html', urlPrefix)` 生成。
- 默认 `/tools/...` fixture 仍通过 `prefixAbsolutePath(...)` 改写。
- summary 仍记录 `url_prefix` 和改写后的 fixture。

### 3. 新增 packaged viewer path smoke

新增：

- `deps/cadgamefusion/tools/web_viewer/scripts/desktop_packaged_viewer_path_smoke.js`

职责：

- 查找或按需打包 packaged VemCAD app。
- 使用 Playwright Electron 启动 packaged binary。
- 读取首个窗口 `window.location.href`。
- 验证实际 URL 包含 `/Resources/cad_resources/tools/web_viewer/index.html`。
- 验证 `window.vemcadDesktop` 存在。
- 验证 bootstrap 走 `legacy-fallback`，且 fallback reason 是 `desktop-runtime-product-bootstrap-disabled`。

### 4. service worker product offline 决策

本轮未让 `service-worker.js` 直接消费 `product-offline-assets.js`。

原因：

- 当前 service worker cache smoke 仍明确验证 `/apps/web/app.js` 不被 precache。
- 接入 product offline asset list 需要同时调整 cache version、install 策略、offline smoke 断言。
- 用户 artifact、manifest、glTF 等运行时产物不应混入固定 app shell 清单。

本轮保留 Phase 2 的生成式 graph 作为下一步输入，继续用验证证明 graph 完整可生成。

## 受影响文件

- [deps/cadgamefusion/tools/web_viewer/scripts/smoke_url_utils.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/smoke_url_utils.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/desktop_packaged_viewer_path_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/desktop_packaged_viewer_path_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_classic_leader_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_classic_leader_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_current_layer_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_current_layer_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_attribute_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_attribute_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_group_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_group_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_layer_session_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_layer_session_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_mleader_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_mleader_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_source_group_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_source_group_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_space_layout_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_space_layout_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js)

## 后续建议

1. 为 service worker product offline 接入设计单独版本和 smoke，不要直接修改现有 v3 shell cache。
2. 把 `desktop_packaged_viewer_path_smoke.js` 纳入 packaged smoke 文档或 CI 的轻量阶段。
3. 继续全量跑其余 `--url-prefix` browser smoke，扩大 repo-root coverage。
