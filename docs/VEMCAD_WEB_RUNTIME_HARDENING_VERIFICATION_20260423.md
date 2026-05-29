# VemCAD Web Runtime Hardening Verification

日期：2026-04-23

## 验证目标

确认本轮 hardening 改动满足 5 个条件：

1. 新增/修改 JS 可解析。
2. desktop 环境不再执行 product bootstrap 探测。
3. 基础 editor smoke 可从 VemCAD repo-root server 运行，并命中 product bootstrap。
4. service worker v2 -> v3 升级会清理旧 cache，并缓存 `legacy_app_bootstrap.js`。
5. 临时 Playwright symlink 与本地静态服务已清理。

## 已执行验证

### 1. 语法检查

命令：

```bash
node --check deps/cadgamefusion/tools/web_viewer/app.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js
node --check deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js
node --check deps/cadgamefusion/tools/web_viewer_desktop/main.js
node --input-type=module -e "import fs from 'node:fs'; JSON.parse(fs.readFileSync('deps/cadgamefusion/tools/web_viewer_desktop/package.json','utf8')); console.log('desktop package json ok');"
```

结果：

- 全部通过。

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

新增覆盖：

- `canLoadProductBootstrap()` 在 `window.vemcadDesktop` 存在时不调用 `fetch()`。
- desktop fallback reason 为 `desktop-runtime-product-bootstrap-disabled`。
- desktop fallback 路径仍调用 legacy bootstrap。

### 3. repo-root editor smoke with `--url-prefix`

临时依赖：

```bash
ln -s /tmp/vemcad-playwright-deps/node_modules deps/cadgamefusion/node_modules
```

静态服务：

```bash
python3 -m http.server 18081 --bind 127.0.0.1 --directory /Users/chouhua/Downloads/Github/VemCAD
```

smoke 命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js --base-url http://127.0.0.1:18081/ --url-prefix deps/cadgamefusion --outdir deps/cadgamefusion/build/editor_selection_summary_smoke_url_prefix
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/editor_selection_summary_smoke_url_prefix/20260423_092810/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "url_prefix": "deps/cadgamefusion",
  "fixture": "/deps/cadgamefusion/tools/web_viewer/tests/fixtures/editor_selection_summary_fixture.json",
  "bootstrap": {
    "source": "product",
    "productBootstrapModuleUrl": "http://127.0.0.1:18081/apps/web/app.js"
  },
  "status": "Layer REDLINE lock: Off",
  "console": 0,
  "page_errors": 0
}
```

结论：

- `--url-prefix deps/cadgamefusion` 会正确生成 repo-root URL。
- 默认 fixture 已同步改写到 `/deps/cadgamefusion/tools/...`。
- 真实 Chromium 中仍命中 `bootstrap.source === "product"`。

### 4. service worker cache/version v3 smoke

命令：

```bash
node deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js --repo-root /Users/chouhua/Downloads/Github/VemCAD --outdir deps/cadgamefusion/build/service_worker_cache_version_smoke_v3
```

结果：

```text
summary_json=/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/build/service_worker_cache_version_smoke_v3/20260423_092810/summary.json
```

关键摘要：

```json
{
  "ok": true,
  "previous_cache_name": "cadgf-web-viewer-v2",
  "current_cache_name": "cadgf-web-viewer-v3",
  "offline_shell_fetch_ok": true,
  "offline_product_fetch_failed": true
}
```

cache 验证点：

- v2 cache 安装后可升级到 v3。
- v2 被清理，只保留 `cadgf-web-viewer-v3`。
- v3 entries 包含 `app.js` 与 `legacy_app_bootstrap.js`。
- `/apps/web/app.js` 仍未被 precache，offline product fetch 失败符合当前边界。

### 5. 清理确认

命令：

```bash
test -e deps/cadgamefusion/node_modules && ls -ld deps/cadgamefusion/node_modules || echo 'deps/cadgamefusion/node_modules absent'
lsof -nP -iTCP:18081 -sTCP:LISTEN || true
```

结果：

- `deps/cadgamefusion/node_modules absent`
- `18081` 无监听进程

## 未执行验证

### 1. packaged desktop pack

未执行命令：

```bash
cd deps/cadgamefusion/tools/web_viewer_desktop
npm run pack
```

原因：

- `pack` 会重新 staging 并生成较大的 Electron 产物；本轮只做代码级 packaged path hardening。

影响：

- `main.js` 语法已验证。
- packaged 实机启动路径仍需下一轮通过 `npm run pack` 和 packaged smoke 验证。

### 2. solver action panel browser smoke

未执行原因：

- 默认 `deps/cadgamefusion/build/solver_action_panels_ui_ranked_probe.out.json` 当前不存在。

已覆盖：

- `solver_action_panel_smoke.js` 语法通过。
- URL prefix helper 与参数解析已落地。

## 风险结论

### 已收敛

- desktop 环境不再对 repo-root product module 做无效探测。
- packaged 启动会优先使用 staged runtime viewer，并保留旧 viewer fallback。
- 基础 editor smoke 支持 repo-root server + `--url-prefix`。
- service worker v3 补齐了 live entry 的静态 `legacy_app_bootstrap.js` 依赖。

### 仍待后续收敛

- 完整 product offline 需要生成式 import graph 清单。
- packaged app 仍需完整 `npm run pack` 验证。
- 其余 editor browser smoke 仍需逐个加入 `--url-prefix`。
