# VemCAD 模块设计

## 文档目的

本文档基于当前仓库与工作区最新代码状态，给出一版适合 VemCAD 后续演进的模块设计方案。

重点不是重复现有实现，而是明确 4 件事：

1. VemCAD 的主产品边界应该如何划分。
2. CADGameFusion、Router、Web/Electron、Qt 各自应承担什么职责。
3. 官方工程模型、派生场景模型、会话快照、服务产物这几类文件应如何区分。
4. 接下来应按什么顺序推进，才能最大化复用当前代码。

## 研读范围与当前基线

本结论基于以下代码与文档：

- 顶层产品仓库：
  - `README.md`
  - `docs/ARCHITECTURE.md`
- `deps/cadgamefusion` 中的核心实现：
  - `core/include/core/*.h*`
  - `editor/qt/src/*`
  - `tools/web_viewer/*`
  - `tools/web_viewer_desktop/*`
  - `tools/plm_router_service.py`
  - `schemas/*.json`

同时，本文档也考虑了当前工作区中的未提交更新：

- `deps/cadgamefusion/editor/qt/src/canvas.cpp`
- `deps/cadgamefusion/editor/qt/src/mainwindow.cpp`
- `deps/cadgamefusion/plugins/dxf_libdxfrw_adapter.cpp`

这些更新说明最近主线重点仍然落在：

- Qt 原生画布 fidelity 提升
- DXF/DWG 导入表现修正
- HATCH、line weight、dash、extents 等 CAD 显示行为贴近 AutoCAD

## 当前代码现状判断

### 1. 顶层仓库仍是“产品意图仓库”，不是完全落地的产品实现仓库

顶层文档已经定义了目标分层：

- `apps/desktop`
- `apps/web`
- `services/router`
- `deps/cadgamefusion`

但当前真正持续演进的实现仍主要位于 `deps/cadgamefusion` 中，尤其是：

- Qt 编辑器
- Web workbench
- Electron 桌面壳
- Router 工具链

因此，VemCAD 目前更像“产品层设计 + 引擎/工具实现同仓并存”的状态。

### 2. CADGameFusion 已经具备“平台层”雏形

当前 CADGameFusion 已经具备作为平台层的几个关键条件：

- 稳定 C ABI 边界：`core_c_api.h`
- 稳定插件 ABI：`plugin_abi_c_v1.h`
- 导入导出插件机制
- `Document` 级场景模型
- 路由、转换、预览工具链

这意味着它非常适合被定义为：

- 几何与导入导出平台
- 跨客户端共享的底层能力提供者

而不适合继续同时承担全部产品层职责。

### 3. Qt 线正在强化“高保真导入/审阅”，但还不是完整工程编辑主线

最近代码显示 Qt 线提升明显：

- 导入链会复制更完整的实体与属性
- 画布支持：
  - Text
  - Ellipse
  - line type
  - line weight
  - hatch 显示策略
  - clip extents
  - Y-flip 画布行为

但 Qt 当前仍存在明显边界：

- `CanvasWidget::reloadFromDocument()` 只把 `Polyline` 进入交互缓存
- hit-test 主要仍围绕 `Polyline`
- 多数命令仍以 polyline 变换为中心
- `Project::save/load()` 仍只完整覆盖 polyline

因此 Qt 当前最合理的定义不是“唯一主工作台”，而是：

- 原生高保真导入审阅器
- 导入质量诊断与验证工具
- 桌面原生 CAD fidelity 客户端

### 4. Web/Electron 线更接近真正的产品工作台

当前 Web workbench 已经具备完整工作台骨架：

- `DocumentState`
- `SelectionState`
- `SnapState`
- `ViewState`
- `CommandBus`
- `ToolRegistry`
- `PropertyPanel`
- `LayerPanel`
- `SolverActionPanel`

同时，Web 侧已经承载大量产品逻辑：

- 命令系统
- 撤销重做
- source group / insert group 工作流
- 属性编辑
- 选择语义
- 导入 provenance
- solver bridge

