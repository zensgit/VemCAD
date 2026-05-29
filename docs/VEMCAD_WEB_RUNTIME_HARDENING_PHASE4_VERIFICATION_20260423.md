# VemCAD Web Runtime Hardening Phase 4 Verification

日期：2026-04-23

## 验证目标

确认 Phase 4 满足 5 个条件：

1. service worker 仍默认只安装 `cadgf-web-viewer-v3` shell cache。
2. product offline cache 只能显式触发，并能缓存 product graph 生成的 147 个 asset。
3. 离线时 product bootstrap asset 和 shell asset 都可从对应 cache 读取。
4. repo-root `--url-prefix deps/cadgamefusion` editor/product preview smoke 覆盖扩大。
5. 临时 Playwright symlink 与静态服务已清理。

## 已执行验证

### 1. 语法检查

命令：

```bash
node --check deps/cadgamefusion/tools/web_viewer/service-worker.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/smoke_url_utils.js
```

结果：

```text
exit 0
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

### 3. service worker cache-version 回归

命令前准备：

```bash
ln -s /tmp/vemcad-playwright-deps/node_modules deps/cadgamefusion/node_modules
```

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js \
  --repo-root /Users/chouhua/Downloads/Github/VemCAD \
  --outdir deps/cadgamefusion/build/service_worker_cache_version_phase4
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/service_worker_cache_version_phase4/20260423_110717/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "previous_cache_name": "cadgf-web-viewer-v2",
  "current_cache_name": "cadgf-web-viewer-v3",
  "product_offline_cache_name": "cadgf-product-offline-v1",
  "offline_shell_fetch_ok": true,
  "offline_product_fetch_failed": true,
  "default_product_cache_not_installed": true
}
```

结论：

- 默认升级仍只安装 shell cache。
- 旧 `cadgf-web-viewer-v2` 被删除。
- 未显式触发 product offline 时，`/apps/web/app.js` 离线读取仍失败。

### 4. product offline 正向 smoke

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js \
  --repo-root /Users/chouhua/Downloads/Github/VemCAD \
  --outdir deps/cadgamefusion/build/service_worker_product_offline_smoke
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/service_worker_product_offline_smoke/20260423_110717/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "shell_cache_name": "cadgf-web-viewer-v3",
  "product_offline_cache_name": "cadgf-product-offline-v1",
  "graph_asset_count": 147,
  "cache_reply": {
    "ok": true,
    "cacheName": "cadgf-product-offline-v1",
    "assetCount": 147,
    "cachedCount": 147
  },
  "offline_product_fetch_ok": true,
  "offline_workspace_fetch_ok": true,
  "offline_shell_fetch_ok": true
}
```

生成的 graph summary：

```text
/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/service_worker_product_offline_smoke/20260423_110717/product_bootstrap_import_graph/20260423_110717/summary.json
```

结论：

- graph -> service worker message -> `cadgf-product-offline-v1` -> offline fetch 全链路通过。
- product cache 和 shell cache 独立存在。

### 5. repo-root `--url-prefix` browser smoke

命令模式：

```bash
python3 -m http.server 18084 --bind 127.0.0.1 --directory /Users/chouhua/Downloads/Github/VemCAD
node deps/cadgamefusion/tools/web_viewer/scripts/<smoke>.js \
  --base-url http://127.0.0.1:18084/ \
  --url-prefix deps/cadgamefusion \
  --outdir deps/cadgamefusion/build/repo_root_url_prefix_phase4/<smoke>
```

通过项：

```text
editor_table_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_table_smoke/20260423_110747/summary.json
editor_mleader_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_mleader_smoke/20260423_110748/summary.json
editor_classic_leader_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_classic_leader_smoke/20260423_110749/summary.json
editor_space_layout_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_space_layout_smoke/20260423_110750/summary.json
editor_selection_summary_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_selection_summary_smoke/20260423_110751/summary.json
editor_current_layer_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_current_layer_smoke/20260423_110752/summary.json
editor_layer_session_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_layer_session_smoke/20260423_110753/summary.json
editor_source_group_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_source_group_smoke/20260423_110755/summary.json
editor_insert_group_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_insert_group_smoke/20260423_110756/summary.json
editor_insert_attribute_smoke ok deps/cadgamefusion/build/repo_root_url_prefix_phase4/editor_insert_attribute_smoke/20260423_110757/summary.json
```

### 6. repo-root product preview smoke

命令：

```bash
python3 -m http.server 18085 --bind 127.0.0.1 --directory /Users/chouhua/Downloads/Github/VemCAD
node deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js \
  --base-url http://127.0.0.1:18085/ \
  --url-prefix deps/cadgamefusion \
  --asset-prefix deps/cadgamefusion \
  --cases deps/cadgamefusion/tools/web_viewer/tests/fixtures/preview_provenance_product_smoke_cases.json \
  --outdir deps/cadgamefusion/build/repo_root_url_prefix_phase4/preview_provenance_product_smoke
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/repo_root_url_prefix_phase4/preview_provenance_product_smoke/20260423_110906/summary.json
passed 1
failed 0
bootstrap_source_counts.product 1
```

## 未通过或未执行项

### preview 默认 29 cases

执行默认 cases 时失败：

```text
page.waitForFunction: Timeout 25000ms exceeded.
```

定位结果：

- 默认首个 case 依赖 `deps/cadgamefusion/build/step186_origin_blocks/manifest.json`。
- 当前工作区该 artifact 不存在。
- 本轮改用已有 artifact 的 `preview_provenance_product_smoke_cases.json` 验证 product preview repo-root 路径。

### solver action panel smoke

未执行原因：

- 默认输入 `/build/solver_action_panels_ui_ranked_probe.out.json` 当前不存在。
- 未发现可直接替代的 `solver_action_panels_ui_ranked_probe.out.json`。

## 清理确认

命令：

```bash
test -e deps/cadgamefusion/node_modules && ls -ld deps/cadgamefusion/node_modules || echo 'deps/cadgamefusion/node_modules absent'
lsof -nP -iTCP:18084 -sTCP:LISTEN || true
lsof -nP -iTCP:18085 -sTCP:LISTEN || true
```

结果：

- `deps/cadgamefusion/node_modules absent`
- `18084` 无监听进程
- `18085` 无监听进程

## 风险结论

### 已收敛

- product offline cache 不再与 shell cache 混用。
- 默认 service worker 安装不会缓存 product assets。
- 显式触发后，147 个 product graph assets 可离线读取。
- repo-root editor smoke 覆盖从单个样例扩展到 10 个编辑器场景。

### 仍待后续收敛

- product app 尚未内置 runtime helper 自动触发 product offline cache。
- product graph 尚未输出 manifest hash。
- solver/default preview 全量 smoke 依赖的 build artifacts 需要补齐后再执行。
