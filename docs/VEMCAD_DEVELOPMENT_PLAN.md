# VemCAD 开发推进计划

> **执行现状与治理（2026-05-29）** — 进度、风险登记与排序建议见
> [`VEMCAD_PLAN_PROGRESS_STATUS_20260528.md`](./VEMCAD_PLAN_PROGRESS_STATUS_20260528.md)（living register）。
> 两点事实需先知道：(1) **Phase 2/3 的真实拆分发生在 `deps/cadgamefusion` 子模块内**，每步是
> CADGameFusion PR + VemCAD gitlink 指针 bump（A→C 发布纪律），不是纯产品仓文件重构——按此估算成本。
> (2) 一次对抗评审判定本方案 **sound-with-fixable-gaps**（架构扎实，缺口在交付管线+排序）；其中排序建议
> （如 P4 先于 P2、推迟 fillet/chamfer）为**建议、待 owner 拍板**，下方 P0–P5 优先级尚未更改。

## 文档目的

在 `docs/VEMCAD_MODULE_DESIGN.md` 的总体判断基础上，把建议收敛成可以逐步执行的开发路线，避免架构结论停留在原则层。

本文档回答 4 个问题：

1. 当前仓库里哪些代码已经可以作为主线复用。
2. 接下来应该先拆什么，后拆什么。
3. 每个阶段的产物、边界和风险是什么。
4. 什么工作不该继续堆到当前模块里。

## 当前基线

### 已经适合继续复用的部分

- `deps/cadgamefusion/core/include/core/core_c_api.h`
  - 已经形成稳定 C ABI 边界。
- `deps/cadgamefusion/core/include/core/plugin_abi_c_v1.h`
  - 插件 ABI 已经足够支撑 importer/exporter 平台化。
- `deps/cadgamefusion/tools/convert_cli.cpp`
  - 转换链路已经是独立工具形态。
- `deps/cadgamefusion/tools/plm_router_service.py`
  - Router 已具备任务队列、产物分发和历史管理雏形。
- `deps/cadgamefusion/tools/web_viewer/state/documentState.js`
  - Web 工作台已有完整状态模型。
- `deps/cadgamefusion/tools/web_viewer/commands/command_bus.js`
  - 命令总线和撤销重做模型已经可复用。
- `deps/cadgamefusion/tools/web_viewer_desktop/main.js`
  - Electron 桌面壳已经覆盖文件打开、Recent Files、Router 自启动和 packaged runtime。

### 当前主线的真实问题

