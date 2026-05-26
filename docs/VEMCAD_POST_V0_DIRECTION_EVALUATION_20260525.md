# VemCAD post-v0 方向评估

- 状态：**决策已拍板（frozen 2026-05-25），进入 Tier 1 规格阶段**
- 日期：2026-05-25
- 前置：Project Runtime v0 已合入 `origin/main`（PR #2，squash `842fb56`）
- 关联：`docs/VEMCAD_PROJECT_RUNTIME_V0_DEVELOPMENT_20260525.md`、`docs/VEMCAD_MODULE_DESIGN.md`

## 文档目的

v0 落地后，决定下一步走向。本文不是实现计划，而是**决策框架**：先钉清"哪个是产品目标决策、哪个是无悔之举、哪个是高风险探针"，再谈动工。核心结论先行：

- **`Project Runtime v1`（接 2D 约束求解器）= post-v0 第一探针**，无悔之举（两种产品目标下都有价值）。
- **OCCT 3D POC 仅在产品明确要正面追 "FreeCAD-height 3D" 时触发**，且只做 timeboxed go/no-go。
- 这两条不在同一根轴上：前者巩固/延伸现有护城河；后者开辟与 FreeCAD 强项正面竞争的新战线。

## 决策 1（唯一 gate OCCT 的决策）：产品目标

| 目标 | 含义 | 代价 | 与现状关系 |
|---|---|---|---|
| **2D 保真 + Web/云护城河** | 深耕 DXF/DWG 保真、Web 工作台、服务化转换/协作 | 周-月级、低风险、复用 v0 | FreeCAD 的弱项；VemCAD 现有强项 |
| **FreeCAD-height 3D** | 参数化实体建模（sketch→feature→solid） | **年级、范畴性**：必须上 OCCT 或商业内核（Parasolid/ACIS） | 正面进 FreeCAD 最强区 |

**关键**：下面 Tier 1-3 在**两个目标下都做**；**只有 Tier 4（OCCT）被决策 1 gate**。因此决策 1 不必阻塞 v1 起步。

## 共同前置（任一方向都需要）

吃透 `v0 Runtime / Web workbench / Router` 三者边界与数据流，避免把产品规则继续堆进 Web 大文件或让 Runtime 耦合编辑器内部形状（v0 已立的原则）。

## 路线分层（最终排序）

### Tier 1 — Project Runtime v1：接 2D solver 探针 + Router `/solve` 契约（合并评估与实现）

把 v0 的 `constraints[]`/`features[]` 桩位从 no-op 升为"可参数化工程真相来源"。

**架构定调（已拍板 2026-05-25）：约束是真相，几何是派生。**
- 持久化真相 = `entities + constraints`（确定、可 golden）；解出的几何 = **rebuild 步重算的派生物**（`feature/index.js` 现在的 no-op `buildRebuildPlan` 即其槽位：v1 让 "rebuild = 跑 solver"）。
- 收益：解出坐标**不作为真相持久化** → 跨平台数值差异不污染保存文件、不破坏 v0 确定性 save 契约；且这正是 FreeCAD 的做法（草图加载即重解）。
- **已拍板 ②（约束为真相、几何派生）**：真相只存约束，几何在加载/rebuild 重解。**「持久化解出几何」= rejected**——仅可作 scene/derive 层的**非权威缓存**（随约束变更失效、永不读作真相、不进 golden/确定性契约），不进入 Project 真相格式。

**v1 可行性 checklist（动工前必核，含已知约束）：**

| 项 | 实测/结论 |
|---|---|
| (a) solver API 边界 | **不在 C ABI**（`core_c_api.h` 无 solver）；C++ only。现成可调边界是 **`tools/solve_from_project.cpp` CLI**（吃 `project.json`、`--json` 出 `SolveResult`/analysis/action-panel）。 |
| (b) 约束→schema 映射 | solver 吃的是 **CADGameFusion 的 CADGF-PROJ**（`scene.entities/constraints/parameters`，约束 ref 形如 `p1.x` 的 `VarRef{id,key}`），**≠** VemCAD 顶层 `VEMCAD-PROJECT`。**必须写 `Runtime → solver-project` adapter + 把 `SolveResult` 回写 Runtime 几何**——不能把 v0 文件直接丢给 CLI。这与 S4/S5 的 `VEMCAD-PROJECT ↔ CADGF Document` 是**同款 adapter 模式**，复用已验证纪律。 |
| (c) 确定性/数值稳定 | **同机重复输出字节一致（实测）；跨平台/重建确定性待专门测。** 若采纳"几何为派生"，门槛从"持久化跨平台字节一致"降为"单次求解容差内可复现"。 |
| (d) 调用路径 | 既无 ABI/WASM 边界，**最便宜路径 = 服务端走 CLI（经 Router）**。**但 CLI 非即插即用**：本地构建 binary 有旧 `@rpath`，需 `DYLD_LIBRARY_PATH` 才能找到 `libcore.dylib` → **v1 范围含"让 solver binary 可部署"子任务**（修 rpath / 静态链接 / 容器化）。WASM/浏览器内是后续优化。 |

