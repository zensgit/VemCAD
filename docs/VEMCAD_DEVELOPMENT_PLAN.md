# VemCAD 开发推进计划

> **执行现状与治理（2026-05-29）** — 进度、风险登记与排序建议见
> [`VEMCAD_PLAN_PROGRESS_STATUS_20260528.md`](./VEMCAD_PLAN_PROGRESS_STATUS_20260528.md)（living register）。
> 两点事实需先知道：(1) **Phase 2/3 的真实拆分发生在 `deps/cadgamefusion` 子模块内**，每步是
> CADGameFusion PR + VemCAD gitlink 指针 bump（A→C 发布纪律），不是纯产品仓文件重构——按此估算成本。
> (2) 一次对抗评审判定本方案 **sound-with-fixable-gaps**（架构扎实，缺口在交付管线+排序）；其中排序建议
> （如 P4 先于 P2、推迟 fillet/chamfer）为**建议、待 owner 拍板**，下方 P0–P5 优先级尚未更改。

## 执行收口状态（2026-05-30）— 已完成 / 暂不做 / 触发条件

> 本节是顶层 roadmap 的当前状态快照；细节见各 development/verification/scoping 文档与
> [`VEMCAD_PLAN_PROGRESS_STATUS_20260528.md`](./VEMCAD_PLAN_PROGRESS_STATUS_20260528.md)（living register）。
> 下方 P0–P5 原文为参考路线，以本节为最新执行事实。

**当前钉点**：VemCAD `main` 子模块指针 = CADGameFusion `711c005`（含 web_viewer golden +
glob 门禁 + 路由 `/manifest`）；`services/router` launcher 已在 main。

### ✅ 已完成（在 main、CI 验证）

- **P0 冻结边界** / **P1 Project Runtime + v1 求解器**（PR #2–#6，该线已 milestone 收口）。
- **规划文档 + 已验证 web WIP 落盘**（#11/#12）——此前是 untracked，现已版本控制。
- **产品 CI 可见性**：root `package.json` + `product_tests`（`core` 无 PAT/无子模块 + `web-integration`）（#13）。
- **方案体检（sound-with-fixable-gaps）+ 治理修订**：A→C 子模块成本、需求驱动重排（建议）、
  "VERIFICATION = 门禁非 run-log" 定义、§7 风险登记。
- **上帝文件 golden 网 + 门禁**：command_registry / workspace / preview 三批 characterization golden，
  且 CADGameFusion 4 个 runner 改 glob → 门禁全部 714 个 web_viewer 测试（CADGameFusion #378–#381 →
  VemCAD 指针 bump #14/#15/#18）。**这是 P2 拆分的前置安全网。**
- **P4 参考 router 契约零缺口**：`GET /manifest/{task_id}`（CADGameFusion #382 → bump #18）。
- **P4 phase 1 薄 router launcher**：`services/router/{launcher,main}.mjs` + 纯 node lifecycle 测试（进 core）
  + review-found orphan bug 修复（#19）。
- **决策文档**：P4 产品化 scoping（#17）、Electron-dedup scoping + 决策（#20）。

### ⏸️ 暂不做（明确 park，按 owner 决定）

- **P2 上帝文件物理拆分**（12.8k 行）——有网了，但**需求驱动触发**，不投机式全量拆；fillet/chamfer 等推迟。
- **P3 desktop shell 收敛**（壳在子模块，A→C）。
- **P4 云/多用户**（共享 DB / 真认证 / OAuth / 水平扩展）——部署目标 **= 桌面/本地单用户（frozen 2026-05-30）**。
- **P4 router 重写**（python→node）。
- **Electron 复用 launcher 去重**——直接 import 是层次反向；挂到 Phase 3（见 dedup 决策文档）。
- **P5 Qt 角色**（仅文档层，inspector/validator 定位不追加产品 UI）。
- **D1b**（CADGF-PROJ schema arity 2→4 / 一等 coincident）——需重开已收口的 solver 线。
- **OCCT / 3D**——被产品目标 gate（frozen 默认：2D 保真 + Web/云护城河；可逆）。

### 🔔 触发条件（满足才动）

| 项 | 触发 |
|---|---|
| P2 拆某域 | 某真实功能需要拆该域（如 solver 诊断 UI）；有 golden 网保护后按域最小切 |
| P4 转云 | 部署目标决策改变（出现云/多用户/协作的真实客户需求） |
| P3 / Electron dedup | desktop shell 收敛立项，或"重复真的造成一次漂移 bug" |
| D1b | 出现真实机械草图需求（radius/diameter/tangent/coincident） |
| OCCT | 产品明确要正面追 FreeCAD-height 3D（拿到 timeboxed POC 数据点后立项） |
| Electron cleanup escalation | 可选防御性小修，随时可做、非必需（真 router 默认 SIGTERM 大概率即终止） |

### 纪律（贯穿，不变）

从最新 `origin/main` 切独立 worktree；子模块改动走 A→C（CADGameFusion PR + gitlink-only 指针 bump +
`merge-base --is-ancestor` 护栏 + editor-light）；测试随代码、绿了再合；交付声明分级诚实（已合入 vs 仅验证文档 vs untested-by-construction）。

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