- `apps/web`、`apps/desktop`、`services/router` 仍是产品层占位目录，真实实现主要还在 `deps/cadgamefusion`。
- Web 侧产品复杂度已明显集中在大文件：
  - `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
  - `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`
  - `deps/cadgamefusion/tools/web_viewer/preview_app.js`
- Qt 仍偏“高保真审阅/验证端”，不是完整工程编辑主线：
  - `deps/cadgamefusion/editor/qt/src/project/project.cpp` 的保存/加载仍只完整覆盖 `Polyline`。
- 官方工程模型仍未独立：
  - `schemas/project.schema.json`
  - `core/include/core/solver.hpp`
  - `tools/solve_from_project.cpp`
  - Web solver bridge
  仍是分散状态，不是独立 `Project Runtime`。

## 开发原则

### 1. 主工作台唯一化

- 以 `web_viewer + web_viewer_desktop` 作为产品主线。
- Qt 保留为 fidelity inspector / regression client，不继续承担唯一正式产品 UI。

### 2. 工程模型与场景模型分离

- `VemCAD Project` 是唯一官方工程真相来源。
- `CADGF Document` 是派生场景与交换格式。
- Session Snapshot 只保存编辑器临时状态，不再充当正式工程文件。

### 3. 平台层与产品层分离

- `CADGameFusion` 只负责平台能力：
  - geometry
  - document
  - plugin ABI
  - importer/exporter
  - convert pipeline
- 产品规则收敛到 VemCAD 自己的 runtime / workbench / service contract。

### 4. 先收敛边界，再迁移目录

- 先明确职责、格式和 API。
- 再把实现从 `deps/cadgamefusion/tools/*` 逐步迁回 `apps/*` 和 `services/*`。
- 不建议一开始就做“大搬家”。

## 分阶段推进

## Phase 0: 冻结边界

### 目标

把“什么是官方工程文件、什么是派生场景、什么是 session cache”完全钉死。

### 产物

- 确认 `VemCAD Project` 为唯一官方工程格式。
- 明确 `CADGF Document` 只用于：
  - import/export
  - preview
  - router artifacts
  - scene interchange
- 明确 Workbench Session 只用于：
  - selection
  - snap
  - view
  - panel/tool state

### 不做的事

- 不在这一阶段改 Qt 交互主线。
- 不做大规模目录迁移。

## Phase 1: 建立 Project Runtime

### 目标

把当前散落在 schema / solver / 前端 bridge 中的工程语义收敛成独立 runtime。

### 建议模块

- `apps/runtime/project/`
  - project schema model
  - persistence / migration
  - deterministic save/load
- `apps/runtime/feature/`
  - feature tree
  - rebuild graph
- `apps/runtime/constraint/`
  - constraints
  - parameters
  - solver binding
- `apps/runtime/scene/`
  - project -> document 派生逻辑

### 阶段结果

- Workbench 不再直接把产品规则写进 `DocumentState`。
- `Project -> Scene(Document)` 变成明确导出关系。

## Phase 2: 拆解 Web Workbench 上帝模块

### 目标

保留当前 Web 主线，但把业务逻辑按领域收敛，避免继续向 `command_registry.js` 和 `workspace.js` 堆功能。

### 优先拆分对象

- `commands/command_registry.js`
  - 按 `file` / `selection` / `transform` / `layer-style` / `source-group` / `insert-group` / `solver` 拆分。
- `ui/workspace.js`
  - 保留组装层，剥离 command wiring、panel wiring、import/export wiring。
- `preview_app.js`
  - 与 editor/workbench 分离，避免 preview/editor 双模式继续混杂。

### 建议目录

- `apps/web/workbench/commands/`
- `apps/web/workbench/panels/`
- `apps/web/workbench/selection/`
- `apps/web/workbench/source-groups/`
- `apps/web/workbench/insert-groups/`
- `apps/web/workbench/io/`

## Phase 3: 收敛 Desktop Shell

### 目标

让 Electron 保持薄壳，不继续吸收业务规则。

### 保留在桌面壳的职责

- 文件打开/保存对话框
- recent files
- packaged runtime detection
- router auto-start
- native diagnostics export

### 回迁出桌面壳的职责

- 与编辑器语义强相关的流程判断
- 可在 Web workbench 表达的业务逻辑
- 可在 Router contract 表达的转换流程规则

## Phase 4: 独立 Router Contract

### 目标

让桌面本地运行与远端部署共享同一套 HTTP 契约。

### 需要固定的接口能力

- convert task submit
- task status
- artifact manifest
- health / readiness
- project/document/version list
- annotation history

### 目录目标

- 顶层 `services/router/` 成为真正产品服务入口。
- `deps/cadgamefusion/tools/plm_router_service.py` 最终退回平台工具或参考实现。

## Phase 5: Qt 角色收敛

### 目标

把 Qt 从“潜在主工作台”收敛到“高保真导入审阅和回归验证端”。

### 保留职责

- fidelity baseline compare
- import inspection
- native rendering regression
- diagnostic workflows

### 不再追加的方向

- 官方工程文件主存储
- 产品主编辑工作流
- 大量产品语义 UI

## 推荐目录落点

```text
VemCAD
├─ apps
│  ├─ runtime
│  │  ├─ project
│  │  ├─ feature
│  │  ├─ constraint
│  │  └─ scene
│  ├─ web
│  │  ├─ workbench
│  │  ├─ preview
│  │  └─ shared
│  └─ desktop
│     ├─ shell
│     └─ bridge
├─ services
│  └─ router
│     ├─ api
│     ├─ worker
│     └─ contract
├─ docs
└─ deps
   └─ cadgamefusion
```

## 优先级

### P0

- 冻结三类数据边界：
  - project
  - document
  - session
- 停止继续把产品规则直接堆进 `DocumentState` / `workspace.js` / `command_registry.js`

### P1

- 建立 `Project Runtime`
- 定义 `Project -> Document` 派生 API

### P2

- 拆 Web workbench 上帝模块
- 收敛 desktop shell

### P3

- Router 独立服务化
- Qt 角色正式降维为 inspector

## 风险与控制

### 风险 1: 目录迁移过早

控制方式：
- 先抽 API 和 contract，再迁实现。

### 风险 2: 新旧格式继续共存但无边界

控制方式：
- 所有入口必须标注读写哪一种文件。
- 所有导入导出流程必须明确 source of truth。

### 风险 3: Web 主线继续长成超大单体

控制方式：
- 新功能禁止直接追加到 `command_registry.js` 和 `workspace.js`，必须落在领域子模块。

### 风险 4: Qt 与 Web 产品语义再次分叉

控制方式：
- 只让两者共享 `Document` / import 结果 / regression fixtures，不共享产品主流程 ownership。

## 本阶段建议直接执行的工作

1. 以本文档为开发基线，不再把 VemCAD 设计目标仅停留在 `docs/ARCHITECTURE.md`。
2. 新增 `Project Runtime` 设计与接口草案文档。
3. 为 Web workbench 做一次按领域的文件拆分清单。
4. 为 Router 固定最小 HTTP contract。
5. 将 Qt 的产品定位正式改写为 inspector / validator。
