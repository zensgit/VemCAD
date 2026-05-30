# VemCAD Web

`apps/web` 是 VemCAD 的产品层 Web 入口，不是当前全部实现所在目录。

现阶段可运行的 workbench / preview 主实现仍在 `deps/cadgamefusion/tools/web_viewer/`。这里的职责是承接产品层目录、迁移入口和后续拆分落点，避免继续把产品规则直接堆回平台层实现。

## 当前实现基线

- live 模式入口：`deps/cadgamefusion/tools/web_viewer/app.js`
  - 当静态根目录可访问 `apps/web/app.js` 时，优先切到产品层 bootstrap。
  - 当运行环境仍只暴露 `deps/cadgamefusion` 时，自动回落到 `legacy_app_bootstrap.js`。
- 编辑工作台：`deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
- 工作台组装层：`deps/cadgamefusion/tools/web_viewer/ui/workspace.js`
- 预览与桌面桥接：`deps/cadgamefusion/tools/web_viewer/preview_app.js`

当前产品层已经落下第一批 facade 入口：

- `app.js`
- `workbench/commands/registry.js`
- `workbench/bootstrap/workspace_bootstrap.js`
- `workbench/contracts/index.js`
- `preview/runtime/preview_bootstrap.js`
- `preview/runtime/editor_handoff.js`
- `preview/runtime/contracts/index.js`
- `workbench/solver/solve_workbench.js`
- `workbench/solver/demo_projects.js`
- `workbench/panels/solve_panel.js`

已有可复用的拆分前置模块包括：

- `adapters/editor_import_adapter.js`
- `ui/layer_session_policy.js`
- `ui/selection_presenter.js`
- `document_preview_fallback.js`
- `desktop_settings.js`

后续拆分应沿着这些现有 seam 继续推进，而不是重新造一套并行结构。

## 计划入口

- [Workbench 拆分计划](../../docs/VEMCAD_WORKBENCH_SPLIT_PLAN.md)
- [验证计划](../../docs/VEMCAD_VERIFICATION_PLAN.md)
- [模块设计](../../docs/VEMCAD_MODULE_DESIGN.md)
- [架构概览](../../docs/ARCHITECTURE.md)
- [Workbench 目标目录说明](./workbench/README.md)

## 目标目录

当前约定的产品层落点如下：

- `apps/web/workbench/`
- `apps/web/preview/`
- `apps/web/shared/`

其中 `apps/web/workbench/` 是 Phase 2 Web workbench 拆分的主要承接目录。
`apps/web/app.js` 是当前产品层模式切换和 bridge contract 的落点。

## 迁移约束

- 新增产品级命令逻辑，不再默认直接追加到 `command_registry.js`。
- 新增 UI wiring / panel orchestration，不再默认直接追加到 `workspace.js`。
- 新增 preview 与 desktop bridge 规则，不再默认直接追加到 `preview_app.js`。
- 新增 solver 诊断 / solve action state，不再默认直接追加到 `workspace.js`。
- 迁移期优先经由 `apps/web/*` facade 暴露稳定入口，再逐步替换 legacy 依赖。
- 迁移期优先保持旧入口兼容，等模块边界稳定后再做物理挪动到 `apps/web/*`。
