# VemCAD Project Runtime v1 — Tier 1 冻结规格：接 2D solver

- 状态：**规格冻结（评审通过 2026-05-25），进入 C 本地环探针**
- 日期：2026-05-25
- 上游决策：`docs/VEMCAD_POST_V0_DIRECTION_EVALUATION_20260525.md`（冻结前提）
- 地基：Project Runtime v0（`origin/main` @ `842fb56`）

## 目的与边界

把 v0 的 `constraints[]`/`features[]` 桩位升为"可参数化工程真相来源"：VEMCAD-PROJECT 经 adapter 喂给 cadgamefusion 的 2D 约束求解器，解出的几何作为**派生物**回写。本规格只定 **Tier 1 本地环探针**（prototype），不含 Router `/solve` 稳定契约（Tier 3）。

**复用 v0 纪律**：统一结果对象 `{ok,value,diagnostics}`、可注入 `clock`、确定性契约、schema 验收件、adapter 与 S4/S5 同款模式。

## 已读实情（grounding，决定规格的硬事实）

- **求解器输入格式 = CADGF-PROJ**（`deps/cadgamefusion/schemas/project.schema.json`）：`scene.entities` 是 `point{x,y}` + `line{p0,p1}`/`circle{center,radius}`/`arc{center,radius,startAngle,endAngle}`/`rect{p0,p1}`，**高阶实体用 point id 引用**。
- **VarRef = `"<entityId>.<key>"`**（schema `$defs.varRef` 正则 `^[^.]+\.[^.]+$`；CLI `solve_from_project.cpp` 按 `.` 切成 `{id,key}`）。
- **CLI 只把 `type=="point"` 映射成求解变量**（`solve_from_project.cpp:138-142`，仅 `id.x`/`id.y`）→ **v1 可解变量仅 point 坐标**；`circle.radius`/`arc.startAngle/endAngle` 是**固定 param、不参与求解**。
- **CLI 输出含解出的变量值**：`--json` 的 `out["vars"] = {"id.key": value}`（`solve_from_project.cpp:537-538`），外加 `ok/iterations/final_error/analysis`（DOF/冲突/冗余/jacobian rank/action_panels）。
- **求解参数**：`maxIterations=100`、`tolerance=1e-6`（`solve_from_project.cpp:175-176`）。
- **CLI 部署脆弱**：本地 binary 旧 `@rpath`，需 `DYLD_LIBRARY_PATH` 找 `libcore.dylib`（v1 范围含修复）。
- **单位枚举不同**：CADGF-PROJ 是 `mm/cm/m/inch/ft`（注意 `inch` 非 `in`）；VEMCAD-PROJECT 是 `mm/cm/m/in/ft` → adapter 须 `in→inch`。

## 冻结决策

### D1 — seed / evaluated 几何边界（核心）

**Project 真相 = sketch/topology + solver 变量 seed/初值 + constraints。** evaluated geometry 是派生缓存，**非权威真相**。

- **为什么 seed 必须是真相**：欠约束/多解草图有多个有效解，solver 靠**初值选解支**；不存 seed，重解会漂到不同分支（丢用户意图的分支）。FreeCAD 即此做法（草图存几何位置作求解初值）。
- **命名分开（强制）**：
  - **`seed`**：VEMCAD-PROJECT 里实体几何的当前值（point x/y、circle radius、arc angle…），作为 solver 初值与分支锚。**持久化、进 golden、是真相。**
  - **`evaluatedGeometry`**：解出后的坐标（来自 `out.vars`）。**派生缓存：随约束/seed 变更失效、永不读作真相、不进 golden/确定性持久化契约**；活在 scene/derive 层（如 CADGF Document），可不持久化或仅作可重算缓存。
- 求解一次后，可用 evaluated 更新 seed（下次以同解支重解）——但"更新 seed"是显式编辑动作，不是序列化副作用。

### D1b — VEMCAD constraint v1 vocabulary（Project 真相格式）

**Project 真相只存语义约束，不存 solver VarRef / 铸造 point id。** 否则真相会泄漏 solver 内部表示、与铸造 id 耦合，adapter 边界形同虚设。

