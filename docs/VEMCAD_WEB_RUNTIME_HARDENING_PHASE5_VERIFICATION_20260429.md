# VemCAD Web Runtime Hardening Phase 5 Verification

日期：2026-04-29

## 验证目标

确认 Phase 5 满足 6 个条件：

1. Product offline runtime helper 可单元测试，不依赖真实 service worker。
2. Product bootstrap 对 offline cache 的触发是非阻塞的。
3. Product import graph 输出 manifest version、内容 digest 和稳定 SHA-256 hash。
4. Service worker product offline browser smoke 仍能缓存并离线读取完整 product graph。
5. Solver action panel repo-root smoke 在补齐 JSON 后可通过。
6. Preview 默认 smoke 的剩余失败原因从“artifact 缺失”收敛为明确的 artifact 质量/expectation 问题。

## 已执行验证

### 1. 语法检查

命令：

```bash
node --check apps/web/app.js
node --check apps/web/offline/product_offline_cache.js
node --check apps/web/tests/product_offline_cache.test.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js
```

结果：

```text
exit 0
```

### 2. Apps/Web 单元测试

命令：

```bash
node --test apps/web/tests/*.test.js
```

结果：

```text
tests 17
pass 17
fail 0
```

覆盖点：

- `readProductOfflineManifest()` 读取 manifest assets。
- fallback 到 `__VEMCAD_PRODUCT_OFFLINE_ASSETS`。
- service worker message payload。
- service worker 不可用、无 active worker、无 assets、timeout。
- `scheduleProductOfflineCaching()` scheduling 与 rejection。
- preview/editor bootstrap 后触发 offline cache。
- offline scheduler 同步失败不阻塞 preview startup。

### 3. Product Import Graph

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/product_bootstrap_import_graph.js \
  --repo-root /Users/chouhua/Downloads/Github/VemCAD \
  --outdir deps/cadgamefusion/build/product_bootstrap_import_graph_phase5_content_hash
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/product_bootstrap_import_graph_phase5_content_hash/20260428_172904/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "asset_count": 148,
  "digest_count": 148,
  "hash": "60d58caf162e67cd0860be2e55c1635918fe24e961d72caf0241938dcb220120",
  "missing_count": 0
}
```

说明：

- Phase 4 是 147 个 assets。
- Phase 5 新增 `apps/web/offline/product_offline_cache.js` 后，graph 闭包变为 148 个 assets。
- `asset_manifest_hash` 基于 asset path 和文件内容 digest。

### 4. Service Worker Product Offline Smoke

命令前准备：

```bash
npm --prefix /tmp/vemcad-playwright-deps install playwright
ln -s /tmp/vemcad-playwright-deps/node_modules deps/cadgamefusion/node_modules
```

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/service_worker_product_offline_smoke.js \
  --repo-root /Users/chouhua/Downloads/Github/VemCAD \
  --outdir deps/cadgamefusion/build/service_worker_product_offline_smoke_phase5
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/service_worker_product_offline_smoke_phase5/20260429_104637/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "graph_asset_count": 148,
  "graph_manifest_version": "product-offline-manifest-v1",
  "graph_asset_manifest_hash": "60d58caf162e67cd0860be2e55c1635918fe24e961d72caf0241938dcb220120",
  "cache_reply": {
    "ok": true,
    "cacheName": "cadgf-product-offline-v1",
    "assetCount": 148,
    "cachedCount": 148
  },
  "offline_product_fetch_ok": true,
  "offline_workspace_fetch_ok": true,
  "offline_shell_fetch_ok": true
}
```

结论：

- graph -> manifest hash -> service worker message -> product cache -> offline fetch 全链路通过。

### 5. Service Worker Cache Version Smoke

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js \
  --repo-root /Users/chouhua/Downloads/Github/VemCAD \
  --outdir deps/cadgamefusion/build/service_worker_cache_version_phase5
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/service_worker_cache_version_phase5/20260429_104637/summary.json
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

- 默认 service worker install/upgrade 仍不会安装 product cache。
- 未显式触发 product offline 时，离线读取 `/apps/web/app.js` 仍失败。

