# VemCAD Router Launcher 去重 Scoping + 决策

- 状态：**只读 scoping + 决策（已拍板：去重推迟到 Phase 3）**，未改代码
- 日期：2026-05-30
- 关联：`services/router/launcher.mjs`（VemCAD #19）·
  `deps/cadgamefusion/tools/web_viewer_desktop/main.js`（Electron 壳，子模块）·
  [`VEMCAD_DEVELOPMENT_PLAN.md`](./VEMCAD_DEVELOPMENT_PLAN.md) Phase 3（desktop shell 收敛）

## 问题

Electron 桌面壳是否可以改为 `import/use services/router/launcher.mjs`，消除两边重复的
spawn / health / timeout / cleanup 逻辑？

## 结论先行（关键层次问题）

**直接让 Electron import `services/router/launcher.mjs` 不可行——依赖方向反了。** Electron 壳在
**CADGameFusion 子模块**里（`tools/web_viewer_desktop/main.js`），`launcher.mjs` 在**产品仓**里
（`services/router/`）。依赖方向是 VemCAD(产品) → CADGameFusion(子模块)；让子模块 import 产品仓文件
= **向上依赖**，CADGameFusion 单独构建 / 被别的消费者使用时该文件不存在 → import 悬空。

**真正去重需要把共享 launcher「下沉」到平台层（子模块内）**，desktop 壳直接 import、`services/router`
变成薄消费者。这是一次 **A→C 重构**，不是产品仓里一个 import。

**额外发现（独立于去重）**：Electron 现有 cleanup `routerProcess.kill()`
（`app.on("before-quit")`，main.js:1108-1110）是 **SIGTERM-only、无 SIGKILL escalation**——和 review
刚在 launcher 抓到的是**同一类 orphan 风险**。但这是**防御性缺口**，不是已确认的活故障：真 python
router 对默认 SIGTERM 大概率直接终止（不像 fake stub 故意 ignore）。

## 两处实现对照

| 能力 | Electron `ensureRouterReady` 等 | `launcher.mjs` |
|---|---|---|
| spawn | `spawn(cmd[0], cmd.slice(1), {cwd, stdio:'ignore'})` | `spawn(command, args, {env, stdio})` — 无 `cwd` |
| 就绪 | `waitForRouter` poll `fetch(/health)` 每 500ms + `Promise.race(spawnErrorPromise)` | `ready()` poll `http.request(/health)` + race exit；有 startTimeout→kill |
| 停止 | before-quit `routerProcess.kill()` (SIGTERM only) | `stop()/terminate()` SIGTERM→SIGKILL escalation, memoized |
| 错误模型 | 5 码 + recovery hint + readiness 元数据（UI 依赖） | 3 码 `ROUTER_START_FAILED/TIMEOUT/NOT_CONFIGURED` |
| 健康检查 | 全局 `fetch` + AbortController | `http.request` + timeout |

## 可去重的「核心」vs Electron 专有

- **可去重核心**（两边重复）：`spawn + /health 轮询 + 就绪/超时 + spawnError race + cleanup-kill`，
  正对应 launcher 的 `spawn + ready() + stop()`。
- **Electron 专有、留在壳里**（不进 launcher）：config 解析（`resolveRouterConfig/StartConfig`）、
  命令构建（`resolveStartCommand`）、路径探测（packaged vs dev、`detectRouterPaths`）、
  **「先查健康、复用已在跑的 router」+ autoStart 闸 + single-flight `routerStartPromise`** 编排、
  5 码错误 + hint + readiness 元数据、`app.on("before-quit")` 钩子。

## 迁移路径

- **路径 A（真去重，A→C）**：把 launcher 生命周期核心下沉进子模块；Electron 用
  `startRouterLauncher({command, args, host, port, cwd, ...})` 替换内联 `spawn + race`（main.js:1158-1208），
  把 `RouterLaunchError` 码映射回 5 码 + hint，`before-quit → launcher.stop()`；launcher 需先补 `cwd`
  选项；VemCAD `services/router/launcher.mjs` 改成薄 re-export（**测试从 product-core 搬到 CADGameFusion
  CI / web-integration**）。CADGameFusion PR + 指针 bump。
- **路径 B（仅对齐契约，最便宜）**：两份各留原处，靠同一 `{url,ready(),stop()}` 契约 + 镜像 lifecycle
  测试保持一致，并把 SIGKILL escalation 抄进 Electron cleanup。无代码合并、接受少量漂移。
- **路径 C（反向，超范围）**：把 Electron 壳从子模块上移到 VemCAD `apps/desktop` → 同层可 import 产品
  launcher。= 主计划 **Phase 3**，工程量远超本议题。

## 风险

1. **层次反向（核心）**：产品 launcher 不能被子模块 import；A 必须下沉，否则不可行。
2. **测试 gating 迁移**：A 把 launcher 测试从纯 node product-core（无 PAT/无子模块、最鲁棒）搬走。
3. **真 router 从未 e2e**：launcher 只对 fake stub 验证过；进 Electron 生产路径 = 首次真用，需先补真
   python router 的 e2e（CADGameFusion Local CI 已有 `plm_router_smoke.py` 可挂）。
4. **错误模型收窄**：3 码 < 5 码 + hint + readiness；映射不当会回退桌面 DWG-not-ready 的 UI 可恢复性。
5. **A→C 开销** + **撤销 #19 归属**（把刚落地的 launcher 重新安置）。

## 测试计划（若将来走 A）

- 下沉后的核心 launcher：搬运 #19 的 lifecycle 测试（fake stub）进子模块 globbed node 门禁。
- Electron 集成：现有 `desktop_packaged_*` / 自启动 smoke 作回归网 + 新断言"经 launcher 启动 → /health
  就绪 + 退出无 orphan（before-quit → stop escalation）"。
- 真 router e2e：复用 `plm_router_smoke.py`，由"经 launcher 启动的 router"驱动一次 convert→/manifest。
- VemCAD 侧 re-export 的测试改挂 web-integration（有子模块）；PR 写明 core 不再覆盖它。
- 错误码映射单测：launcher 3 码 → Electron 5 码 + hint 完整。

## 决策（拍板 2026-05-30）

1. **现在不做去重（路径 A）。** 两份实现都在跑、都有覆盖、当前无漂移故障；A 的代价高且多为负向
   （A→C + 重新安置 #19 + 测试 gating 搬离 product-core + 真 router 首次 e2e + 错误映射回退风险），
   对 desktop phase 1 最小化姿态是过度投资。
2. **去重的正确触发点 = Phase 3（desktop shell 收敛）**，那时本就要重新安置壳；或等"重复真的造成
   一次漂移 bug"再做（需求/事件驱动，非投机）。
3. **保持契约对齐**：两边都已是 `{url, ready(), stop()}` 形状，将来下沉时零摩擦。
4. **Electron cleanup 的 SIGTERM→SIGKILL escalation = 可选防御性小修**，非必需、不紧急。

## 备注

本文为只读 scoping + 决策记录，未触碰任何实现代码。P4 phase 1（launcher 已落 main、CI 绿）是干净
完整的交付点；本议题之后的动作属 Phase 2/3 级别或非必需小修。
