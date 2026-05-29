# VemCAD Web Runtime Hardening Phase 2 Verification

日期：2026-04-23

## 验证目标

确认本轮改动满足 5 个条件：

1. 所有新增/修改 JS 可解析。
2. 批量改造的 editor smoke 保持默认行为，并支持 repo-root `--url-prefix`。
3. product bootstrap import graph 能完整解析当前静态闭包，且无 missing import。
4. repo-root browser smoke 至少覆盖两个新改造脚本。
5. packaged build 包含 staged viewer 与旧 fallback viewer。

## 已执行验证

### 1. 语法检查

命令：

```bash
node --check deps/cadgamefusion/tools/web_viewer/app.js
node --check deps/cadgamefusion/tools/web_viewer/service-worker.js
node --check deps/cadgamefusion/tools/web_viewer_desktop/main.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js
```

结果：

- 全部通过。

批量 smoke 脚本：

```bash
for f in \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_classic_leader_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_current_layer_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_attribute_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_group_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_layer_session_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_mleader_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_source_group_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_space_layout_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js; do
  node --check "$f" || exit 1
done
```

结果：

- `all-smoke-checks-ok`

### 2. Node bootstrap 单元测试

命令：

```bash
node --test apps/web/tests/web_bootstrap_entry.test.js
```

结果：

```text
tests 5
pass 5
fail 0
```

### 3. product bootstrap import graph

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js --repo-root /Users/chouhua/Downloads/Github/VemCAD --outdir deps/cadgamefusion/build/product_bootstrap_import_graph
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/product_bootstrap_import_graph/20260423_095436/summary.json
graph_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/product_bootstrap_import_graph/20260423_095436/product-offline-import-graph.json
assets_js=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/product_bootstrap_import_graph/20260423_095436/product-offline-assets.js
```

关键摘要：

```json
{
  "ok": true,
  "file_count": 147,
  "asset_count": 147,
  "file_counts": {
    "apps_web": 3,
    "web_viewer": 137,
    "vendor": 7,
    "other": 0
  },
  "missing_count": 0
}
```

说明：

- 初版 graph 只扫到 137 个文件。
- 补充常量 dynamic import 解析后，`preview_app.js` 与 vendor dynamic dependency 进入图，最终为 147 个文件。

### 4. repo-root browser smoke

临时依赖：

```bash
ln -s /tmp/vemcad-playwright-deps/node_modules deps/cadgamefusion/node_modules
```

静态服务：

```bash
python3 -m http.server 18082 --bind 127.0.0.1 --directory /Users/chouhua/Downloads/Github/VemCAD
```

table smoke：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js --base-url http://127.0.0.1:18082/ --url-prefix deps/cadgamefusion --outdir deps/cadgamefusion/build/editor_table_smoke_url_prefix
```

结果：

```text
summary_json=deps/cadgamefusion/build/editor_table_smoke_url_prefix/20260423_095554/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "url_prefix": "deps/cadgamefusion",
  "fixture": "/deps/cadgamefusion/tools/web_viewer/tests/fixtures/editor_table_fixture.json"
}
```

insert group smoke：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/editor_insert_group_smoke.js --base-url http://127.0.0.1:18082/ --url-prefix deps/cadgamefusion --outdir deps/cadgamefusion/build/editor_insert_group_smoke_url_prefix
```

结果：

```text
summary_json=deps/cadgamefusion/build/editor_insert_group_smoke_url_prefix/20260423_095554/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "url_prefix": "deps/cadgamefusion",
  "fixture": "/deps/cadgamefusion/tools/web_viewer/tests/fixtures/editor_insert_group_fixture.json"
}
```

清理：

- `deps/cadgamefusion/node_modules` 临时 symlink 已删除。
- `18082` 静态服务已停止。

### 5. packaged build

命令：

```bash
cd deps/cadgamefusion/tools/web_viewer_desktop
npm run pack
```

结果：

- `electron-builder --dir` 成功生成 `dist/mac-arm64/VemCAD.app`。
- macOS code signing 被跳过，原因是本机没有有效 Developer ID identity；这是本地签名环境限制，不影响本次资源布局验证。

资源检查：

```bash
find dist/mac-arm64/VemCAD.app/Contents/Resources \
  -path '*cad_resources/tools/web_viewer/index.html' \
  -o -path '*cad_resources/tools/web_viewer/app.js' \
  -o -path '*web_viewer/index.html' \
  -o -path '*web_viewer/app.js'
```

结果包含：

```text
dist/mac-arm64/VemCAD.app/Contents/Resources/cad_resources/tools/web_viewer/app.js
dist/mac-arm64/VemCAD.app/Contents/Resources/cad_resources/tools/web_viewer/index.html
dist/mac-arm64/VemCAD.app/Contents/Resources/web_viewer/app.js
dist/mac-arm64/VemCAD.app/Contents/Resources/web_viewer/index.html
```

补充检查：

```json
{
  "cad_resources/tools/web_viewer/index.html": true,
  "cad_resources/tools/web_viewer/app.js": true,
  "cad_resources/tools/web_viewer/legacy_app_bootstrap.js": true,
  "web_viewer/index.html": true,
  "web_viewer/app.js": true
}
```

结论：

- staged viewer 已进入 packaged `cad_resources`。
- 旧 fallback viewer 仍存在。
- 下一步需要 runtime smoke 验证实际启动 URL，而不只是文件存在。

## 未执行验证

### 1. 全量 editor browser smoke

本轮只对 `editor_table_smoke.js` 和 `editor_insert_group_smoke.js` 做 repo-root browser 代表性验证。

影响：

- 其余改造脚本已通过语法检查。
- 后续可按同一 `--url-prefix deps/cadgamefusion` 方式逐个跑全量 browser smoke。

### 2. packaged runtime smoke

未执行：

- `desktop_packaged_settings_smoke.js`

原因：

- 本轮目标是完成 `npm run pack` 与资源布局验证。
- 实际运行 packaged app 的 Settings/Open CAD smoke 涉及更长 UI 流程和本地 DWG/route 依赖，留到下一轮。

## 风险结论

### 已收敛

- 基础 editor smoke 已基本具备 repo-root server 运行能力。
- product offline 资源闭包已有生成式 graph，可作为后续 service worker precache 输入。
- packaged build 已证明 staged viewer 资源进入 `cad_resources`。

### 仍待后续收敛

- `--url-prefix` helper 仍在各脚本重复，应抽共享 utility。
- service worker 还没有消费 `product-offline-assets.js`。
- packaged app 实际启动路径仍需 UI/runtime smoke 确认。
