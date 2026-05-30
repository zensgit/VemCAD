# Workbench Panels

这个目录承接 editor panel 和 panel orchestration 相关模块。

当前产品层入口：

- `solve_panel.js`：把 solver controller state 映射到最小 DOM panel。它只消费
  `workbench/solver` 的稳定状态，不重新定义 solve contract，也不直接调用 solver。

## 适合放在这里的内容

- property panel、solver action panel、状态栏等 UI 协作者
- panel state 到 DOM 的映射
- panel 级交互编排和消息展示

## 不应继续堆在这里的内容

- 纯命令逻辑
- 全局 bootstrap 壳层
- preview-only overlay 或 desktop bridge

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`

panel 层负责消费稳定命令和状态，不负责重新定义对外 contract。
