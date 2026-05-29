# VemCAD Web Runtime Hardening Development

日期：2026-04-23

## 目标

延续上一轮 web bootstrap 集成后的剩余建议，优先收敛三类风险：

1. packaged desktop 不应对不存在的 repo-root `apps/web/app.js` 做无效 product 探测。
2. browser smoke 应逐步支持从 VemCAD repo root 静态服务运行。
3. service worker 至少要缓存当前 live entry 的静态 import 闭包，避免离线时 `app.js` 命中但 `legacy_app_bootstrap.js` 缺失。

## 并行结论

本轮并行检查拆成三条线：

- desktop packaging：packaged 默认加载 `Resources/web_viewer/index.html`，会让 `app.js` 尝试探测不存在的 repo-root product 模块。
- browser smoke：多数 editor smoke 已有 `--base-url`，但仍硬编码 `tools/web_viewer/index.html` 与 `/tools/web_viewer/...` fixture 路径。
- service worker：受控 viewer 页面可以拦截 `/apps/web/*` 子资源请求，但 product/editor import 闭包较大，手写完整 product offline 清单风险高。

因此本轮采用小步方案：

- desktop 环境显式保持 legacy fallback，不做 product fetch/import。
- packaged 启动优先使用 staged `cad_resources/tools/web_viewer/index.html`。
- 先把基础 editor smoke 和 solver panel smoke 加上 `--url-prefix`。
- service worker 只把当前 shell 静态依赖补齐到 v3，不承诺完整 product offline。

## 实现内容

### 1. desktop 运行时禁用 product 探测

修改：

- `deps/cadgamefusion/tools/web_viewer/app.js`

新增：

- `isDesktopRuntime()`
- `getProductBootstrapFallbackReason()`

行为变化：

- 当 preload 暴露 `window.vemcadDesktop` 时，`canLoadProductBootstrap()` 直接返回 `false`。
- desktop fallback reason 明确记录为 `desktop-runtime-product-bootstrap-disabled`。
- browser repo-root 运行仍保留 product-first 行为。

### 2. packaged desktop 优先使用 staged viewer

修改：

- `deps/cadgamefusion/tools/web_viewer_desktop/main.js`

新增：

- `resolvePackagedViewerPath()`

行为变化：

- packaged 默认优先从 `detectCadRuntime().viewerRoot/index.html` 启动。
- 当前 staging 产物中该路径对应 `Resources/cad_resources/tools/web_viewer/index.html`。
- 如果 staged viewer 不存在，仍回退到旧的 `Resources/web_viewer/index.html`，避免破坏旧包结构。

### 3. browser smoke 增加 repo-root URL 前缀

修改：

- `deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js`

新增参数：

- `--url-prefix deps/cadgamefusion`

行为变化：

- 空前缀保持原来的 deps-root server 行为。
- 指定 `--url-prefix deps/cadgamefusion` 时，页面 URL 变为 `deps/cadgamefusion/tools/web_viewer/index.html`。
- `editor_selection_summary_smoke.js` 的默认 fixture 会同步从 `/tools/...` 改写为 `/deps/cadgamefusion/tools/...`。
- summary 中记录 `url_prefix`，方便验证报告确认实际运行模式。

### 4. service worker app shell v3

修改：

- `deps/cadgamefusion/tools/web_viewer/service-worker.js`
- `deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js`

行为变化：

- cache name 从 `cadgf-web-viewer-v2` 升级到 `cadgf-web-viewer-v3`。
- precache 增加 `./legacy_app_bootstrap.js`。
- cache/version smoke 改为读取当前 `CACHE_NAME`，并模拟 `cadgf-web-viewer-v2 -> 当前版本` 升级。

## 受影响文件

- [apps/web/tests/web_bootstrap_entry.test.js](/Users/chouhua/Downloads/Github/VemCAD/apps/web/tests/web_bootstrap_entry.test.js)
- [deps/cadgamefusion/tools/web_viewer/app.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/app.js)
- [deps/cadgamefusion/tools/web_viewer/service-worker.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/service-worker.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/solver_action_panel_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js)
- [deps/cadgamefusion/tools/web_viewer_desktop/main.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer_desktop/main.js)

## 未做事项

- 没有把 `apps/web/*` 硬塞进 service worker precache；当前 product/editor 闭包较大，后续应做生成式清单。
- 没有删除 `package.json` 里的旧 `Resources/web_viewer` extraResource；本轮先保留回退能力。
- 没有批量改完所有 editor smoke；本轮先改基础 selection smoke 与 solver panel smoke，后续可按同一 helper 模式扩展。

## 后续建议

1. 给其余 editor smoke 复制 `--url-prefix` 模式。
2. 为 product offline 做静态 import graph 生成脚本，而不是人工维护 100+ 文件清单。
3. 在下一轮 packaged 验证中运行 `npm run pack`，确认 packaged app 实际从 `cad_resources/tools/web_viewer/index.html` 启动。
