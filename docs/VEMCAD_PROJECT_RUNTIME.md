# VemCAD Project Runtime

## 文档目的

本文档定义 `apps/runtime` 的职责边界与目录骨架，确保 VemCAD 后续在实现 `Project Runtime` 时，不再把工程语义继续分散到：

- `CADGF Document`
- Workbench 前端状态
- solver bridge
- router 中间产物

本文档重点回答 5 个问题：

1. `Project Runtime` 负责什么，不负责什么。
2. 需要先固定哪些核心对象。
3. 它的输入输出边界是什么。
4. 它与 `CADGF Document` 的关系是什么。
5. 推荐按什么顺序落地实现。

## 定位

`Project Runtime` 是 VemCAD 的官方工程模型内核，位于产品层与 CAD 平台层之间。

它的目标不是替代 CADGameFusion，而是把产品级工程语义稳定地收敛在一层独立 runtime 中：

- 向上承接：
  - `apps/web`
  - `apps/desktop`
  - `services/router`
- 向下输出：
  - `CADGF Document`
  - 求解输入
  - 可用于预览、导出、转换的场景结果

因此，`Project Runtime` 应被视为：

- `VemCAD Project` 的唯一真相来源
- feature / constraint / rebuild 的唯一语义归属
- `CADGF Document` 的派生生产者

## 职责

### 1. 官方工程模型

- 定义 `VemCAD Project` 根对象、子对象和稳定 identity。
- 负责工程文件持久化、版本迁移、向后兼容和 deterministic save/load。
- 管理工程级元数据，例如单位、命名规则、引用和 rebuild 策略。

### 2. 参数与约束

- 定义参数、表达式、作用域和依赖关系。
- 定义约束对象、求解输入输出映射和诊断结果。
- 将求解失败、冲突、欠约束/过约束状态收敛为 runtime 级结果，而不是散落在前端组件里。

### 3. Feature Tree 与 Rebuild

- 定义 feature 的生命周期、依赖关系和执行顺序。
- 管理增量失效、重建传播、跳过策略和稳定重建结果。
- 让“工程变更 -> 场景变化”成为明确且可测试的 runtime 行为。

### 4. Scene Derivation

- 把 `VemCAD Project` 派生成 `CADGF Document`。
- 为预览、导出、转换和路由服务提供统一的场景生成入口。
- 管理派生缓存、稳定 scene id 和增量更新边界。

## 非职责

`Project Runtime` 不应承担以下职责：

- `CADGF` 的底层几何内核、插件 ABI、导入导出器实现
- Web/Electron/Qt 的界面状态、面板状态、视图状态和交互细节
- Router 的任务队列、HTTP 编排和产物分发
- 会话级临时状态，例如 selection、snap、camera、panel docking

这些职责继续分别归属：

- `deps/cadgamefusion`
- `apps/web`
- `apps/desktop`
- `services/router`

## 核心对象

建议首先固定以下对象族，而不是先堆命令和页面行为。

### 根对象

- `ProjectModel`
  - 官方工程根对象。
  - 持有项目元数据、对象索引、版本号和入口配置。
- `ProjectRevision`
  - 持久化快照的版本语义。
  - 用于迁移、回滚和兼容判断。

### 工程语义对象

- `ProjectSpace`
  - 工程中的逻辑工作空间或编辑上下文。
- `ParameterStore`
  - 参数定义、表达式、求值结果与依赖关系。
- `ConstraintSet`
  - 约束集合、求解输入、求解输出与诊断。
- `FeatureNode`
  - 单个 feature 的声明、输入引用、输出引用与失效状态。
- `FeatureGraph`
  - feature 之间的依赖图与 rebuild 顺序。

### 派生对象

- `RebuildPlan`
  - 一次重建的执行清单、顺序和失效范围。
- `SceneDerivation`
  - `ProjectModel` 到 `CADGF Document` 的派生过程定义。
- `DerivedScene`
  - 某次重建后生成的稳定场景结果。
- `RuntimeDiagnostic`
  - 参数、约束、feature、scene 派生过程中的统一诊断对象。

## 目录骨架

`apps/runtime` 建议按 4 个模块切分：

- `apps/runtime/project/`
  - `ProjectModel`
  - persistence
  - migration
  - identity / naming / revision rules
- `apps/runtime/constraint/`
  - parameters
  - expressions
  - constraints
  - solver binding / diagnostics
- `apps/runtime/feature/`
  - feature definitions
  - feature graph
  - rebuild invalidation / ordering
- `apps/runtime/scene/`
  - project -> `CADGF Document`
  - scene cache
  - derived ids / export-facing scene packaging

## I/O 边界

### 输入

`Project Runtime` 的输入应限制为“工程层意图”和“平台层结果”，而不是 UI 细节。

