# vemcad-render — 渲染服务 v0（Phase 1 WS-A）

把 CADGameFusion `render_cli`（共享 scene renderer 的无头出口）包装为内网 HTTP
服务。规格出处：`docs/VEMCAD_RENDER_SERVICE_PHASE1_DEVELOPMENT_20260610.md`
（A2a/A3），正式接口契约随 A7 落档（W3）。

## 端点（v0）

- `GET /healthz` — 服务状态、render_cli（路径/sha256/冒烟结果）、字体目录
  （数量/指纹）、并发水位。
- `POST /render` — multipart 字段 `file`（**仅 DXF**，默认上限 48 MiB）+
  查询参数 `format=png|svg`、`width`、`height`（16–8192，且 width×height ≤
  64 MP）、`bg=dark|white|#RRGGBB`、`view=extents|sheet`、
  `style=source|acad-plot`（默认 `source`；`acad-plot` 仅 PNG，输出中性灰度
  plot-raster 风格，用于 AutoCAD PLOT/EXPORTPNG 参照对比和白底图纸预览）。
  命中四元组缓存（内容 sha256 + 规范化参数 + render_cli 二进制 sha256 +
  字体库指纹）直接回图，响应头 `X-Render-Cache: hit|miss`、`X-Render-Key`。
  `view=sheet` 另带 `X-Render-Sheet-Mode: detected|fallback|unknown` 和
  `X-Render-Resolved-View`，用于确认图框窗口是否成功检测，或是否按 fail-safe
  回退到 extents。
  饱和返回 429。错误一律结构化信封
  `{"status":"error","error_code":...,"error":...}`（口径同 ROUTER_CONTRACT）。
- `POST /diff` — **版本可视化对比（L1 旗舰）**：multipart `file_a`(Rev A) +
  `file_b`(Rev B)（**仅 DXF**）+ 查询参数 `width`/`height`/`bg`/`view`（两版用
  **同一组**参数渲染，§5 的背景+配色由此天然一致；叠加图恒为 PNG）+
  `summary_only`。两版各自命中 `/render` 四元组缓存出 PNG，再经共享
  diff 引擎（`tools/render_regression/diff.py`）逐墨迹分类
  unchanged/added/removed，出三色叠加图 + 摘要（叠加图亦缓存，键含两版 sha +
  参数 + tol）。响应：默认回叠加 PNG，摘要随响应头
  `X-Diff-Changed-Fraction`/`-Added-Px`/`-Removed-Px`/`-Unchanged-Px`/
  `-Comparable`/`-Cache`/`-Key`；`summary_only=true` **或**不可比时回 JSON 摘要。
  **§5 视图空间守卫**：两版墨迹 bbox 纵横比差超阈（各自按自身外延 fit）→
  `comparable=false`、`skip_reason=view-space-mismatch`，不出误导叠加图（改外延
  的版本留待"共同窗口"后续）。numpy/Pillow 缺失 → 501 `DIFF_UNAVAILABLE`
  （懒加载，不拖垮 `/render`）。

## 安全姿态（Phase 1）

内网绑定、429 背压、**可选 Bearer token**（设 `RENDER_AUTH_TOKEN` 即要求数据
端点带 `Authorization: Bearer <token>`，否则 401；`/healthz` 始终开放;不设=
现状无认证、向后兼容）。Yuantus 客户端用 `RENDER_SERVICE_SERVICE_TOKEN` 发该
头，两边设同一 token 即开启。渲染在沙箱子进程中执行（超时、内存上限、独立临时
目录、最小环境变量；macOS 开发机经 `sandbox-exec` 尽力禁网并记录，Linux 正本由
容器层 `--network none` 强制）。详见方案 A3/A7。

## 运行

```bash
export RENDER_CLI_PATH=/path/to/render_cli   # 缺省自动找 deps/cadgamefusion/build/editor/qt/render_cli
python3 -m uvicorn app.main:app --factory --host 127.0.0.1 --port 8077
# app.main:app 为工厂函数 create_app
```

测试：`RENDER_CLI_PATH=... python3 -m pytest services/render/tests -q`
（无二进制时渲染类用例自动跳过，参数/缓存单测照跑）。

## `view=sheet` 默认化前审计

`view=sheet` 是 opt-in 图纸预览窗口：先按 extents 渲染，再检测图框窗口并重渲染；
检测不可靠时 fail-safe 保持 extents。把它升为 `/render` 默认前，先对实际图纸目录
跑 corpus audit（图纸只从运行时目录读取，不进仓）：