- **constraint 记录**：`{ id, type, refs: [SemRef…], value? }`。`type` ∈ v1 支持集（见 D2）；`value` 仅 `distance`/`angle` 有。
- **SemRef（语义引用）= 对象 `{ entity: <vemcadEntityId>, at: <role> }`**——**v1 输入只接受对象形式**。紧凑串 `<entityId>@<role>` 仅作文档示意/未来兼容，**不作 v1 输入**（否则源 id 含 `@`/`.` 时又要引入一套转义——对象形式天然无分隔符问题）。role 按实体类型：line→`start`/`end`、circle→`center`、arc→`center`、rect→`p0`/`p1`、point→`self`。
- **每 type 的语义元数 + 精确展开顺序**：已由 C 第一刀**读 solver residual 钉死**——见[附录 — SemRef→VarRef 展开表](#附录--c-钉死semrefvarref-展开表源自-solvercpp-residual-1143-1207)。摘要（**v1 = 6 类**）：`horizontal`/`vertical` = **1 line 或 2 point**（equate 端点 y/x）；`distance` = 2 点（+value）；`parallel`/`perpendicular`/`angle` = 2 line（angle +value）。`equal` **不在 v1**（见风险/附录）。
- **展开（adapter 职责）**：每个 SemRef 经 `(entity,role) → 铸造 point → pointId.x/.y` 展开成 solver VarRef，按该 type 的 solver 期望顺序/arity 排列。Project 真相侧**只见 SemRef**。
- **v1 constraint 模块升级**（v0 仅校 id/排序）：增校 `type ∈ 支持集`、SemRef 的 `entity` 存在且 `role` 对该实体类型合法、SemRef 个数与 type 语义元数匹配；不合法 → `ok:false`/diagnostic。
- **原则**：semantic refs 是真相（稳定、可 golden、与 solver 解耦）；VarRef / 铸造 id 是 adapter 的 transient 产物。

### D2 — VEMCAD-PROJECT → CADGF-PROJ adapter（crux）

与 S4/S5 同款 adapter，但目标是 **CADGF-PROJ 求解格式**，结构变换更重（消费 D1b 的语义 refs，展开成 VarRef）：

- **实体分解（内联坐标 → 具名 point + 引用）**：
  - VEMCAD `line:[[x0,y0],[x1,y1]]` → 铸造 2 个 point（role `start`/`end`）+ CADGF-PROJ `line{p0,p1}` 引用它们。
  - `circle:{c:[cx,cy],r}` → 铸造 center point（role `center`）+ `circle{center,radius:r}`。
  - `arc`、`rect`、裸 `point` 同理（arc→`center`；rect→`p0`/`p1`；point→`self`）。
  - **铸造 point id = 确定性内部 id，与源 entity id 解耦、无 `.`**（按规范化后稳定顺序分配，如 `pt0/pt1/…`），并维护**可逆映射 `solverPointId ↔ (sourceEntityId, role)`** 供回写。
  - **不 reject project-valid id（已定，非二选一）**：源 entity id 可为任意非空字符串（含 `.`）——它**永不进 solver/VarRef 命名空间**（VarRef 正则 `^[^.]+\.[^.]+$` 以 `.` 为唯一分隔符，故内部 id 必须无点）。源 id 只活在可逆映射的一侧，靠确定性内部 id 隔离，无需 reject 或 escape 源 id。
  - **seed = 这些铸造 point 的 x/y**（取自 VEMCAD 实体几何）。
- **VarRef**：约束 ref 一律 `"<铸造pointId>.x"` / `"<铸造pointId>.y"`（铸造 pointId 无点，`.x`/`.y` 是唯一分隔点）。
- **constraints 支持集 = 6 类（schema ∩ solver 一致 + 语义对 CAD 自然，已实测）**：`horizontal`/`vertical`（无 value、2 refs）、`parallel`/`perpendicular`（无 value、8 refs）、`distance`（value+4 refs）、`angle`（value+8 refs）。**`equal` 已移出 v1**（solver 里只是标量 `a-b`，非等长/等半径；见风险 + 附录）。
  - **`coincident/concentric` 暂 BLOCKED**：CADGF-PROJ schema 定 **2 refs**，但 solver residual（`core/src/solver.cpp:1185/1191`）要 **≥4 refs**（x0,y0,x1,y1）→ 2 过 schema 但 solver 报 `WrongArity`、4 喂 solver 但过不了 schema。**解禁前提 = 先修 CADGF-PROJ schema 到 4 refs**。
  - **每种类型的 ref 顺序**由探针对照真实 solver + 已知良好 fixture **实测钉死**（schema 只定 arity 不定语义顺序，见验收）。
- **units**：`mm/cm/m/ft` 直通；**`in → inch`**（CADGF-PROJ 枚举是 `inch` 非 `in`）；未知 → `ok:false`。
- **范围内/外**：v1 只映射 point 坐标可解的约束。**不求解、标 diagnostic、passthrough 原几何（不丢）** 的有：引用 radius/angle 的约束、`coincident/concentric`（见上）、`ellipse/spline/block`；以及 **CADGF-PROJ 没有的 `text`（不求解）与 `polyline`**（v1 prototype 先 passthrough；将来可拆成 vertex points + segment 约束再纳入求解）。

### D3 — 求解调用（prototype，shell-out）

- 路径：写出 CADGF-PROJ json → `solve_from_project --json <file>` → 读 `out`。
- **可注入 solver runner**（默认 shell-out 到 CLI；测试可注入 fake），便于纯 Node 测试不依赖真 binary。
- binary 发现 + `DYLD_LIBRARY_PATH`/rpath 由 runner 封装；**solver 版本/`maxIter=100`/`tol=1e-6` 钉死并记录**（reproducibility 前提）。
- 这是 prototype；稳定 `/solve`（binary discovery/timeout/输入校验/版本容差钉死/并发隔离/可选 C ABI）属 **Tier 3**。

### D4 — SolveResult 回写语义

- `out.vars`（`{"<pointId>.x|y": value}`）→ 逆 adapter 映射回 VEMCAD 实体几何 → **evaluatedGeometry**（派生场景）。
- `out.analysis`（DOF estimate / structural_state / conflict / redundancy / action_panels）→ Runtime **诊断**（喂 Tier 2 的 UI 抽取）。
- `out.ok/iterations/final_error` → 求解状态。
- 回写**不覆盖 seed**（除非显式"以解出值更新 seed"动作）。
- **evaluated → derive 通道（显式，P2）**：S4 `deriveCadgfDocument(project)` 只读 `project.entities`(=seed)；evaluated 不进 Project，故用 **`buildEvaluatedProjectView(project, evaluatedGeometry)`** 产出**临时 project-view**（seed 被 evaluated 覆盖的只读副本）再喂现有 `deriveCadgfDocument`——**S4 签名不变**。此 view 是 **transient derive 输入，不是 save/load 真相**：永不序列化、不进 golden。（备选：给 derive 加 `{evaluatedGeometry}` option；选 view 方案因不改 S4、边界更干净。）

### D5 — rebuild = solve（feature 槽位）

v0 `feature/index.js` 的 no-op `buildRebuildPlan` 升级为"跑 solver"：`(entities seed + constraints) → solve → evaluatedGeometry → buildEvaluatedProjectView → deriveCadgfDocument`。constraints/seed 是真相，evaluated 是 rebuild 产物（经临时 view 进 derive，不持久化）。

### D6 — 确定性验收

- 同 seed + 同 constraints + 钉死的 solver 版本/maxIter/tol → 同 `out.vars`。**同机已实测字节一致；跨平台/重建待专门测**。
- 真相（seed+constraints）走 v0 既有确定性序列化/golden；evaluated **不进** golden（派生、可不可复现都不污染真相文件）。

## Tier 1 本地环探针（先本地、后 Router）

**先跑通这一环再碰任何服务化**：
```
VEMCAD-PROJECT → [D2 adapter] → CADGF-PROJ json
   → [D3 本地 solve_from_project --json] → out
   → [D4 回写] → evaluatedGeometry + diagnostics
   → [S4 deriveCadgfDocument] → 派生 CADGF Document
```

### 测试计划（已实现）

- 纯 Node（注入 fake solver runner，不依赖真 binary）：
  - `runtime_solverproject_adapter.test.js`（C1，16 用例）：VEMCAD-PROJECT → CADGF-PROJ 结构——point 铸造（dot-free 内部 id + 可逆映射）、6 类 VarRef 展开序、`in→inch`、arity；范围外/畸形实体与约束 → diagnostic 且不输出；半截 point / 坏 radius / 源 id 撞 `__pN` 等边界。
  - `runtime_solve_loop.test.js`（C2，8 用例）：固定 `out.vars` → evaluatedGeometry 逆映射；`buildEvaluatedProjectView` 不改 seed；`solveProject`/`solveAndDeriveScene` 本地环；**unsatisfied → ok:false + 保留 analysis、不回写/不 derive**；runner throw → `SOLVE_FAILED`。
- 独立验收（像 S6，不进 `node --test`）：`apps/runtime/tools/run_solver_acceptance.sh`
  - 用**真** `solve_from_project`（封 `DYLD_LIBRARY_PATH`）对 6 类各跑一遍，断言解满足约束（tol 内）+ `out.ok` + 同机可复现；跑完整 `solveAndDeriveScene`，派生的 CADGF Document 经 **`document.schema.json`** 校验；外加 1 个矛盾用例断言**正确拒绝 + 保留 analysis**。

### 验收判据（达成）

- 纯 Node 测试全绿（runtime **102/102**），不污染既有套件。
- 独立验收 **7/7**：真 solver 对 6 类解出满足约束、同机可复现；6 个派生 CADGF Document 过 `document.schema.json`；矛盾用例正确拒绝并保留 analysis。
- 每种 v1 约束类型的 ref 顺序**已由 C 读 solver residual 钉死 + 真 solver 验证**（见附录）。

## 风险 / 开放项

- **每种约束的 ref 顺序**：schema 只定 arity 不定语义顺序；探针**第一刀**就是用真 solver + 已知 fixture 把每种类型的 ref 排列钉死，否则 adapter 是猜的。
- **coincident/concentric blocked**：schema(2) 与 solver(≥4，`solver.cpp:1185/1191`) arity 矛盾 → 不在 v1 prototype 支持集；解禁需先修 CADGF-PROJ schema 到 4 refs（独立小工作项）。
- **`equal` 不暴露到 v1（已拍板）**：CADGF-PROJ/solver 有 `equal`，但它只是标量等式 `a-b`，非 CAD 的等长/等半径；暴露会把 solver 变量语义漏回 Project 真相、与 D1b 冲突。未来等长/等半径 → 引入语义明确的 `equal_length`/`equal_radius`，并先解决非 point 变量（长度/半径入变量）或扩 solver 映射。坐标相等由 `horizontal`/`vertical`（接受 2 point）表达。
- **polyline/text 暂 passthrough**：CADGF-PROJ 无此类型；text 不求解，polyline 拆点纳入求解为后续增强。
- **point-only 求解**：radius/angle 不可解是当前 CLI 的真实限制；若 v1 需要尺寸约束（半径/角度），要么扩 CLI 变量映射（C++ 改动，超出 prototype），要么 v1 明确不收这类约束。
- **跨平台确定性**：未验；因 evaluated 不进真相，风险被 D1 降级为"单次容差内可复现"，但 Tier 3 稳定契约仍要专门测。
- **CLI 部署**：rpath/DYLD 修复是 prototype 范围内的子任务；稳定化属 Tier 3。

## 备注

未跟踪草案；与评估文档一起、从更新后的 `origin/main` 切**新分支**提交（勿用 stale 本地 `docs/project-runtime-v0`）。

## 附录 — C 钉死：SemRef→VarRef 展开表（源自 solver.cpp residual :1143-1207）

直接读 solver residual 提取每类**精确变量顺序**（非黑盒猜）。adapter 必须按此序展开 SemRef → 铸造 point 的 `pointId.x/.y`：

| type | SemRef（语义） | VarRef 顺序（喂 solver） | residual | value |
|---|---|---|---|---|
| `horizontal` | 1 line | `[start.y, end.y]` | `y1-y0` | — |
| `vertical` | 1 line | `[start.x, end.x]` | `x1-x0` | — |
| `distance` | 2 point | `[A.x, A.y, B.x, B.y]` | `√((x1-x0)²+(y1-y0)²) - value` | 距离 |
| `parallel` | 2 line | `[L1.s.x,L1.s.y,L1.e.x,L1.e.y, L2.s.x,L2.s.y,L2.e.x,L2.e.y]` | 叉积/(‖v1‖‖v2‖) | — |
| `perpendicular` | 2 line | 同 parallel 8 序 | 点积/(‖v1‖‖v2‖) | — |
| `angle` | 2 line | 同 parallel 8 序 | `acos(cosθ) - value` | 弧度 |
| `equal` | 2 标量变量 | `[a, b]` | `a-b` | — | ← **solver primitive，不在 VEMCAD v1** |

> 上表前 6 行 = **v1 支持集**；`equal` 行仅记录 solver 事实，**不是 VEMCAD v1 Project constraint**。

**发现 / 决定**：
- **`equal` 移出 v1（已拍板）**：residual 是 `a-b`（两标量变量相等），非 CAD 的等长/等半径；v1 point-only 变量下它只能做坐标相等，暴露会把 solver 变量语义漏回 Project 真相、与 D1b 冲突。坐标相等改由 `horizontal`/`vertical`（接受 2 point）表达。未来等长/等半径 → 引入语义明确的 `equal_length`/`equal_radius` + 先解决非 point 变量。
- `horizontal`/`vertical` 取 **1 line 的两端点，或 2 point**，equate 单坐标（y/x）。
- solver 另实现 `tangent`(6)/`point_on_line`(6) 等，但 **CADGF-PROJ schema 无这些类型** → 不在 v1（schema ∩ solver）。
- 此表是 C 的地基；adapter 单测须逐类断言**这 6 类**展开顺序，独立验收用真 solver fixture 复核（解满足约束）。