Electron 桌面壳则进一步承接：

- 文件打开
- 最近文件
- 本地 Router 自启动
- 打包运行时资源探测

因此，从“主产品工作台”角度看，Web/Electron 明显比 Qt 更接近主线。

### 5. 当前最大缺口仍然是“官方工程模型”没有真正独立出来

现在至少存在 4 类不同语义的数据：

1. `CADGF Document`
2. `CADGF-PROJ`
3. `vemcad-web-2d-v1` session/snapshot
4. Router artifact manifest

问题不在于格式多，而在于职责尚未完全钉死。

当前最缺的一层是：

- `Project Runtime`

也就是：

- sketches
- constraints
- parameters
- feature tree
- rebuild dependency
- solver integration

这一层不能继续分散在：

- `Document`
- solver bridge
- 前端状态模型
- 各种导入导出中间脚本

## 推荐总体架构

建议将 VemCAD 设计为如下 4 层结构：

```text
VemCAD
├─ Product Runtime
│  ├─ Project Runtime
│  ├─ Scene Runtime
│  └─ Collaboration Meta
├─ Core Platform (CADGameFusion)
│  ├─ core_c ABI
│  ├─ Document / geometry / plugin ABI
│  └─ import/export / converter toolchain
├─ Client Surfaces
│  ├─ Web/Electron Workbench
│  └─ Native Qt Inspector
└─ Router Services
   ├─ conversion
   ├─ artifact delivery
   └─ project/document/version history
```

### 核心原则

- `CADGameFusion` 做平台，不做完整产品前台。
- `Web/Electron` 做主工作台。
- `Qt` 做原生高保真审阅与导入验证端。
- `Router` 做独立服务层。
- `Project Runtime` 作为官方工程模型内核，必须独立出来。

## 模块职责设计

## 1. Platform Core

### 定义

由 `deps/cadgamefusion` 提供的底层平台能力。

### 职责

- 稳定 C ABI
- 稳定插件 ABI
- `Document` 场景模型
- 几何基础能力
- 导入器/导出器
- 转换 CLI
- mesh/export pipeline

### 不应承担的职责

- 产品级工程语义
- 项目版本与协作逻辑
- 主工作台 UI 状态
- 会话级编辑器临时状态

### 结论

应将其正式视为平台层，而不是继续把它当作“产品仓库主体”。

## 2. Project Runtime

### 定义

VemCAD 的官方工程内核。它是未来真正的单一业务真相来源。

### 职责

- sketch entities
- constraints
- parameters
- feature tree
- resources
- rebuild dependency graph
- solver binding
- project persistence
- migration/versioning

### 关键输出

- 派生 `Scene Runtime`
- 导出 `CADGF Document`
- 导出 solver project

### 当前状态

当前这层只存在于若干散落的部件中：

- `schemas/project.schema.json`
- `core/include/core/solver.hpp`
- `tools/solve_from_project.cpp`
- Web 侧 solver bridge

### 设计要求

- 不再只做“solver 专用导出格式”
- 必须变成正式官方工程模型
- 支持 deterministic save/load/migration

## 3. Scene Runtime

### 定义

面向渲染、预览、导入交换的场景层。

### 核心模型

- `Document`
- layers
- entities
- text
- import provenance
- style/render metadata

### 职责

- 从导入器直接生成 scene
- 从 `Project Runtime` 派生 scene
- 为 Web/Qt/Router 提供统一场景输入
- 为 glTF/mesh/export 提供统一基础

### 设计要求

- 它是派生场景，不是官方工程源文件
- 应继续复用当前 `Document` 能力
- 应避免承担参数化工程语义

## 4. Router Service

### 定义

转换、产物分发、项目/文档/版本历史服务。

### 职责

- 任务提交与排队
- conversion execution
- artifact manifest 生成
- `document.json` / glTF / metadata 分发
- project/document/version 查询
- annotation 历史
- local/remote 统一 API

