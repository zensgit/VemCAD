# VemCAD Web Bootstrap Integration Verification

日期：2026-04-22

## 验证目标

确认本次双态 bootstrap 改动满足 6 个条件：

1. 新入口代码可解析。
2. product / legacy 入口选择逻辑可测。
3. editor handoff contract 没有回退。
4. 两种静态根目录下的资源可达性判断与设计一致。
5. preview provenance smoke 能在 repo-root server 下命中 product bootstrap。
6. service worker v1 -> v2 升级与 offline app shell cache 行为符合设计。

## 已执行验证

### 1. 语法检查

命令：

```bash
node --check apps/web/app.js
node --check deps/cadgamefusion/tools/web_viewer/app.js
node --check deps/cadgamefusion/tools/web_viewer/legacy_app_bootstrap.js
```

结果：

- 3 个入口相关模块都通过语法检查。

### 2. 模块导出检查

命令：

```bash
node --input-type=module -e "const mod = await import('./apps/web/app.js'); console.log(Object.keys(mod).sort().join(','));"
node --input-type=module -e "globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP = true; const mod = await import('./deps/cadgamefusion/tools/web_viewer/app.js'); console.log(Object.keys(mod).sort().join(','));"
```

结果：

- `apps/web/app.js` 导出：
  - `bootstrapVemcadWebApp`
  - `ensureWorkspaceBootstrapped`
  - `installVemcadAppBridge`
  - `resetVemcadWebAppBootstrapState`
  - `setEditorMode`
  - `setPreviewMode`
- `deps/.../app.js` 导出：
  - `PRODUCT_BOOTSTRAP_MODULE_URL`
  - `bootstrapProductWebApp`
  - `bootstrapWebViewerEntry`
  - `canLoadProductBootstrap`
  - `renderBootstrapFailure`

### 3. Node 内置测试

命令：

```bash
node --test apps/web/tests/web_bootstrap_entry.test.js
```

结果：

```text
✔ bootstrapWebViewerEntry prefers product bootstrap when reachable
✔ bootstrapWebViewerEntry falls back to legacy bootstrap when product module is unreachable
✔ installVemcadAppBridge imports payload into bootstrapped workspace
✔ bootstrapLegacyWebViewerApp wires preview mode and editor handoff contract
```

结论：

- 入口优先级符合预期。
- fallback 路径可用。
- `window.__vemcadApp.switchToEditor()` handoff contract 未回退。
- legacy preview 模式仍能切回 editor。

### 4. 现有 web_viewer Node 回归

命令：

```bash
node --test deps/cadgamefusion/tools/web_viewer/tests/document_preview_fallback.test.js deps/cadgamefusion/tools/web_viewer/tests/property_panel_dom_roots.test.js apps/web/tests/web_bootstrap_entry.test.js
node --test deps/cadgamefusion/tools/web_viewer/tests/editor_import_adapter.test.js deps/cadgamefusion/tools/web_viewer/tests/editor_commands.test.js
```

结果：

- 第一条命令：10/10 通过
- 第二条命令：302 个测试里 300 通过，2 个失败

失败测试：

- `solver.export-project outputs valid CADGF-PROJ that solve_from_project can consume`
- `selection-derived refs solve correctly with multiple constraint types`

失败原因：

- 两条失败都不是 JS 回归，而是本地 `deps/cadgamefusion/build_fix/tools/solve_from_project` 在执行时找不到 `@rpath/libcore.dylib`
- 报错路径仍指向旧的 `/Users/huazhou/...` 构建目录，说明是本机 solver 二进制/动态库装配问题，不是本次 bootstrap wiring 引入的问题

结论：

- 与 bootstrap/preview/editor handoff 直接相关的 JS 层测试通过
- `editor_commands.test.js` 的 solver 桥接尾部用例受本地原生构建环境阻塞，不能把这 2 个失败归因到本次入口改动

### 5. 静态根目录分辨验证

通过与现有 smoke 相同的静态文件解析规则进行文件级验证，结论如下：

- 当静态根目录是 VemCAD repo root 时：
  - `/deps/cadgamefusion/tools/web_viewer/index.html` 存在
  - `/apps/web/app.js` 存在
- 当静态根目录是 `deps/cadgamefusion` 时：
  - `/tools/web_viewer/index.html` 存在
  - `/apps/web/app.js` 不存在

结论：

- 这证明了本次不能直接把 live entry 硬切到 repo-level `apps/web/app.js`
- 也证明了 `product -> legacy fallback` 的双态方案是必要的

### 6. repo-root browser smoke：editor product bootstrap

临时依赖准备：

```bash
npm install --prefix /tmp/vemcad-playwright-deps playwright
/tmp/vemcad-playwright-deps/node_modules/.bin/playwright install chromium
ln -s /tmp/vemcad-playwright-deps/node_modules deps/cadgamefusion/node_modules
```

说明：

- 依赖安装在 `/tmp`
- Chromium 下载到 Playwright 用户缓存
- `deps/cadgamefusion/node_modules` 是临时 symlink，验证后已清理

静态服务：

```bash
python3 -m http.server 18080 --bind 127.0.0.1 --directory /Users/chouhua/Downloads/Github/VemCAD
```

