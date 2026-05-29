# VemCAD 规划推进进度核对（2026-05-28）

- 状态：**只读盘点报告**，未改任何代码 / 未提交
- 基线：以 **`origin/main` tip `ce22086`**、子模块指针 `ba5f882` 为真相
  （本地分支 `docs/project-runtime-v0` 已 stale：**ahead 78 / behind 9**，工作区落后于 main，
  不能直接用本地 `git status` 当进度信号）
- 对照对象：`docs/VEMCAD_DEVELOPMENT_PLAN.md`（5 阶段主线，本文称"规划MD"）
  + `docs/VEMCAD_WORKBENCH_SPLIT_PLAN.md`（其 Phase 2 的展开）

## 0. 一句话结论

主线 **Phase 0–1 已完成并合入 main**（且 P1 已扩展到 v1 求解器，用户于 2026-05-26 主动
**收口在 milestone**）；**Phase 4 部分完成**（`/solve` HTTP 服务已上线，Router 主契约未产品化）；
**Phase 2 / 3 / 5 尚未动工**。最值得注意的事实：**"规划MD"本身、以及一整条已"验证"的 web
工作（bootstrap / 离线缓存 / workbench 拆分脚手架）目前全部是 untracked WIP，不在 `origin/main`、
不受 CI 保护**——只有 `apps/web/shared/runtime_bridge.js`（S7）落了盘。

## 1. 阶段进度对照表（已对 `origin/main` 校准）

| Phase（规划MD） | 状态 | 证据 / 说明 |
|---|---|---|
| **P0 冻结边界** | ✅ 完成 | 三类数据边界（project / document / session）已钉死；决策 frozen（`VEMCAD_POST_V0_DIRECTION_EVALUATION`）。 |
| **P1 建立 Project Runtime** | ✅ 完成（+v1 求解器） | `apps/runtime/*`（含 `solver/`、`solve_cli.mjs`）全在 origin/main；PR #2–#6 已 merge；node+真实 solver 验收绿。**用户已主动 CLOSE 此线 at milestone。** |
| **P2 拆 Web Workbench 上帝模块** | 🟡 **仅脚手架（0% 物理抽离）** | 3 个上帝文件原封未动：`command_registry.js` **5463** / `workspace.js` **2909** / `preview_app.js` **4422** = **12,794 行**仍是整块。`apps/web/workbench/*` 只有目录树 + README + 1–18 行 re-export facade，且**全部 untracked**。 |
| **P3 收敛 Desktop Shell** | ⬜ 未开始 | `apps/desktop/` 仅 README（150B）。 |
| **P4 独立 Router 契约** | 🟡 部分完成 | `services/solve/`（`/solve` HTTP，PR #6）**已在 main**；但 `services/router/` 仍是 README + REPO_POINTER 占位，**0 行可执行代码**。完整 ROUTER_CONTRACT（convert/status/manifest/history/projects/...）的真实实现仍是子模块里的参考实现 `deps/.../plm_router_service.py`（~2001 行），未产品化。 |
| **P5 Qt 角色收敛** | ⬜ 仅文档层 | 无代码动作。 |

> 校正：早前 survey 子代理在 stale 工作区里读到 `services/solve` "不存在"——那是因为本地分支落后 main 9 个
> 提交、`services/solve` 没 checkout 到磁盘。`git ls-tree origin/main` 确认它**确实已合入**。

## 2. 关键发现：两条"未落盘"的 web 工作线

untracked WIP 不是垃圾，是**两条真实但从未合入 main 的工作线**：

1. **Web bootstrap / 运行时硬化线**（4 月系列文档：`WEB_BOOTSTRAP_INTEGRATION_*`、
   `WEB_RUNTIME_HARDENING_PHASE{1..5}_*`，含 DEVELOPMENT + VERIFICATION）：
   - `apps/web/app.js`（136 行，真实）：preview/editor 双模式 bootstrap + `window.__vemcadApp.switchToEditor` 桥 + 离线缓存触发。
   - `apps/web/offline/product_offline_cache.js`（143 行，真实）：service-worker 产品资源缓存。
   - `apps/web/tests/web_bootstrap_entry.test.js`（8 例）、`product_offline_cache.test.js`（9 例）。
   - **文档声称"已开发 + 已验证"，但代码全是 untracked，未在 main，无 CI**。⚠️"有验证文档" ≠ "已合入"。
2. **Workbench 拆分脚手架**（对应 `WORKBENCH_SPLIT_PLAN.md` 的 Phase 0 边界冻结）：
   - 目标目录树 + 14 个 README + 4 个兼容面 contract 常量（`workbench/contracts/index.js` 等）
     + 几个 1–5 行 re-export facade（`workspace_bootstrap.js`、`commands/registry.js`）。
   - 这些 facade 仍直接 re-export 子模块里的上帝文件 → **目前是纯转发，没隔离作用**。

唯一落盘的 web 文件：`apps/web/shared/runtime_bridge.js`（S7，已在 main）。

## 3. Phase 2 剩余工作量拆解（survey 结果）

### 3a. `command_registry.js`（5463 行，37 命令，~10 领域）— SPLIT_PLAN Phase 1

物理抽离 ≈ **0%**；目标子目录（`commands/{shared,entity,selection,groups,solver}`）尚不存在。
4 个稳定兼容面（`registerCadCommands`、`computeRotatePayload`、`computeScalePayload`、37 个命令 id /
`commandResult` 语义）**都在、且 load-bearing**。各目标模块归属与体量：