### 6. Solver Artifact 与 Repo-Root Smoke

生成默认 solver JSON：

```bash
./build/tools/solve_from_project \
  --json build/solve_from_project_json_smoke/ranked_constraints_project.json \
  > build/solver_action_panels_ui_ranked_probe.out.json
```

生成结果：

```json
{
  "ok": true,
  "action_panel_count": 4,
  "structural_state": "mixed"
}
```

执行 smoke：

```bash
python3 -m http.server 18086 --bind 127.0.0.1 --directory /Users/chouhua/Downloads/Github/VemCAD
node deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js \
  --base-url http://127.0.0.1:18086/ \
  --url-prefix deps/cadgamefusion \
  --outdir deps/cadgamefusion/build/solver_action_panel_smoke_phase5_repo_root
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/solver_action_panel_smoke_phase5_repo_root/20260429_104707/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "panel_count": 4,
  "flow_check_count": 26,
  "url_prefix": "deps/cadgamefusion",
  "solver_json": "/build/solver_action_panels_ui_ranked_probe.out.json"
}
```

### 7. Step186 Preview Artifacts

默认校验模式：

```bash
python3 tools/prepare_step186_preview_artifacts.py \
  --build-dir build \
  --outdir build/prepare_step186_preview_artifacts_phase5
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/prepare_step186_preview_artifacts_phase5/20260428_092944/summary.json
passed 4
failed 1
```

失败：

```json
{
  "id": "mleader_json_only",
  "error": "mleader_json_only validation failed: document entity id=1 source_type LEADER requires proxy_kind='leader'"
}
```

跳过校验生成完整 artifact：

```bash
python3 tools/prepare_step186_preview_artifacts.py \
  --build-dir build \
  --outdir build/prepare_step186_preview_artifacts_phase5_skip_validate \
  --skip-validate
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/prepare_step186_preview_artifacts_phase5_skip_validate/20260428_093007/summary.json
passed 17
failed 0
validated false
```

默认 preview smoke 引用的 16 个 manifests 已存在：

```json
{
  "total": 16,
  "present": 16,
  "missing": []
}
```

### 8. Preview 默认 Smoke

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js \
  --base-url http://127.0.0.1:18086/ \
  --url-prefix deps/cadgamefusion \
  --asset-prefix deps/cadgamefusion \
  --outdir deps/cadgamefusion/build/preview_provenance_smoke_phase5_default_repo_root
```

结果：

```text
page.waitForFunction: Timeout 25000ms exceeded.
```

定位：

- `build/step186_origin_blocks/manifest.json` 已存在。
- 该 manifest 只有 `document_json`，`status` 是 `partial`。
- warnings 包含 `mesh_gltf_missing` 和 `mesh_metadata_missing`。
- 默认 case 仍期待 `Loaded successfully.`，但当前 JSON fallback 路径不会满足这个状态文本。

结论：

- 默认 preview smoke 不再阻塞于 manifest 缺失。
- 剩余问题是 artifact 内容/状态 expectation：TinyGLTF 不可用导致 glTF 输出缺失，且 `mleader_json_only` 校验仍失败。

## 清理确认

命令：

```bash
test -L deps/cadgamefusion/node_modules && rm deps/cadgamefusion/node_modules || true
lsof -nP -iTCP:18086 -sTCP:LISTEN || true
```

结果：

- `deps/cadgamefusion/node_modules` 临时 symlink 已移除。
- `18086` 无监听进程。
- `/tmp/vemcad-playwright-deps/node_modules` 保留为临时依赖缓存。

## 风险结论

### 已收敛

- Product offline runtime helper 已接入 product bootstrap，且失败不阻塞启动。
- Product offline graph 现在有 version、content digests 和 manifest hash。
- Service worker product offline 全链路以 148 个 assets 通过真实浏览器验证。
- Solver action panel repo-root smoke 已从“缺默认 JSON”推进到通过。

### 仍待后续收敛

- Step186 `mleader_json_only` proxy metadata 校验失败。
- TinyGLTF 不可用导致默认 preview artifacts 缺 glTF/mesh metadata。
- 默认 preview 29 cases 需要在修复 artifacts 后重跑。