### 当前代码信号

`plm_router_service.py` 已经不只是简单转换脚本，而是在向服务化管理靠拢：

- task queue
- history
- project list
- document list
- versions
- annotation event
- metrics

### 设计要求

- 保持独立部署能力
- 本地桌面与云端共用协议
- 从仓库结构上最终独立为单独服务仓库

## 5. Web Workbench

### 定义

VemCAD 的主产品工作台。

### 职责

- 编辑器主界面
- 命令系统
- 属性系统
- 图层系统
- 选择系统
- source group / insert group 工作流
- solver action surface
- session 级状态持久化

### 当前优势

- 已有完整工作台骨架
- 产品交互语义最丰富
- 测试数量最多
- Electron 可直接承接桌面产品形态

### 当前问题

- 领域逻辑过度集中
- `command_registry.js` 过大
- `workspace.js` 过大
- 工程模型仍未从 session/document 中抽离

### 设计方向

继续作为主前台，但要按领域拆包：

- file/import/export
- selection
- transform
- layer/style
- annotation/source-group
- insert-group
- solver

## 6. Desktop Shell

### 定义

Electron 桌面壳。

### 职责

- 打开文件
- 文件关联
- recent files
- packaged runtime
- local router auto-start
- native save/open bridge

### 设计要求

- 尽量薄
- 避免继续吸收业务规则
- 业务逻辑应尽量回到 Web Workbench 或 Router Client

## 7. Native Qt Inspector

### 定义

高保真原生 CAD 导入审阅与验证端。

### 职责

- 导入 fidelity 验证
- 原生画布显示
- DXF/DWG 行为对照
- 渲染回归基线
- 审阅与诊断

### 不建议承担的职责

- 官方工程编辑主线
- 唯一正式产品 UI
- 官方工程文件主存储

### 原因

当前 Qt 强于导入显示 fidelity，弱于全实体一致编辑和正式工程持久化。

## 8. QA / Regression

### 定义

独立的一等能力，而不是附属脚本集合。

### 职责

- DXF/DWG 样本集
- Web smoke
- Electron smoke
- Qt fidelity tests
- artifact validation
- golden baseline

### 设计要求

- 统一按“产品流”组织验证
- 明确覆盖：
  - import fidelity
  - project roundtrip
  - router artifacts
  - workbench editing flow

## 文件与数据模型边界

这里必须明确 4 种数据的角色。

## 1. VemCAD Project

### 角色

官方工程源文件。

### 内容

- project metadata
- sketches
- constraints
- parameters
- feature tree
- resources
- rebuild inputs

### 要求

- 人可读
- 可迁移
- 有 schema
- deterministic ordering
- 可做版本比较

### 结论

它才是未来唯一的“工程真相来源”。

## 2. CADGF Document

### 角色

派生场景文件与交换文件。

### 内容

- layers
- entities
- metadata
- settings
- import provenance
- render/export 所需信息

### 用途

- Router 产物
- Viewer 输入
- 导入交换
- 场景派生输出

### 结论

它不是官方工程源文件。

## 3. Workbench Session

### 角色

临时会话快照。

### 内容

- selection
- snap
- view
- tool state
- panel state

### 用途

- 本地恢复
- session cache
- 编辑器状态暂存

### 结论

不能继续承担正式工程语义。

## 4. Artifact Manifest

### 角色

服务产物描述文件。

### 内容

- `document_json`
- `mesh_gltf`
- metadata
- hashes
- provenance
- viewer URL

### 用途

- Router 输出
- 预览分发
- 验证与下载

### 结论

只属于服务交付层。

## 推荐主数据流

## 1. 导入流

```text
DWG/DXF
-> Importer / Router / Plugin
-> CADGF Document
-> Web Workbench / Qt Inspector
```

## 2. 编辑流

```text
VemCAD Project
-> Project Runtime
-> Scene Runtime
-> CADGF Document
-> Workbench View
```