| 目标模块 | 源位置（行） | 体量 | 备注 |
|---|---|---|---|
| `shared/snapshot.js` | 41–108 | ~68 | **gating**：所有命令依赖 `withSnapshot`，先搬。 |
| `shared/selection.js` | 110–175 | ~66 | 与 transform 共享 whole-group 助手（勿重复计）。 |
| `entity/create.js` | 177–204 + 5067–5091 | ~55 | 低 UI 耦合。 |
| `solver/bridge.js` | 5372–5432 | ~60 | **内联在注册表里**，无独立函数，机械抽离易漏。 |
| `selection/property_patch.js` | 4902–5066 (+源文本 4087–4424) | ~165 (+~340) | 自带子集快照历史。 |
| `selection/transform.js` | 850–1075 + 3997–4085 | ~315 | 数学已 seam 进 `geometry.js`，命令仍内联。 |
| `selection/trim_extend.js` | 4425–4901 | ~477 | 自包含，**可比计划更早搬**（与 fillet 无关）。 |
| `groups/insert_group.js` / `source_group.js` | 205–849（交错） | ~280 / ~265 | 两组命令在 317–849 **交错**，须按命令 id 拆。 |
| `selection/break_join.js` | 1076–1544 + 3888–3996 | ~575 | 与 fillet 共享 pick 助手。 |
| `selection/fillet_chamfer.js` | 1545–3887 | **~2,125 (+~215)** | **占全文件 ~40%，几何密集，最高回归风险，计划正确地排最后。** |

### 3b. `workspace.js`（2909 行）— SPLIT_PLAN Phase 2
8 个目标模块，但**覆盖不全**：source-group/insert-group/space/layer/tool wiring（~707–1299、
1664–1820，89 处引用）+ 组装壳 **不属于这 8 个模块** → 抽完 8 个 workspace.js 也不会清空成薄壳。
最大块是 panels（1516–2577，statusBar 配置 1571–2177 ~600 行）；solver runtime（~600+ 行）散在全函数。
风险：`window.__cadDebug` 闭包重、`bootstrapCadWorkspace` 返回形状是兼容面，抽离须零能力回退。

### 3c. `preview_app.js`（4422 行）— SPLIT_PLAN Phase 3
10 个目标模块，唯一已完成的 seam = editor-handoff（`switchToEditor` 已在 `app.js`，preview 仅消费）。
**计划遗漏的前置**：~80 个模块级可变状态 + ~50 个 DOM ref 无 context 对象承载 → **必须先引入
共享 runtime context**，否则机械按域抽离会产生循环依赖 / 20+ 参数签名。整个 desktop 域
（settings/recent/batch/open）挤在一个 884 行 `if(desktopBridge){...}` 闭包里（3522–4405），需先把状态提出闭包。
`?manifest=`/`?gltf=`/fallback 路径是 smoke 契约但**无自动化测试**——动它前要先补测试。

## 4. 贯穿性结论：Phase 2/3 是"子模块工程"，不是纯产品仓改动

`WORKBENCH_SPLIT_PLAN` 的策略是"**先在 `deps/cadgamefusion/tools/web_viewer/` 内逻辑拆分，再
（Phase 4）物理迁移到 `apps/web/*`**"。这意味着 Phase 1–3 的真实拆分**发生在 CADGameFusion 子模块内**，
必然走已固化的 **A→C 子模块发布纪律**（CADGameFusion 开 PR + VemCAD gitlink-only 指针 bump +
`merge-base --is-ancestor` 护栏 + editor-light CI）。这正是记忆里标注的"交互式 web viewer 回路天然
submodule-native"的那块。→ **继续 Phase 2 = 一项跨子模块、~12.8k 行、多 PR 的工程，不是一次小改。**

## 5. 风险

1. **规划MD 与一整条已验证 web 工作未受版本控制**：丢失/漂移风险高，且 main 上无 CI 看护它们。
2. **"验证文档存在" 被误读为 "已合入"**：盘点时极易高估进度（4 月 5 个 hardening phase 看似完成，实则未落盘）。
3. **本地分支 stale + 工作区脏**：任何继续都必须按既定纪律**从最新 `origin/main` 切独立 worktree**，
   绝不在 `docs/project-runtime-v0` 这个 stale/脏分支上动手。
4. **fillet/chamfer（~40%）** 是 Phase 1 的体量与回归风险主体，需最强测试 backstop。
5. Router 契约的 `/manifest/{task_id}` 端点连参考实现里都没有（靠 artifact_urls 暴露）——契约 vs 实现存在缺口。

## 6. 建议的下一步（排序）

**S0（无悔、低风险、纯产品仓、不碰子模块）— 推荐先做：**
把 untracked 的"规划MD + 已验证 web WIP（bootstrap/离线/脚手架）+ 计划文档"**从最新 origin/main 切干净
分支落盘**，纳入版本控制 + CI。理由：当前规划文档本身和一大批"已验证"工作都不在 main，这是最先要消除的风险；
且这一步不重开用户已收口的求解器线，也不进子模块。（**需用户确认**，因为这会动到被标记"先别碰"的 WIP。）

**S1（按规划MD 的 P2 优先级，子模块工程）：** 开工 `command_registry.js` 拆分第一步——
先搬 `shared/snapshot.js`（41–108）+ `shared/selection.js`（110–175），共 ~134 行、gate 全部下游；
在 CADGameFusion 子模块内做，遵循 A→C 纪律。

**S2（Phase 4 收尾）：** 把 `plm_router_service.py` 逻辑产品化进 `services/router/`，补 `/manifest` 缺口；
GPL/LibreDWG 隔离的独立仓拆分（REPO_POINTER）另议。

---
*本报告由只读 survey（4 并行子代理读 ~12.8k 行 + 服务层盘点）+ origin/main 校准生成；未改代码。*
