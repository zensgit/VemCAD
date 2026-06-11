# vemcad-render — 渲染服务 v0（Phase 1 WS-A）

把 CADGameFusion `render_cli`（共享 scene renderer 的无头出口）包装为内网 HTTP
服务。规格出处：`docs/VEMCAD_RENDER_SERVICE_PHASE1_DEVELOPMENT_20260610.md`
（A2a/A3），正式接口契约随 A7 落档（W3）。

## 端点（v0）

- `GET /healthz` — 服务状态、render_cli（路径/sha256/冒烟结果）、字体目录
  （数量/指纹）、并发水位。
- `POST /render` — multipart 字段 `file`（**仅 DXF**，默认上限 48 MiB）+
  查询参数 `format=png|svg`、`width`、`height`（16–8192，且 width×height ≤
  64 MP）、`bg=dark|white|#RRGGBB`、`view=extents`（v0 唯一取值）。
  命中四元组缓存（内容 sha256 + 规范化参数 + render_cli 二进制 sha256 +
  字体库指纹）直接回图，响应头 `X-Render-Cache: hit|miss`、`X-Render-Key`。
  饱和返回 429。错误一律结构化信封
  `{"status":"error","error_code":...,"error":...}`（口径同 ROUTER_CONTRACT）。

## 安全姿态（Phase 1）

仅内网绑定、无认证、429 背压；渲染在沙箱子进程中执行（超时、内存上限、
独立临时目录、最小环境变量；macOS 开发机经 `sandbox-exec` 尽力禁网并记录，
Linux 正本由容器层 `--network none` 强制）。详见方案 A3/A7。

## 运行

```bash
export RENDER_CLI_PATH=/path/to/render_cli   # 缺省自动找 deps/cadgamefusion/build/editor/qt/render_cli
python3 -m uvicorn app.main:app --factory --host 127.0.0.1 --port 8077
# app.main:app 为工厂函数 create_app
```

测试：`RENDER_CLI_PATH=... python3 -m pytest services/render/tests -q`
（无二进制时渲染类用例自动跳过，参数/缓存单测照跑）。

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
| `RENDER_ASSUME_NO_NETWORK` | 未设 | Linux 容器以 `--network none` 运行时设为 `1`，使渲染报告如实记录 `network_isolated`（A6 镜像负责设置） |

## 备注

- **缓存键中"渲染器版本"的规范定义 = render_cli 二进制 sha256**（方案文字
  "子模块 SHA"的运行时等价物，亦覆盖 worktree 开发二进制；随 A7 落档）。
- 渲染类测试在无二进制环境自动 skip——**CI 渲染通道必须对 skip 判失败**
  （D3 接线时用构建产物跑全量并断言 0 skipped），防止快乐路径静默失测。
- 每个产物旁存 `<key>.report.json`（`vemcad.render_service_report`：参数、
  哈希、耗时、`network_isolated`）。B1 落地后 render_cli 自身的
  `vemcad.render_report`（view rect/实体计数/字体记录）将内嵌于其下。