```bash
python3 services/render/tools/sheet_readiness_audit.py \
  --base-url http://127.0.0.1:8077 \
  --input-dir /path/to/dxf-corpus \
  --out-dir /tmp/vemcad-sheet-audit \
  --width 1600 --height 1131 --bg white --style acad-plot
```

输出：

- `summary.json` — 每张图的 `pass|review|fail`、`sheet_mode`、保留墨迹比例、
  edge-ink 裁切风险和渲染路径。
- `contact_sheet_*.png` — extents vs sheet 的人工复核总览。

默认退出码只因 `fail` 非零；若要把人工复核项也设成门禁，传
`--fail-on-review`。

**部署**（让 Yuantus 可调用）：`docker-compose.deploy.yml` 拉 GHCR 镜像
（`ghcr.io/zensgit/vemcad-render:main`，main 推送自动发布）一键起；
`tools/deploy_smoke.sh <BASE_URL>` 为部署后验证闸（healthz + /render + /diff）。
步骤、网络可达性、Yuantus 接线、回滚见
`docs/VEMCAD_RENDER_SERVICE_DEPLOY_RUNBOOK_20260614.md`。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `RENDER_CLI_PATH` | 仓库内自动探测 | render_cli 二进制 |
| `RENDER_CACHE_DIR` | `~/.cache/vemcad-render` | 内容寻址缓存根 |
| `RENDER_FONT_DIR` | 无 | 字体目录（A5 接管；指纹自第一天进缓存键） |
| `RENDER_MAX_UPLOAD_BYTES` | 50331648 (48 MiB) | `/render` 直传上限（独立于契约 §2.4） |
| `RENDER_WORKERS` | cores/2（≥1） | 并发渲染上限，饱和 429 |
| `RENDER_TIMEOUT_S` | 120 | 单次渲染超时 |
| `RENDER_MEM_LIMIT_MB` | 2048 | 子进程地址空间上限（Linux 强制，macOS 尽力） |
| `RENDER_SANDBOX_EXEC` | 1 | macOS 是否用 sandbox-exec 禁网包裹（0 关闭） |
| `RENDER_AUTH_TOKEN` | 未设 | 设则数据端点要求 `Authorization: Bearer <token>`（401 否则）；`/healthz` 豁免；不设=无认证（现状） |
| `RENDER_ASSUME_NO_NETWORK` | 未设 | Linux 容器以 `--network none` 运行时设为 `1`，使渲染报告如实记录 `network_isolated`（A6 镜像负责设置） |

## 备注

- **缓存键中"渲染器版本"的规范定义 = render_cli 二进制 sha256**（方案文字
  "子模块 SHA"的运行时等价物，亦覆盖 worktree 开发二进制；随 A7 落档）。
- 渲染类测试在无二进制环境自动 skip——**CI 渲染通道必须对 skip 判失败**
  （D3 接线时用构建产物跑全量并断言 0 skipped），防止快乐路径静默失测。
- 每个产物旁存 `<key>.report.json`（`vemcad.render_service_report`：参数、
  哈希、耗时、`network_isolated`）。B1 落地后 render_cli 自身的
  `vemcad.render_report`（view rect/实体计数/字体记录）将内嵌于其下。

## 包验证器（`/package`、`validate_package`）

实现契约 §9（2D 至 standard 封顶，A4 上限）：仅"manifest 不可解析 / 未知
major / 身份字段缺失（package_id、source.sha256、producer.plugin_name/
host_app）"拒收，其余一律降级+生效等级兜底（检入永不被阻塞）；按 payload
逐项隔离（sha/size/格式/§2.4 上限）；`rich` 永不授予；3D discipline 仅记
unsupported note。身份 upsert 键 = (tenant, source.sha256, plugin_name,
host_app, schema_major)，按租户隔离索引、拒绝跨身份劫持同 package_id、指针
不回退到更低 plugin_version。package_id/tenant 经安全字符校验，禁止路径穿越。

**记录性偏差（待 A7/PR-S7b 正式落档）：**
- **完整性/pending-TTL 简化**：契约 §2.1 设想"载荷未到齐→pending 态+TTL"。
  v0 简化为：缺失载荷立即按 payload 隔离并定稿，同身份再提交走 upsert
  顶替——无 pending/TTL 状态机。
- **包总量 1 GiB 上限以 413 拒收**（传输层防护）而非按条隔离；按条隔离
  适用于 manifest 内声明的单条超限（≤256 条、单载荷≤512 MiB、栅格≤64 MP，
  均已实现为隔离）。