- 来自 `apps/web` / `apps/desktop`：
  - 新建工程
  - 加载/保存工程
  - 参数编辑
  - 约束编辑
  - feature 增删改
  - rebuild 请求
- 来自 `deps/cadgamefusion` 或导入链路：
  - importer 产出的几何/文档数据
  - scene 派生所需的平台对象
- 来自 `services/router`：
  - 批处理重建/导出请求
  - 项目版本选择与产物生成请求

### 输出

`Project Runtime` 的输出应是稳定且可复用的产品契约。

- `VemCAD Project` 持久化结果
- 参数/约束/feature 的查询视图
- `RebuildPlan` 与 `RuntimeDiagnostic`
- 派生后的 `CADGF Document`
- 面向预览、导出、转换链路的场景结果

### 明确不穿透的内容

以下内容不应直接进入 `Project Runtime` 核心模型：

- selection、hover、snap、camera 等会话状态
- 面板展开/折叠、工具栏状态、对话框状态
- Electron 文件对话框或最近文件列表
- Router 内部任务调度细节

## 与 CADGF Document 的派生关系

`Project Runtime` 与 `CADGF Document` 的关系必须明确为：

- `VemCAD Project` 是真相来源。
- `CADGF Document` 是派生产物。

这意味着：

1. 工程编辑首先修改 `ProjectModel`，而不是直接把 `CADGF Document` 当作工程真相。
2. `CADGF Document` 应可由 `ProjectModel` 重新生成，而不是依赖前端内存状态补全。
3. 预览、导出、转换、路由服务优先消费派生后的 `CADGF Document`。
4. 若发生 `CADGF Document` 与 `ProjectModel` 不一致，以 `ProjectModel` 为准重新派生。

推荐采用以下链路：

```text
VemCAD Project
  -> Parameter / Constraint Solve
  -> Feature Rebuild
  -> Scene Derivation
  -> CADGF Document
  -> preview / export / router artifacts
```

### 派生规则

- 派生过程必须尽量 deterministic。
- `CADGF Document` 可以被缓存，但缓存失效后必须可重建。
- 派生结果可以作为交换与渲染边界，但不反向替代工程文件。
- 导入得到的 `CADGF Document` 若要进入官方工程，应经过 runtime 归一化后写入 `ProjectModel`。

## 与其他层的协作边界

### 与 `apps/web`

- Web 负责命令组织、面板状态、交互流程。
- Runtime 负责工程规则、重建与查询结果。

### 与 `apps/desktop`

- Desktop 负责文件壳、原生对话框和本地运行时集成。
- Runtime 不吸收桌面壳逻辑。

### 与 `services/router`

- Router 负责远程或本地服务编排。
- Runtime 提供项目加载、重建和场景派生能力，不承担任务队列职责。

### 与 `deps/cadgamefusion`

- CADGF 提供底层文档、几何和导入导出平台能力。
- Runtime 在其上构建产品级工程语义，但不重写平台层 ABI。

## 阶段性实现顺序

建议按“先钉死真相来源，再补派生链路”的顺序推进。

### Phase 0: 文档与目录冻结

- 固定 `apps/runtime` 的目录骨架和术语。
- 明确 `VemCAD Project` 与 `CADGF Document` 的主从关系。
- 禁止继续把工程语义散落到 UI session 或临时脚本里。

### Phase 1: `project/` 基础落地

- 定义 `ProjectModel`、`ProjectRevision`、稳定 id 规则。
- 建立 save/load、schema version 和 migration。
- 先保证“官方工程文件”独立成立。

### Phase 2: `constraint/` 落地

- 收敛参数、表达式、约束对象。
- 固定 solver binding 输入输出。
- 建立统一诊断对象，避免错误状态分散在各层。

### Phase 3: `feature/` 落地

- 建立 `FeatureNode`、`FeatureGraph`、`RebuildPlan`。
- 明确失效传播和增量 rebuild 规则。
- 让工程语义真正具备可重复重建能力。

### Phase 4: `scene/` 落地

- 实现 `ProjectModel -> CADGF Document` 的统一派生入口。
- 固定 scene cache、derived id 与 invalidation。
- 让 preview/export/router 全部消费同一种派生结果。

### Phase 5: 客户端与服务集成

- 让 `apps/web` 从直接操纵场景状态，迁移到调用 runtime。
- 让 `apps/desktop` 只保留壳职责。
- 让 `services/router` 以 runtime + CADGF 作为后台实现边界。

## 当前目录骨架的意义

本次仅建立 `apps/runtime` 的提交骨架，不提前假设具体语言、框架或序列化格式。

当前目录的作用是先固定模块职责：

- `project/` 管工程真相
- `constraint/` 管求解语义
- `feature/` 管重建语义
- `scene/` 管派生场景

后续无论实现落在 TypeScript、C++ bridge 还是混合层，均应遵守本文件定义的职责与边界。
