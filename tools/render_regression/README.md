# 渲染回归语料（冻结清单与治理规则）

任务：Phase 1 **D0**（见 `docs/VEMCAD_RENDER_SERVICE_PHASE1_DEVELOPMENT_20260610.md`）。

## 冻结清单

| 清单 | 内容 | 计数 |
|---|---|---|
| `corpus_manifest_dxf.json` | `~/Downloads/训练图纸/训练图纸_dxf/` 全部 `.dxf`（sha256+size） | 110（52 张图，各 1–4 版） |
| `corpus_manifest_dwg.json` | `~/Downloads/训练图纸/训练图纸/` 全部 `.dwg`（110 与 DXF 同名） | 114 |

- 一切验收（M1b、D2、C6）以清单内文件 + sha256 为准；目录里后续新增/改动的文件
  不自动进入语料，须重新冻结（新版本清单 + PR）。
- AutoCAD 锁文件（`.dwl`/`.dwl2`，含用户名/主机名）已剔除，**禁止**进入任何
  清单、存储或报告。

## 治理规则（D0，冻结于 2026-06-10）

1. **用途**：仅限内部质量回归（X4 已确认，2026-06-10）；不得用于训练、对外
   演示或公开样例。
2. **存储**：语料文件留在私有位置；本仓库只存哈希清单，**不存图纸本体**。
3. **报告**：回归报告（含渲染图像）只落私有 CI/工件库，**不出公共 CI**；
   保留期默认 90 天，超期清理。
4. **试点子集**：C0 从 DWG 清单预选 ≥10 张（记录其 sha256 子清单于 C0 交付物）。
5. 清单更新（增删图纸、版本变化）只经 PR，说明原因并附前后计数。

## D2 回归台（compare / baseline / regress）

依赖：numpy + PIL（纯 Python，无 scipy）。

- `compare.py` —— 比对两张同图渲染：二值化→墨迹 bbox 裁剪→统一画布→小平移
  搜索对齐；门控指标 = 膨胀容差（默认 2px）的墨迹 IoU（F1 式），SSIM 仅参考；
  §5 语义：`background+color_mapping+视图空间`不齐时 skip-and-flag；按
  `capture_method` 信任加权（offscreen-render/plot-raster=可门控、
  viewport-capture=advisory、dwg-thumbnail=record）；分带 pass/review/fallback。
- `baseline.py` —— 基线治理：sha256 清单（`baselines.json`，图像走工件库/LFS、
  不进 git），三层 self/ref-render/acad（acad>ref-render>self），记录需具名
  批准人，按字节校验防漂移。
- `regress.py` —— 编排：渲染每张 golden → 与最佳基线 compare → 分带报告；
  `--update-baseline self --approver NAME` 记录自基线。门控失败 = 被门控图在
  gate 信任下落 fallback 带、或渲染失败；NO-BASELINE/advisory/record 不门控。
  渲染步骤可注入（合成图单测验证逻辑；端到端 render_cli 运行在 CI——本地
  Homebrew Qt 暂不可用）。
- `golden/golden.json` —— D1 金样集 v1（2D 子集）；FIELD/ACAD_TABLE/XREF/天正
  类列于 `deferred`（插件产出或 Phase 2）。D3 负责把 pytest + 端到端接入 CI。

测试：`python3 -m pytest tools/render_regression/tests -q`（18，合成图，无需 render_cli）。