**探针内部排序（先本地、后服务）：** 先在本地/测试跑通 `Runtime → CADGF-PROJ adapter → 本地 CLI → 回写 → re-derive` 这一环（验证映射 + 单次确定性 + 回写），**再**加 Router `/solve` 端点。最risk的未知（映射、确定性、回写）前置。

### Tier 2 — Web workbench 拆分

由 v1 的 solver 状态/诊断（DOF / 冲突 / 冗余 / action-panel，见 `solver.hpp` 的 `ConstraintAnalysis`/`SolveResult`）**驱动**该从 `command_registry.js`/`workspace.js` 抽什么——让集成需求告诉你拆什么，而非投机性拆分。

### Tier 3 — Router 契约固化

`/solve` 分**两层**，否则会把 CLI 的部署脆弱性泄漏给产品 API：

- **prototype（Tier 1 内）**：允许 shell-out CLI（最便宜），只为验证可行性。
- **stable（本 Tier）**：必须满足下列**验收清单**（v0 里 S6 的对应物——不达标不算"产品 API"）：
  - binary discovery、rpath / library path（解决 v1 实测的 `@rpath`/`DYLD_LIBRARY_PATH` 脆弱）
  - timeout、取消 / 长任务中断
  - stdout JSON 上限、stderr 捕获、exit code → 错误码映射
  - 输入校验（shell-out 前先验 solver-project 合法）
  - **solver 版本 / 算法 / 容差钉死**（几何为派生、每次重解 → 必须可复现）
  - 并发隔离
- **此处决定 shell-out vs C ABI**：稳定契约可评估把 solve 暴露进 C ABI（Router 同库内进程调用、更稳、为 WASM 铺路），从根上规避 shell-out-to-binary 的打包/子进程脆弱。

### Tier 4 — OCCT 3D POC（被决策 1 gate）

仅当决策 1 选 "FreeCAD-height 3D" 才触发，且**只做 timeboxed go/no-go 探针**，回答一个问题：
> 能否在**不动摇现有 2D 核心**的前提下，让 `Sketch → Extrude → Boolean → STEP export` 走通一条 OCCT 绑定（藏在现有 `core_c` C ABI 之后）？

跑通 → 拿到集成成本/风险真实数据再立项；跑不通 → 廉价止损。**在拿到这个数据点前，不把 OCCT 设为关键路径并投入。** 注：2D 草图求解（Tier 1）本就是 3D 特征建模的前置，故 v1 在 3D 路线上也不浪费。

## 证据点（grounding）

- `VarRef{id,key}` + solver 算法：`deps/cadgamefusion/core/include/core/solver.hpp`（VarRef @ line 9）
- CLI 入口 + `--json`：`deps/cadgamefusion/tools/solve_from_project.cpp`（usage @ line 19；读 `scene.entities/constraints` @ ~line 133）
- solver 输入 schema（CADGF-PROJ）：`deps/cadgamefusion/schemas/project.schema.json`
- v0 constraint 明确 no-op：`apps/runtime/constraint/index.js`
- Router 契约尚无 `/solve`：`services/router/CONTRACT.md`
- v1 adapter 可复用的同款模式：`apps/runtime/scene/index.js`（`deriveCadgfDocument`/`importProjectFromCadgfDocument`）

## 冻结前提（已拍板 2026-05-25）

1. **产品目标 = 2D 保真 + Web/云护城河（默认）**。OCCT 不启动，仅保留 Tier 4 的 timeboxed POC 触发条件。**可逆默认**：出现具体 3D 需求/客户即触发，不是永久封死。
2. **几何持久化 = 只存约束、加载/rebuild 重解**。「持久化解出几何」rejected → 仅可作非权威缓存（见 Tier 1）。
3. **solve 路径 = 探针 CLI shell-out；稳定契约再评估 C ABI/进程内**（见 Tier 3 两层 + 验收清单）。

## 备注

- 本文档为新增、未跟踪；不在任何已提交栈里，未触碰当前脏工作区。后续如需纳入版本库，建议从**更新后的 `origin/main`** 切新分支提交（勿用已 stale 的本地 `docs/project-runtime-v0`）。
