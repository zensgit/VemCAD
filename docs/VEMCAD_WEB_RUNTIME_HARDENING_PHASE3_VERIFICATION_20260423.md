# VemCAD Web Runtime Hardening Phase 3 Verification

日期：2026-04-23

## 验证目标

确认本轮 Phase 3 改动满足 5 个条件：

1. Shared URL utility 与所有使用它的 smoke 可解析。
2. URL utility 重构后，repo-root browser smoke 行为不回退。
3. packaged runtime smoke 能证明真实启动路径来自 `cad_resources/tools/web_viewer/index.html`。
4. product offline import graph 仍可生成 147 个 asset，无 missing import。
5. 临时 Playwright symlink 与静态服务已清理。

## 已执行验证

### 1. 语法检查

命令：

```bash
for f in \
  deps/cadgamefusion/tools/web_viewer/scripts/smoke_url_utils.js \
  deps/cadgamefusion/tools/web_viewer/scripts/desktop_packaged_viewer_path_smoke.js \
  deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js \
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

```text
final-script-checks-ok
```

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

### 3. packaged viewer path smoke

命令前准备：

```bash
ln -s /tmp/vemcad-playwright-deps/node_modules deps/cadgamefusion/node_modules
```

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/desktop_packaged_viewer_path_smoke.js --outdir deps/cadgamefusion/build/desktop_packaged_viewer_path_smoke
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/desktop_packaged_viewer_path_smoke/20260423_101145/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "location": "file:///Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer_desktop/dist/mac-arm64/VemCAD.app/Contents/Resources/cad_resources/tools/web_viewer/index.html",
  "has_desktop_bridge": true,
  "bootstrap": {
    "source": "legacy-fallback",
    "fallbackReason": "desktop-runtime-product-bootstrap-disabled"
  },
  "status": "Ready."
}
```

结论：

- packaged app 实际启动 URL 来自 `cad_resources/tools/web_viewer/index.html`。
- desktop bridge 已暴露。
- product probe 在 desktop runtime 中被禁用，稳定走 legacy fallback。

### 4. shared URL utility 后的 repo-root browser smoke

命令前准备：

```bash
ln -s /tmp/vemcad-playwright-deps/node_modules deps/cadgamefusion/node_modules
python3 -m http.server 18083 --bind 127.0.0.1 --directory /Users/chouhua/Downloads/Github/VemCAD
```

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/editor_table_smoke.js --base-url http://127.0.0.1:18083/ --url-prefix deps/cadgamefusion --outdir deps/cadgamefusion/build/editor_table_smoke_url_utils
```

结果：

```text
summary_json=deps/cadgamefusion/build/editor_table_smoke_url_utils/20260423_101247/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "url_prefix": "deps/cadgamefusion",
  "fixture": "/deps/cadgamefusion/tools/web_viewer/tests/fixtures/editor_table_fixture.json",
  "url": "http://127.0.0.1:18083/deps/cadgamefusion/tools/web_viewer/index.html?mode=editor&debug=1&cadgf=%2Fdeps%2Fcadgamefusion%2Ftools%2Fweb_viewer%2Ftests%2Ffixtures%2Feditor_table_fixture.json"
}
```

结论：

- `smoke_url_utils.js` 抽取后，repo-root URL 和 fixture rewrite 保持正确。
- 真实 Chromium smoke 仍通过。

### 5. product bootstrap import graph

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js --repo-root /Users/chouhua/Downloads/Github/VemCAD --outdir deps/cadgamefusion/build/product_bootstrap_import_graph_phase3
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/product_bootstrap_import_graph_phase3/20260423_101059/summary.json
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

### 6. 清理确认

命令：

```bash
test -e deps/cadgamefusion/node_modules && ls -ld deps/cadgamefusion/node_modules || echo 'deps/cadgamefusion/node_modules absent'
lsof -nP -iTCP:18083 -sTCP:LISTEN || true
```

结果：

- `deps/cadgamefusion/node_modules absent`
- `18083` 无监听进程

## 未执行验证

### 1. service worker 消费 product offline assets

未执行原因：

- 本轮明确不接入 `product-offline-assets.js`。
- 需要先设计 cache version、artifact 策略和新的 offline smoke。

当前边界：

- `service-worker.js` 仍是 v3 shell cache。
- `product_bootstrap_import_graph.js` 已提供可验证输入。

### 2. 全量 repo-root browser smoke

本轮只在 shared utility 抽取后重跑 `editor_table_smoke.js`。

影响：

- 所有相关脚本已通过 `node --check`。
- 其余 browser smoke 可按同样命令逐步补跑。

## 风险结论

### 已收敛

- `--url-prefix` URL/fixture rewrite 不再散落在每个 smoke 内部。
- packaged app 实际启动路径已被 runtime smoke 覆盖。
- product offline graph 仍可稳定生成 147 个 asset。

### 仍待后续收敛

- service worker 仍未消费 product offline asset list。
- 全量 repo-root browser smoke 还未全部跑完。
- 现有 `desktop_packaged_settings_smoke.js` 仍是长流程验证，后续可与轻量 viewer path smoke 分层使用。
