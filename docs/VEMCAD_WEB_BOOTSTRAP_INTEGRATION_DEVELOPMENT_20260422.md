# VemCAD Web Bootstrap Integration Development

日期：2026-04-22

## 目标

把上一轮已经落下的 `apps/web/*` facade 接到真实运行入口，同时不破坏当前仍以 `deps/cadgamefusion/tools/web_viewer/` 为静态根目录的 smoke、desktop 打包和独立运行路径。

## 背景判断

上一轮已经完成：

- `apps/web/app.js`
- `apps/web/workbench/*`
- `apps/web/preview/runtime/*`

这些产品层 facade 已经具备稳定 import target，但真实运行入口仍是：

- `deps/cadgamefusion/tools/web_viewer/index.html`
- `deps/cadgamefusion/tools/web_viewer/app.js`

如果直接把 `index.html` 的 module script 改成 `apps/web/app.js`，会碰到两个结构性问题：

1. 很多现有 smoke 默认只把 `deps/cadgamefusion` 作为静态根目录。
2. desktop 打包与 staged resources 仍只复制 `tools/web_viewer/**`。

因此不能直接做“硬切入口”，否则 standalone / packaged 路径会直接 404 或缺文件。

## 最终方案

采用双态 bootstrap：

1. 保持 `deps/cadgamefusion/tools/web_viewer/app.js` 作为真实浏览器入口。
2. 入口先探测 `apps/web/app.js` 是否可达。
3. 可达时，切到产品层 `bootstrapVemcadWebApp()`。
4. 不可达时，自动回落到 legacy bootstrap。

这样可以同时覆盖两类运行方式：

- VemCAD repo root 集成部署
- 仍只暴露 `deps/cadgamefusion` 的 legacy / standalone 路径

## 实现内容

### 1. 抽出 legacy 启动逻辑

新增：

- `deps/cadgamefusion/tools/web_viewer/legacy_app_bootstrap.js`

职责：

- 保留原始 editor / preview 切换逻辑
- 继续暴露 `window.__vemcadApp.switchToEditor()`
- 保持对 `workspace.js` 和 `preview_app.js` 的 legacy 装配方式

这样 `app.js` 不再直接承载整段启动逻辑，而是只做入口决策。

### 2. 重写 live entry 为兼容壳

修改：

- `deps/cadgamefusion/tools/web_viewer/app.js`

入口现在负责：

- 探测产品层 bootstrap 模块 `apps/web/app.js` 是否可访问
- 可访问时调用 `bootstrapVemcadWebApp()`
- 不可访问时调用 `bootstrapLegacyWebViewerApp()`
- 在 `window.__vemcadBootstrap` 上暴露本次启动来源：
  - `product`
  - `legacy-fallback`

同时为了可测试性，入口壳增加了这些导出：

- `PRODUCT_BOOTSTRAP_MODULE_URL`
- `canLoadProductBootstrap()`
- `bootstrapProductWebApp()`
- `bootstrapWebViewerEntry()`
- `renderBootstrapFailure()`

浏览器默认行为保持不变：

- 只要没有显式设置 `globalThis.__VEMCAD_SKIP_AUTO_BOOTSTRAP = true`，入口仍会自动启动

### 3. 刷新 service worker app shell 版本

修改：

- `deps/cadgamefusion/tools/web_viewer/service-worker.js`

把 cache name 从 `cadgf-web-viewer-v1` 提升到 `cadgf-web-viewer-v2`，避免现有 service worker 继续长期提供旧版 `./app.js`。

这一步不是为了把 `apps/web/app.js` 也纳入 precache，而是为了：

- 让已经被 service worker 控制的页面至少能拿到新的 live entry 壳

### 4. 补最小无浏览器回归测试

新增：

- `apps/web/tests/web_bootstrap_entry.test.js`

使用 `node:test` 覆盖这些关键行为：

- 入口壳优先选择 product bootstrap
- product 不可达时回退到 legacy bootstrap
- `installVemcadAppBridge()` 能通过已 bootstrapped workspace 完成 `switchToEditor()` handoff
- `bootstrapLegacyWebViewerApp()` 在 preview 模式下仍暴露 editor handoff contract

### 5. 增强 editor browser smoke 观测字段

修改：

- `deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js`

新增 summary 字段：

- `bootstrap`

该字段只记录 `window.__vemcadBootstrap`，不参与通过/失败判定。目的：

- browser smoke 仍验证原有 editor 行为 contract
- 验证报告可以直接看到本次页面实际走的是 `product` 还是 `legacy-fallback`

