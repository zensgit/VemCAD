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

**已知缺口（对冻结计划 §5 的诚实偏差，待 B 线补）**：D2 v0 **没有文字/几何
分离打分**——§5 要求"文字区/几何区分开打分（字体替换期几何分才门控）"，但
真正的分离需要渲染端提供文字掩膜（render report 现仅给文字计数，非像素区域）。
v0 的门控指标 `ink_iou` 是文字+几何合并值（**故不命名 geometry_***），且文字
密集金样置 `gate=false`，使字体替换期不会误判门控。补救方向：render_cli 输出
文字 bbox/分层渲染 → 拆 `text_iou` + `geometry_iou`、仅几何门控。另外 ink_iou
对**颜色**与**纵横比**回归本身盲（灰度+bbox 归一），故 compare 另出
`color_dist`/`aspect_delta`，超阈值把 pass 降级 review，不让其静默通过。

## 版本可视化对比（diff.py，L1 旗舰引擎）

依赖同上：numpy + PIL。这是**收费项**"图纸版本可视化对比"的可验证内核——
给同一张图的两个版本渲染（Rev A=参照、Rev B=候选），输出三色高亮图让审图
一眼看出改了哪。

- `diff.py` —— **复用 compare 的对齐与墨迹掩膜**（二值化→墨迹 bbox 裁剪→统一
  画布→小平移搜索），对齐后逐墨迹像素分类：
  - `unchanged`（灰 `170,170,170`）—— 两版都有墨迹（容差内）；
  - `removed`（红 `220,30,30`）—— 只在 A、B 里没了；
  - `added`（绿 `30,160,30`）—— B 里新增。
  分类带**膨胀容差**（默认 2px，同 compare），故 ≤tol 的 AA/hinting 抖动不算改动；
  小平移先被对齐吸收。产出 3 色 overlay PNG + `DiffResult`（`changed_fraction`
  = (added+removed)/墨迹并集 ∈[0,1]，及 `unchanged/added/removed` 像素数、`dx/dy`）。
- **可比性同 §5 铁律（引擎自判，不只信调用方）**：两版须共享
  `background+color_mapping+视图空间`。引擎按各自外延 fit，故当两版墨迹 bbox
  纵横比差超 `ASPECT_TOL` → `comparable=False`、`skip_reason=view-space-mismatch`
  （不出误导叠加图；改外延的版本留待"共同窗口"后续）。两版皆空 → `both-blank`。
- **纯图入/图出**——不在此渲染（两张输入由渲染服务产出）。合成 PIL 对验证
  （确定性、无需 render_cli）。
- CLI：`python3 tools/render_regression/diff.py REV_A.png REV_B.png --out overlay.png`
  → stdout 打 JSON 摘要、写 overlay。
- **产品化形态**：渲染服务 `POST /diff` **已落地**（`services/render`：收两版
  DXF → 各走 /render 四元组缓存出 PNG → 本引擎出 overlay+摘要；契约见 A7 §4.3）；
  下一步 Yuantus `/cad/diff?v1=&v2=` 走版本库取两版 → 调服务 → 前端展示。属 L1
  收费功能（见 `docs/VEMCAD_RENDER_PRODUCTIZATION_NOTE_20260613.md`）。

## X3 媲美 AutoCAD 对比（compare_vs_acad.py）+ 取图/视图空间一致性检测

`compare_vs_acad.py` 复用 D2 comparator（对齐 + 墨迹 IoU + color/aspect 守卫）
和 `diff.py`（三色叠加），把"像不像 AutoCAD"变成一个可引用的分数。**纯图入**：
喂两张 PNG（参照=AutoCAD，候选=我们）。

### 取图契约（apples-to-apples，必须先满足）

X3 分数只有在**两张图同处一个视图空间**时才有意义。AutoCAD 参照必须按下式产出：

- **PLOT / EXPORTPNG（或 PUBLISH）按"图形范围/EXTENTS"出图**（fit-to-EXTENTS），
  与 render_cli 的模型空间外延一致；**不要**用某个图纸/布局的 paper-space 版面
  （版面会把图形按页边距内缩，填充比/纵横比都与外延渲染对不上）。
- **白底**、**单色(monochrome) 关闭**（保留各图层颜色，否则 color_dist 误报）。
- **与我们的渲染同纵横比**，长边 ≥ 1600 px。

### 取图不一致 → 不是渲染缺陷（framing/capture mismatch 检测）

D2 对齐故意"各自按墨迹 bbox 裁剪再统一画布"，因此**对图形在页面上的位置与
填充比是盲的**——这在同视图空间下是对的，却会让"paper-space PLOT（墨迹被页边距
内缩）vs 模型外延渲染（墨迹铺满画框）"这种**取图不一致**伪装成低 IoU、被误读为
渲染失真。

`compare.framing_divergence(ref, cand)`（纯函数、确定性、无副作用，复用
`_ink_mask`/`_ink_bbox`）在出 IoU 判定**之前**先量两个被门控指标丢弃的视图空间
信号：

- **页面填充比/轴** = 墨迹 bbox 边长 ÷ 图像边长；paper PLOT 与外延渲染即使几何
  相同也会在此分叉。
- **aspect_delta** = `|1 - cand_aspect/ref_aspect|`（与 compare 的 aspect 守卫同定义）。

`framing_mismatch` = 任一轴填充比差 > `FRAMING_TOL`(0.05) **或** aspect_delta >
`ASPECT_TOL`(0.06)。命中时 `compare_vs_acad.py` 改打：
**`NOT COMPARABLE (framing/capture mismatch)`**——并打印各轴填充比与 div 数值——
明确这是**取图窗口不同**，而非渲染器错误；正常 IoU 判定（EXCELLENT/CLOSE/
DIVERGENT）被抑制，避免误归因。`framing_divergence` 只读图、**不动** `compare()`
的 `CompareResult`、也不影响 D2/regress 门控。

> 实例 G11：填充比 HEIGHT 差 ~0.10 触发，而 aspect_delta 0.0569 仍 **低于**
> ASPECT_TOL——即原 aspect 守卫静默、正是本检测要补的盲区。

**真正能改分的对等修复**（让 render_cli 按 `--window` 渲到与 AutoCAD 同窗，或把
AutoCAD 参照重新按 EXTENTS 导出）需要 AutoCAD 环境/渲染端改动，**不在本次改动
范围**；本检测只负责正确"归因"——把一对 framing 不一致的图标出来，不假装它是渲染
缺陷。

`autocad_batch_compare.py --candidate-frame reference-envelope` is a
diagnostic-only batch mode for existing AutoCAD references. It writes temporary
candidate PNGs under the output directory, framing the VemCAD ink into the
AutoCAD PNG's ink envelope before scoring. Use it to answer "does this mismatch
survive after paper/capture envelope differences are removed?" It is not a
render-service mode and not a pass/fail gate; the original candidate path is
preserved as `source_ours` in the summary.

`autocad_batch_compare.py --tile-grid COLSxROWS` adds a local-error diagnostic
on top of the same global X3 alignment. For each pair, the tool crops/resizes
both sides to the comparator canvas, applies the normal small translation
alignment, then scores each grid tile. It writes `tile_summary.json`,
`tile_summary.tsv`, and `tile_heatmaps/*_tile_heatmap.png`. Use this when a
global Ink-IoU score only says "bad" but not whether the miss is concentrated
in a title block, table, dense text area, or main geometry. This is diagnostic
only: it is not a semantic split and does not create a new pass/fail gate.

测试：`python3 -m pytest tools/render_regression/tests -q`（57 tests，合成图，
无需 render_cli）。
