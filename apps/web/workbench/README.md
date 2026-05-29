# VemCAD Web Workbench

这个目录用于承接从现有 Web workbench 中拆出的产品层模块。

当前可运行实现仍在 `deps/cadgamefusion/tools/web_viewer/`。拆分时不建议一开始就做大规模物理移动，而是先把模块边界和对外契约钉住，再把稳定模块迁入 `apps/web/workbench/`。

## 目标

- `command_registry.js` 收敛为薄注册层。
- `workspace.js` 收敛为 bootstrap / composition 层。
- 领域逻辑按命令、面板、选择、group、IO、solver 分区落地。

## 计划中的子目录

- `contracts/`
- `commands/`
- `panels/`
- `selection/`
- `source-groups/`
- `insert-groups/`
- `io/`
- `solver/`
- `bootstrap/`

这些目录不需要一次性全部创建。规则是：哪个领域先完成契约和验证，哪个目录先落第一批模块。

## 入口文档

- [兼容 Contract 入口](./contracts/README.md)
- [Workbench 拆分计划](../../../docs/VEMCAD_WORKBENCH_SPLIT_PLAN.md)
- [验证计划](../../../docs/VEMCAD_VERIFICATION_PLAN.md)

## 当前 facade 入口

- `./commands/registry.js`
- `./bootstrap/workspace_bootstrap.js`
- `./contracts/index.js`
