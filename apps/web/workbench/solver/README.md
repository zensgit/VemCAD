# Workbench Solver

这个目录承接 editor solver bridge、solver state 和诊断协作者。

当前产品层入口：

- `solve_workbench.js`：调用产品 `/solve` 服务、归一化 solve summary、从
  `evaluatedView` 派生 CADGF preview document，并提供可绑定 UI 的 controller
  `{ getState, subscribe, solve }`。
- `demo_projects.js`：三个固定 VEMCAD-PROJECT 样本（可解、冲突、unsupported
  passthrough），用于 demo / smoke / fixture。
- `demo_fetch.js`：纯前端 demo fetch，按 `demo_projects.js` 的 project id 返回固定
  `/solve` 信封，便于在没有真实 solve 服务时演示 panel 状态流。
- `demo_page.js` / `demo.html`：可打开的产品层 solve workbench demo，串起 app bridge、
  panel、demo fixtures 和 demo fetch。
- `preview_canvas.js`：把 solved 后的 CADGF preview document 绘成轻量 SVG 预览。

## 适合放在这里的内容

- solver bridge 和 action 状态机
- solver diagnostics、request/event state 归一化
- 被 panel 和 debug hook 共同消费的 solver 领域 helper

## 不应继续堆在这里的内容

- panel DOM 细节
- 全局 bootstrap 入口
- preview runtime 或 desktop 集成

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`

solver 领域逻辑应独立于 UI 壳层，避免继续依赖 `workspace.js` 中的大段闭包状态。
