# Workbench Solver

这个目录承接 editor solver bridge、solver state 和诊断协作者。

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
