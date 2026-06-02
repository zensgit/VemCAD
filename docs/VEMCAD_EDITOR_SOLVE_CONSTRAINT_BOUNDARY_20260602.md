# VemCAD Editor-Solve ↔ Native-Solver 边界 — 两套约束/求解系统

- 状态：**边界 + 定位钉定（2026-06-02）**——避免团队反复期望「编辑器 Solve dock 解用户在编辑器里画/加的约束」
- 日期：2026-06-02
- 地基：`origin/main` @ `5a61e81`（CADGameFusion 子模块 `aaecd0b`，dual-mode 入口已合并）
- 相关：`docs/VEMCAD_SOLVER_DIAGNOSTIC_UI_BOUNDARY_20260602.md`（同类「钉边界」决策）；求解线 PR 串 #45–#55 + dual-mode #384/#56
- 证据来源：e2e 浏览器验证（Playwright + 真实 /solve）+ node 级 round-trip + 源码定位

## 目的

求解 dock（产品求解线 #45–#55）现在已在 live 编辑器里**可达并能调用真实 /solve**（dual-mode 入口 #384/#56 之后）。但 e2e 验证发现：**编辑器里点 Solve 不会移动几何**，因为编辑器导出给 /solve 的工程**没有约束**。本文钉死根因、产品求解线的**定位**，以及统一两套系统的**待决选项**——这是产品决策，不是小修复。

## 根因：两套并行、互不连通的求解系统

| | 编辑器原生求解器（子模块） | 产品求解线 #45–#55 |
|---|---|---|
| 约束表示 | 底层 **VarRef**（`"id.x","id.y"` 按 x/y 成对；`documentState.constraints` Map，refs 是字符串） | 高层**语义 SemRef** `{entity, at}`（Tier1 规格**故意**与 solver VarRef 解耦） |
| 录入方式 | `cad-add-constraint`（手输逗号分隔 VarRef）/ `cad-import-solver`「Import Solver JSON」 | VEMCAD-PROJECT（demo / 导入 / 存读档 / runtime） |
| 求解器 | 编辑器自带会话（`solverDiagnostics`、solver-action 面板、`solver.export-project`） | VEMCAD-PROJECT → `/solve` → Tier1 求解器 → 写回 |
| 文档来源 | `documentState.listConstraints()`（VarRef） | 产品桥导出 —— **只几何，丢约束** |

**约束在哪丢的**：产品桥走 CADGF 交换格式（`exportRuntimeProjectFromDocumentState → exportCadgfDocument → importProjectFromCadgfDocument`）。`exportCadgfDocument` 发 **0 条**约束；`importProjectFromCadgfDocument` 自注「CADGF 不带 VemCAD 约束 → 返回空」。CADGF 是**几何交换格式**，本就不携带 VemCAD 语义约束。

**node 级确证**：导入带 1 个 horizontal 约束的工程 → 编辑器 DocumentState → 再导出 → `constraints: []`（实体在、约束没了）。浏览器侧印证：导入后编辑器求解 `dof=0/state=unknown`（无约束特征）；而带约束时真实 /solve 是 `dof=1/underconstrained` 且把斜线压平成 `[[0,2.5],[10,2.5]]`。

**为何不能简单「桥多读一下约束」**：编辑器约束是 **VarRef**（solver 变量级），产品 /solve 要 **SemRef**（语义级）。VarRef→SemRef 是**有损/歧义**的，且 Tier1 规格**有意**保持二者解耦（「真相不能泄漏 solver 内部表示、与铸造 id 耦合」）。所以这是表示层不匹配，不是一行 map。

## 已验证可用（产品求解线的真正定位）

产品求解线对**语义工程**是完整、已验证的：
- dual-mode 入口两条启动路径（产品可达→dock 挂载；缺席→legacy，零回归）——浏览器实测。
- 编辑器 Solve 按钮 → 真实 /solve → 真实 Tier1 求解器 → 面板 'Solved'——浏览器 + 真实后端实测。
- 真实求解器对语义约束工程正确求解（curl：斜线 + horizontal → 压平）。
- 写回（auto-apply + 撤销）/ 冲突高亮+清除+建议 / 导入·导出·复现包——单测 + 浏览器实测。

→ **产品求解线服务 SEMANTIC 工程**（demo / 存读档 / 导入的 VEMCAD-PROJECT / runtime / 未来 API）。这条路就绪。

## 定位结论（本文钉定）

- **编辑器 Solve dock 不是用来解「编辑器原生（VarRef）约束」的**——那是编辑器**原生求解器**的活，且它已在做。
- **产品求解线 = 语义工程的求解路径**。它在编辑器里对**语义来源**（如导入的 VEMCAD-PROJECT）有效；对编辑器**手画+原生约束**无效（约束表示不通）。
- 不要再期望「在编辑器里画线、加约束、点 Solve 就动」——除非先做下面的统一决策之一。

## 待决选项（产品决策，本轮未建）

- **A. 编辑器 dock 改接编辑器原生求解器**（用 `solver.export-project` + 原生会话），而非 /solve。最务实——编辑器已能解自己的约束；代价：产品求解线对编辑器用途让位、两条 UI 需收敛。
- **B. 产品线专注语义工程 + 给编辑器加「语义约束创作」**（让用户在编辑器里产生 `{entity,at}` 约束，桥才有料可带）。让产品的新求解架构真正进编辑器；代价：大功能（编辑器侧 A→C）。
- **C. VarRef↔SemRef 转换层**。有损、复杂、违背规格解耦初衷；不推荐。

## 解禁门（再做「编辑器可视约束求解」前）

先在 A/B/C 里定方向；**不要假设产品桥能携带编辑器的原生约束**。任何「让编辑器画的约束进 /solve」的工作，必须先解决表示层（VarRef↔SemRef）或改走原生求解器。

## 不在本边界内

- 产品求解线本身（已就绪，服务语义工程）。
- live-doc 持续求解（vs 挂载快照）——独立的已命名 deferred 项。
