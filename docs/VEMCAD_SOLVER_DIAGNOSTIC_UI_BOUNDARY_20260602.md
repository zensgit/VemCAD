# VemCAD Solver 诊断 UI 边界 — 冲突可做，冗余/欠约束暂缓

- 状态：**边界钉定（2026-06-02）**——避免重复在不可靠的 solver 结构信号上堆 UI
- 日期：2026-06-02
- 地基：`origin/main` @ `9a3be72`
- 上游：冲突 UX 三件套已合并 —— 高亮 (#48) / 干净求解清除 (#49) / 行动文字 (#50)
- 相关规格：`docs/VEMCAD_RUNTIME_V1_SOLVER_TIER1_SPEC_20260525.md`（求解器仍是 **Tier 1 prototype**）

## 目的

求解结果驱动用户改图的诊断 UI 里，**冲突（over-constrained）路径已做且稳定**，但**冗余（redundancy）/ 欠约束（under-constrained）高亮在当前 Tier 1 求解器上不可靠**。本文把这条边界钉死：记录实测证据、说明为什么是 **solver 信号问题而非产品接线问题**、并给出**解禁门（gate）**，让以后不再回到"在不可靠信号上做 UI"的循环。

**结论先行**：现在**不要**做冗余/欠约束高亮。冲突路径是稳定、有价值的核心，停在那里是干净边界。

## 已做且稳定：冲突诊断 UI（id 键，可靠）

机制是 **id 键的**，因此绕开了跨 Node→JSON→C++ 边界的索引对齐脆弱性（与几何写回同一套稳健原理）：

- solver 的 conflict 类 `action_panel` 带 `variable_keys`（`"<铸造点id>.<坐标>"`，见 `deps/cadgamefusion/tools/solve_from_project.cpp` 的 `make_action_panel_json` + `out["analysis"]["action_panels"]`）。
- 经 adapter 的 `pointMap`（`mintedId → {entity, role}`，`apps/runtime/solver/adapter.js`）反解到**拥有该点的编辑器实体 id**（线的 start/end 归并到同一条线）。
- 落地：
  - `apps/runtime/solver/index.js` — `resolveConflictEntityIds(analysis, pointMap)` + `solveProject` 服务端富化 `analysis.conflict_entity_ids`（随 analysis 走，ok 真/假两路都到 controller；冲突走 `ok:false`）。
  - `apps/web/workbench/solver/solve_workbench.js` — `summarize` 暴露 `summary.conflictEntityIds` + `summary.conflictAdvice`（首个 enabled 冲突面板的 `hint`）。
  - `apps/web/workbench/solver/editor_solve.js` — 冲突时高亮（独立于 auto-apply 的 `envelope.ok` 门）；干净求解后清除**仅我们设的**高亮（`shouldClearHighlight`）。
  - `apps/web/workbench/panels/solve_panel.js` — `Conflicting: <ids> — <hint>` 建议行。
- 真实 solver 验证：两条互斥距离约束 → `conflict_entity_ids = ["P1","P2"]`，已在 `apps/runtime/tools/solve_acceptance.mjs` 的 `conflict` 用例断言（本地 C3 门）。

## 暂缓：冗余 + 欠约束高亮 —— solver 结构信号不可靠（实测）

用**真实** `solve_from_project`（`deps/cadgamefusion/build/tools/solve_from_project` @ 子模块 `49f763f` + `build/core` 的 libcore）跑探针，结果：

| 探针 sketch（语义） | 期望 | 实测（真 solver） |
|---|---|---|
| `transitive-horizontal`：`h(P1,P2)` + `h(P2,P3)` + **`h(P1,P3)`**（第三条由传递性蕴含 → 真冗余） | `redundant_constraint_estimate ≥ 1` | **`ok=true, structural_state=well_constrained, redundant=0`** ← 漏检真实冗余 |
| `dup-parallel`：两条线 `parallel` **重复两次** | redundant ≥ 1 | **`ok=false, state=unknown, redundant=0`，无 enabled 面板** ← 噎住判 unknown |
| `dup-horizontal`：同一线 `horizontal` 重复两次 | redundant ≥ 1 | **`ok=false, state=unknown`，无 enabled 面板** |
| 矛盾距离（`d=10` 且 `d=20`，前序冲突探针） | 冲突 | `state=mixed`，conflict **与** redundancy 面板都填充（但**本质是冲突**） |

**判断**：redundancy 类 `action_panel` 只在**矛盾/混合**情形稳定填充（那里 conflict 已经主导）；对**真正可解的冗余**（`ok:true`）要么**漏检**（`redundant=0`），要么把图判成 **`unknown` 且 `ok:false`**。欠约束自由变量（`free_variable_keys`）信号只会更噪（自由度高的图里大量点都"自由"）。

**若现在做冗余/欠约束高亮**：绝大多数真实冗余图形会**什么都不显示**，只有奇怪的混合情形偶尔亮——低价值且会误导（时有时无）。

## 为什么这是 solver 信号问题，而非产品接线问题

`res.analysis`（含 `structural_state` / `redundant_constraint_estimate` / `action_panels`）整体来自 C++ `solve_from_project` → `core/src/solver.cpp`（`classify_structural_state`、冗余/witness 检测、conflict group 构造）。产品层只做**透传 + 按 id 解析**，已被冲突路径证明是对的。缺陷在 **solver 的结构分析本身**。

提升它（让可解图上的冗余/欠约束稳定可报）属于 **Tier-2 / C++ 求解器工作**，超出当前**冻结范围**（已拍板：不做 full solver rewrite、D1b、OCCT、cloud）。因此本轮**不动 solver、不在弱信号上做 UI**。

## 解禁门（gate）—— 再做结构诊断 UI 前必须满足

1. 在 **N 个可解（`ok:true`）的代表性冗余/欠约束 sketch** 上，solver **稳定**报告对应 `structural_state` 并填充对应 `action_panel`（`variable_keys` 非空且可经 `pointMap` 解析到实体）。
2. 把该断言加进 `apps/runtime/tools/solve_acceptance.mjs`（**真 solver**，本地 C3 门），像现有 `conflict` 用例那样钉死——绿了才算信号可靠。
3. 满足后**产品侧改动极小**（见下），届时再做高亮/面板。

## 复用资产（信号成熟后，产品侧扩展很小）

- `resolveConflictEntityIds` 可直接泛化为按类别：`resolveEntityIdsByCategory(analysis, pointMap, 'redundancy')`；`solveProject` 再加一行 `analysis.redundant_entity_ids`。
- `summarize` 已有 `conflictEntityIds` / `conflictAdvice` 模式，加 `redundant*` 同款。
- 呈现优先选**面板信息行**（如 `Redundant: <ids> — <hint>`）而非选区高亮：冗余多出现在**成功**求解上，自动改选区会与 auto-apply / 用户选区相撞（冲突路径之所以用选区高亮，是因为它本身是**阻塞**态、`ok:false`）。
- 本地真 solver 验证入口：`VEMCAD_SOLVE_BIN=deps/cadgamefusion/build/tools/solve_from_project`、`VEMCAD_SOLVE_LIBPATH=deps/cadgamefusion/build/core`。

## 不在本边界内

- **停靠/对接 UI**（交互壳层，路线图 step 4）——独立于本信号问题，可在任意时点单独评估，与 solver 成熟度无关。
