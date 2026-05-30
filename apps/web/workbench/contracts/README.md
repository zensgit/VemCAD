# Workbench Contracts

这个目录用于承接 Web workbench 拆分期间必须保持稳定的兼容 contract 说明和后续 facade 落点。

## 迁移期稳定 contract

- `registerCadCommands(commandBus, context)`
  - editor 命令注册兼容导出。内部实现可以拆分，但调用形状和已注册命令语义不能因迁移直接消失。
- `computeRotatePayload(centerPoint, referencePoint, targetPoint)`
  - 旋转工具使用的兼容 payload helper。迁移期继续保留，直到工具侧完成切换。
- `computeScalePayload(centerPoint, referencePoint, targetPoint)`
  - 缩放工具使用的兼容 payload helper。迁移期继续保留，直到工具侧完成切换。
- `bootstrapCadWorkspace({ params })`
  - workbench 启动入口。返回的 `{ destroy, state, commands, importPayload }` 视为稳定对外接口。
- `mountSolveWorkbenchDemo({ root, appBridge })`
  - 产品层 solve workbench demo 入口。用于本地 smoke / demo，不替代正式 workbench bootstrap。
- `window.__vemcadApp.switchToEditor(documentJson)`
  - preview -> editor 的稳定桥接路径。preview/runtime 和 workbench/bootstrap 可以重组，但全局 handoff 入口不能回退。
- `window.__vemcadApp.mountSolvePanel(root, { project, controller })`
  - 产品层 solver panel 的稳定挂载入口。它动态加载 `workbench/panels/solve_panel.js`，只消费 solver controller contract，不直接重写 `/solve` 契约。
- `window.__cadDebug`
  - `?debug=1` 下暴露的 debug / smoke contract。它不是普通产品 API，但拆分时不能回退核心调试能力。

## 当前上游实现

- `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`
- `deps/cadgamefusion/tools/web_viewer/app.js`
- `deps/cadgamefusion/tools/web_viewer/preview_app.js`

## 目录边界

- 这里记录兼容面和 facade 落点，不承接大段领域实现。
- 命令、bootstrap、preview runtime 的实际模块应分别回到 `../commands/`、`../bootstrap/` 和 `../../preview/runtime/`。
- preview 侧运行时入口补充说明见 [../../preview/runtime/contracts/README.md](../../preview/runtime/contracts/README.md)。

## 当前导出入口

- `index.js`
  - 产品层聚合导出稳定 workbench contract，并标记全局 contract 常量。
