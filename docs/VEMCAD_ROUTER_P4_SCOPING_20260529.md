# VemCAD Phase 4 (Router 产品化) 立项 Scoping

- 状态：**只读 scoping 报告（决策依据，未写实现代码）**
- 日期：2026-05-29
- 关联：[`VEMCAD_DEVELOPMENT_PLAN.md`](./VEMCAD_DEVELOPMENT_PLAN.md) Phase 4 ·
  [`VEMCAD_ROUTER_CONTRACT.md`](./VEMCAD_ROUTER_CONTRACT.md) ·
  [`VEMCAD_PLAN_PROGRESS_STATUS_20260528.md`](./VEMCAD_PLAN_PROGRESS_STATUS_20260528.md) §7
- 参考实现基线：`deps/cadgamefusion/tools/plm_router_service.py` @ CADGameFusion `origin/main`（~2001 行）

## 0. 一句话结论

参考实现**不是薄脚本，而是一个功能基本完整的 ~2001 行 python 服务**。Phase 4 的真正成本是**产品决策**（部署目标 / 语言归属 / 是否真要拆仓），不是补端点——端点几乎都已具备。关键澄清：**Router 代码本身是 GPL-clean 的**（GPL 在它 shell-out 的转换器里），这改变了"为隔离 GPL 而拆仓"的必要性。

## 1. 参考实现的真实能力（已具备，非待建）

| 能力 | 现状 | 证据 |
|---|---|---|
| 并发/队列 | `ThreadingHTTPServer` + 有界 `queue.Queue(maxsize)` + worker 线程池 (`max_workers`) | :20, :124-138 |
| 认证 | `--auth-token` 单一 Bearer token（可选；`/metrics` 可单独 require） | :67, :704, :713 |
| 上传限额 | `max_bytes` | :69 |
| 产物分发 | 继承 `SimpleHTTPRequestHandler`，静态 serve `/artifacts/…` | :20 |
| 转换执行 | shell-out 到 `convert_cli`（subprocess）+ **binary 发现 + allowlist** | `CONVERT_CLI_NOT_FOUND/NOT_ALLOWED`, `plugin_allowlist` |
| 历史 | **内存 List + 追加到 `history_file`**（capped by `history_limit`） | :131-196 |
| 指标 | `GET /metrics` | :1361 |

→ 这是一个真实服务，不是占位脚本。"产品化"主要是**归属/部署/语言**问题，不是从零实现。

## 2. 端点：契约 vs 参考实现（gap 只有一个）

参考实现 (`do_GET`/`do_POST`/`do_OPTIONS`) 已有：

- `GET /health` · `GET /metrics` · `GET /projects` · `GET /projects/{id}/documents` ·
  `GET /documents/{id}/versions` · `GET /history` · `GET /status/{task_id}`
- `POST /convert` · `POST /annotate`
- `OPTIONS`（CORS preflight）

**唯一缺口 = `GET /manifest/{task_id}`**（契约 §3.4）：

- 契约要求一个返回**裸 manifest JSON body**（非外层 envelope）的专用路由，并定义错误码 `404 TASK_NOT_FOUND` / `409 TASK_NOT_READY` / `500 MANIFEST_MISSING`。
- 参考实现当前是把 manifest **内联**进 convert/status 响应（`"manifest": …`）+ 给一个 `manifest_url` 指向磁盘 `output_dir/manifest.json` 的静态文件。
- 数据已存在（`manifest.json` 在 task 输出目录）→ 补这个专用路由是**小改动**。

其余契约要素（envelope `status/error_code`、task state 机、history/projects/documents/versions 形状、错误码集、auth）参考实现基本对齐。

## 3. GPL / 拆仓的真相（去风险点）

`services/router/REPO_POINTER.md` 给的拆仓理由是"隔离 GPL-only 转换器（LibreDWG）"。但实测：

- **`plm_router_service.py` 中 0 处 GPL / LibreDWG / DWG 直接引用**。
- GPL 耦合在它 **shell-out 的 `convert_cli` / importer 插件**里，**不在 router 代码内**。

→ **结论**：为隔离 GPL 而把 Router 拆成独立仓**可能并不必要**。Router 可以放在产品仓（node 或 python）、保持 GPL-clean；GPL 转换器留在它现在的位置（子模块/独立分发），通过 subprocess + allowlist 边界调用。**若仍要拆仓，理由应是"独立发布节奏/部署"，而不是 GPL 隔离**——两者是不同的问题，不应混为一谈。

## 4. "产品化" = 三选一（成本递增）

| 方案 | 做法 | 代价 | 取舍 |
|---|---|---|---|
| **C 薄 facade** | `services/router` 放一个 node facade，spawn 子模块 python（类比 `services/solve`→`solve_cli`） | 最小 | runtime 耦合子模块 python；产品层不真正"拥有"实现 |
| **B 搬迁拥有** | 把 python 移出子模块、进 `services/router` 由产品仓拥有 | 中 | `services/` 变 python+node 混栈；与子模块 fork/漂移风险 |
| **A 重写 node** | 把 ~2001 行 python 重写成 node:http 进 `services/router`（与 `services/solve` 统一）+ 补 `/manifest` | 最大（~2001 行） | 产品仓统一 node、自有、最干净的产品故事；一次性投入大 |

## 5. 云就绪缺口（端点之外的"稳定契约"差距）

若部署目标是云/多用户，下列项需要补（桌面单用户则可暂不补）：

- **历史持久化**：现为内存 + 单机 `history_file`，**非共享 DB** → 多实例水平扩展时历史/项目/版本视图不一致。
- **认证**：现为单一静态 Bearer token → 多用户需真实身份/租户隔离。
- **转换器可达性**：shell-out 到 `convert_cli` 的 binary 发现（与 `solve_cli` 同类的 rpath/部署脆弱性，参考实现已用 allowlist + 错误码缓解，但容器化/托管仍需固化）。

## 6. 写代码前必须先定的产品问题

1. **部署目标（gate 一切）**：桌面单用户（Electron 拉起，file 历史够用）还是云/多用户（需共享 DB + 真认证 + 水平扩展）？
2. **语言 / 归属**：port→node（统一、产品自有）vs 保留/搬 python vs 薄 facade spawn？
3. **拆仓**：Router 既 GPL-clean，独立仓是否仍要（独立发布节奏）？GPL 转换器隔离是单独议题。
4. **范围**：全量（projects/documents/versions/annotations/metrics）还是 MVP（convert/status/manifest/health）？

## 7. 无悔的第一小步（不论上面怎么定）

在**参考实现**里补 `GET /manifest/{task_id}` 专用路由（返回裸 manifest body + 契约定义的 404/409/500 错误码；数据已在 `output_dir/manifest.json`）。这是契约合规、体量小、对任何产品化路径都有用的一步，走 A→C（CADGameFusion PR + VemCAD 指针 bump）。

## 备注

- 本文为只读 scoping，未触碰任何实现代码。
- 立项决定后，再据第 6 节的回答选择第 4 节的方案与第 5 节的云就绪范围。