smoke 命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js --base-url http://127.0.0.1:18080/deps/cadgamefusion/ --fixture /deps/cadgamefusion/tools/web_viewer/tests/fixtures/editor_selection_summary_fixture.json --outdir deps/cadgamefusion/build/editor_selection_summary_smoke_product
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/editor_selection_summary_smoke_product/20260422_231511/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "status": "Layer REDLINE lock: Off",
  "bootstrap": {
    "source": "product",
    "productBootstrapModuleUrl": "http://127.0.0.1:18080/apps/web/app.js"
  },
  "selection": "single",
  "entityCount": 1,
  "primaryType": "line",
  "console": 0,
  "pageErrors": 0
}
```

结论：

- `index.html -> tools/web_viewer/app.js -> apps/web/app.js -> workbench facade` 已在真实 Chromium 中跑通
- editor selection/property/layer panel contract 保持通过
- smoke summary 已记录 `bootstrap.source === "product"`

### 7. repo-root browser smoke：preview product bootstrap

命令：

```bash
node --input-type=module -e "<inline Playwright preview check>"
```

验证 URL：

```text
http://127.0.0.1:18080/deps/cadgamefusion/tools/web_viewer/index.html
```

结果摘要：

```json
{
  "bootstrap": {
    "source": "product",
    "productBootstrapModuleUrl": "http://127.0.0.1:18080/apps/web/app.js"
  },
  "status": "Loaded successfully.",
  "meshCount": "1",
  "vertexCount": "4",
  "previewHidden": false,
  "editorHidden": true,
  "pageErrors": 0
}
```

说明：

- Chromium 输出了若干 WebGL `GPU stall due to ReadPixels` performance warning
- 没有 page error
- preview 分支确认通过 `apps/web/app.js -> preview/runtime/preview_bootstrap.js -> preview_app.js`

### 8. repo-root browser smoke：preview provenance product/failure cases

失败态 provenance cases：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js --base-url http://127.0.0.1:18080/deps/cadgamefusion/ --cases deps/cadgamefusion/tools/web_viewer/tests/fixtures/preview_provenance_failure_cases.json --outdir deps/cadgamefusion/build/preview_provenance_failure_product_auto
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/preview_provenance_failure_product_auto/20260422_235836/summary.json
```

关键摘要：

```json
{
  "passed": 3,
  "failed": 0,
  "bootstrap_source_counts": {
    "product": 3
  }
}
```

成功态 product provenance case：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js --base-url http://127.0.0.1:18080/deps/cadgamefusion/ --cases deps/cadgamefusion/tools/web_viewer/tests/fixtures/preview_provenance_product_smoke_cases.json --outdir deps/cadgamefusion/build/preview_provenance_product
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/preview_provenance_product/20260422_235836/summary.json
```

关键摘要：

```json
{
  "passed": 1,
  "failed": 0,
  "bootstrap_source_counts": {
    "product": 1
  }
}
```

覆盖点：

- repo-root server 下自动改写相对 page / manifest 路径
- product bootstrap 被真实 Chromium 命中
- selection details 包含 `ATTRIB_INSERT_OVERRIDE`
- provenance detail 包含 `Origin INSERT/insert | exploded`
- block detail 包含 `Block Name AttribBlock`

### 9. service worker cache/version browser smoke

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js --repo-root /Users/chouhua/Downloads/Github/VemCAD --outdir deps/cadgamefusion/build/service_worker_cache_version_smoke
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/service_worker_cache_version_smoke/20260423_000302/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "offline_shell_fetch_ok": true,
  "offline_product_fetch_failed": true,
  "second_snapshot": {
    "keys": [
      "cadgf-web-viewer-v2"
    ]
  }
}
```

覆盖点：

- 首次安装 v1 cache 后，升级到 v2 会清理 v1
- v2 cache 包含 scope 内 app shell 资源
- `/apps/web/app.js` 没有被当前 service worker precache
- offline 时 scope 内 `./app.js` 可以从 cache 成功获取
- offline 时 scope 外 `/apps/web/app.js` 获取失败，符合当前设计边界

## 未执行验证

### 1. desktop / packaged 资源 staging

未执行原因：

- 本次只验证 repo-root browser 与 tools/web_viewer scope，不重构 desktop packaging

影响：

- packaged 环境仍预期走 legacy fallback，直到 staging 显式复制或映射 `apps/web/*`

### 2. 真实用户 profile 中的既有 service worker 升级

未执行原因：

- 本次 smoke 使用隔离浏览器 profile 验证 v1 -> v2 升级
- 没有复用真实用户浏览器 profile 中可能存在的旧 cache/storage 状态

影响：

- v1 -> v2 逻辑已验证
- 真实用户 profile 仍建议在下一轮发布前做一次手工升级确认

## 风险结论

### 已收敛

- 入口不会因为 repo root / deps root 差异而直接失效
- legacy handoff contract 保持可用
- 新产品层 facade 已接到真实 live entry 决策路径
- repo-root preview provenance smoke 已命中 product bootstrap
- service worker v1 -> v2 cache 清理和 offline shell 行为已完成浏览器级验证

### 仍待后续收敛

- desktop packaging 仍只复制 `tools/web_viewer/**`
- service worker 仍未把 `apps/web/*` 纳入完整 precache 范围
- 其他 browser smoke 的 URL/资源路径假设仍需逐个收敛到双根目录模式

## 建议后续验证

后续如果要扩展 packaged 覆盖面，优先验证 packaged 资源目录下的 fallback 行为：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js --base-url http://<packaged-or-staged-server>/
```