## 3. 求解流

```text
Workbench edits
-> Project Runtime constraints / params
-> Solver
-> Rebuild
-> Scene Runtime refresh
-> Document refresh
```

## 4. 发布流

```text
Project / Document
-> Router / Exporter
-> manifest + document.json + glTF + metadata
```

## 推荐仓库结构

推荐目标结构如下：

```text
vemcad/
├─ apps/
│  ├─ workbench-web/
│  ├─ desktop-shell/
│  └─ native-inspector/
├─ packages/
│  ├─ project-runtime/
│  ├─ scene-runtime/
│  ├─ router-client/
│  ├─ cadgf-bridge/
│  └─ file-formats/
├─ services/
│  └─ router/
├─ schemas/
│  ├─ vemcad-project.schema.json
│  ├─ cadgf-document.schema.json
│  └─ artifact-manifest.schema.json
├─ qa/
│  ├─ fixtures/
│  ├─ baselines/
│  └─ smoke/
└─ deps/
   └─ cadgamefusion/
```

## 分阶段演进建议

## Phase 0：先把边界钉死

目标：

- 统一命名和职责
- 不急着大规模搬代码

动作：

- 正式定义：
  - `VemCAD Project`
  - `CADGF Document`
  - `Workbench Session`
  - `Artifact Manifest`
- 明确 Qt = `Inspector`
- 明确 Web/Electron = `Workbench`

成功标志：

- 团队对“哪个文件才是官方工程文件”没有歧义

## Phase 1：抽出 Project Runtime

目标：

- 从当前分散实现中抽出工程内核

动作：

- 将约束、参数、feature tree、solver bridge 收敛到统一 runtime
- 让 `Project -> Document` 成为正式派生流程
- 让 `CADGF-PROJ` 从“solver bridge only”升级为官方工程模型基础

成功标志：

- Web、Qt、CLI 不再各自维护不同的工程状态语义

## Phase 2：工作台模块化

目标：

- 把 Web 工作台从大文件逻辑中解耦

动作：

- 拆 `command_registry.js`
- 拆 `workspace.js`
- 按领域建立模块边界
- 抽 Router client SDK

成功标志：

- 工作台逻辑按领域可独立演进

## Phase 3：Router 正式服务化

目标：

- 让本地与远端部署共享一套服务契约

动作：

- 固化 Router API
- 固化 artifact manifest
- 固化 project/document/version/history/annotation 能力
- 视需要将 `services/router` 拆到独立仓库

成功标志：

- 本地桌面与远端部署模式只在部署方式不同，不在业务协议不同

## 当前最重要的设计决策

## 决策 1

`CADGameFusion` 是平台层，不是完整产品层。

## 决策 2

`Web/Electron` 是主工作台，`Qt` 是高保真原生审阅端。

## 决策 3

`VemCAD Project` 必须成为唯一官方工程源文件。

## 决策 4

`CADGF Document` 是派生场景，不再承担官方工程语义。

## 决策 5

Router 不只是 converter，而是产品服务层的一部分。

## 当前工作区特别说明

当前工作区中还有一些局部调试/未提交变更需要特别谨慎：

- Qt 导入后存在固定 extents 缩放覆盖逻辑
- 这类逻辑更像针对样例图纸的调试，不建议固化为正式产品默认行为

在后续进入产品化阶段时，应避免将这类样例特化逻辑误升格为产品设计。

## 结论

按当前最新代码，VemCAD 最合理的整体设计是：

- `CADGameFusion` 做平台
- `Project Runtime` 做官方工程内核
- `Scene Runtime / CADGF Document` 做派生场景
- `Web/Electron` 做主产品工作台
- `Qt` 做原生高保真审阅与导入验证端
- `Router` 做独立服务与产物分发层

这条路线的优势是：

- 最贴合当前代码事实
- 最大化复用已有资产
- 避免 Qt / Web 双主线内耗
- 为后续协作、版本、云端部署保留清晰边界