### 6. 增强 preview provenance smoke 的 repo-root 运行能力

修改：

- `deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js`

新增能力：

- 支持 `--url-prefix`，用于把 case query 中的相对页面路径挂到 repo-root server 下的 `deps/cadgamefusion`
- 支持 `--asset-prefix`，用于把相对 `manifest` / `gltf` 参数改写到 repo-root server 可访问路径
- 在未显式传 `--asset-prefix` 时，会根据最终页面路径自动推导 viewer root 前缀
- summary 新增 `bootstrap_source_counts`，用于确认 preview smoke 实际跑到 product 还是 legacy fallback

新增：

- `deps/cadgamefusion/tools/web_viewer/tests/fixtures/preview_provenance_product_smoke_cases.json`

该 case 使用 repo-root server 验证：

- product bootstrap 被命中
- 插入属性 override provenance 能正确显示
- selection details 中保留 group、origin、block、attribute value 等关键字段

### 7. 新增 service worker cache/version smoke

新增：

- `deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js`

职责：

- 用临时静态服务模拟 `cadgf-web-viewer-v1 -> cadgf-web-viewer-v2` 升级
- 验证旧 cache 被清理
- 验证新版 app shell cache 包含 `index.html`、`app.js`、`style.css`、manifest 和 icon
- 验证 `apps/web/app.js` 没有被错误 precache
- 进入 offline 后验证 scope 内 `./app.js` 可由 service worker cache 提供
- 进入 offline 后验证 scope 外 `/apps/web/app.js` 不会被当前 service worker 误接管

## 受影响文件

- [apps/web/app.js](/Users/chouhua/Downloads/Github/VemCAD/apps/web/app.js)
- [apps/web/tests/web_bootstrap_entry.test.js](/Users/chouhua/Downloads/Github/VemCAD/apps/web/tests/web_bootstrap_entry.test.js)
- [apps/web/README.md](/Users/chouhua/Downloads/Github/VemCAD/apps/web/README.md)
- [deps/cadgamefusion/tools/web_viewer/app.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/app.js)
- [deps/cadgamefusion/tools/web_viewer/legacy_app_bootstrap.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/legacy_app_bootstrap.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/editor_selection_summary_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/preview_provenance_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/scripts/service_worker_cache_version_smoke.js)
- [deps/cadgamefusion/tools/web_viewer/service-worker.js](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/service-worker.js)
- [deps/cadgamefusion/tools/web_viewer/tests/fixtures/preview_provenance_product_smoke_cases.json](/Users/chouhua/Downloads/Github/VemCAD/deps/cadgamefusion/tools/web_viewer/tests/fixtures/preview_provenance_product_smoke_cases.json)

## 这次没有做的事

- 没有把 `index.html` 的 `<script type="module">` 直接改到 `apps/web/app.js`
- 没有改 desktop packaging/staging 资源复制路径
- 没有把 `apps/web/*` 纳入 service worker scope 内的 precache
- 没有把所有 browser smoke 的默认静态根目录硬切到 repo root；本次只让 preview provenance smoke 支持显式/自动路径前缀

## 剩余风险

### 1. product bootstrap 只在 repo-root 部署时可直接命中

如果运行环境只暴露 `deps/cadgamefusion`，当前行为会稳定回落到 legacy bootstrap，而不会使用 `apps/web/app.js`。

### 2. service worker 仍只 precache `./app.js`

当前刷新的是 entry shell，不是完整的 `apps/web/*` app shell。换句话说：

- 在线加载：当前方案可工作
- 完整 offline precache：还没有收敛到产品层入口

### 3. desktop / packaged 仍依赖 legacy 目录结构

本次故意保留这一点，以避免把入口迁移和 packaging 重构耦合到同一个变更里。

### 4. preview provenance smoke 已支持 repo-root，但其他 smoke 仍需逐步收敛

本次只补了当前验证所需的 preview provenance 前缀能力。其他 browser smoke 若也要从 repo root 统一调度，还需要逐个整理 URL 与资源路径假设。

## 下一步建议

1. 把其他 browser smoke 的静态根目录也抽成可配置，支持 repo root 与 `deps/cadgamefusion` 双模式。
2. 把 desktop staging 也改成显式支持 VemCAD repo root 的 `apps/web/*` 资源。
3. 再决定是否把 product bootstrap 彻底迁入 service worker scope 内，或者通过构建产物镜像到 `tools/web_viewer/`。
