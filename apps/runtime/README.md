# VemCAD Runtime

`apps/runtime` 是 VemCAD 的产品运行时入口，负责承载官方工程模型，而不是 UI 会话状态或 CAD 内核实现。

当前目录先提供可提交的模块骨架，后续实现按 `docs/VEMCAD_PROJECT_RUNTIME.md` 推进。

## 目录职责

- `project/`: 工程文件模型、持久化、版本迁移、稳定 save/load。
- `constraint/`: 参数、约束、求解绑定与诊断。
- `feature/`: feature tree、依赖图、rebuild 计划与执行顺序。
- `scene/`: `Project` 到 `CADGF Document` 的派生与场景缓存。

## 边界

- 输入：Workbench/desktop/router 发起的工程编辑意图、导入结果、重建请求。
- 输出：稳定的 `VemCAD Project`、派生 `CADGF Document`、重建诊断与查询接口。
- 不负责：Electron 壳、Web 面板状态、CADGF 几何内核、插件导入导出 ABI。
