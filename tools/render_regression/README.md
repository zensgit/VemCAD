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

需要把这个判断接入脚本或审计记录时，使用机器可读 view-space contract：

```bash
python3 tools/render_regression/compare_vs_acad.py acad.png ours.png \
  --viewspace-report viewspace.json \
  --require-viewspace-match
```

`--viewspace-report` 写出 `schema=vemcad.x3_viewspace_contract/v1`，包含
`status=match|mismatch|unavailable`、填充比、阈值、X3 summary 与建议动作。
`--require-viewspace-match` 在 `mismatch`/`unavailable` 时返回 `2`，用于阻止
把不同窗 AutoCAD PNG 的低分误当成 renderer fidelity 结论。默认不加该 flag 时，
CLI 仍保持诊断用途并返回 `0`。

> 实例 G11：填充比 HEIGHT 差 ~0.10 触发，而 aspect_delta 0.0569 仍 **低于**
> ASPECT_TOL——即原 aspect 守卫静默、正是本检测要补的盲区。

### AutoCAD reference request / route artifacts（无人值守流）

当一批候选图需要 fresh matched-view AutoCAD PNG 时，不直接从低 X3 分数开渲染器
缺陷。先生成/履行 reference request，再用 artifact route 决定下一步：

```bash
python3 tools/render_regression/acad_manifest_compare.py \
  --manifest <acad_manifest.json> \
  --candidate-cases <candidate_cases.json> \
  --out-dir <compare-dir>

python3 tools/render_regression/acad_reference_batch.py \
  --validate-request <compare-dir>/reference_request.json \
  --candidate-cases <candidate_cases.json> \
  --require-request-boundary autocad_equivalence_claim=false \
  --require-request-boundary requires_returned_autocad_png=true \
  --require-request-boundary requires_viewspace_match=true \
  --out-dir <request-validation-dir>

python3 tools/render_regression/acad_reference_request_run.py \
  --from-request <compare-dir>/reference_request.json \
  --candidate-cases <candidate_cases.json> \
  --reference-dir <returned-autocad-png-dir> \
  --require-request-boundary autocad_equivalence_claim=false \
  --require-request-boundary requires_returned_autocad_png=true \
  --require-request-boundary requires_viewspace_match=true \
  --fail-on-input-review \
  --out-dir <run-dir>

python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --text \
  --require-source-boundary autocad_equivalence_claim=false \
  --require-request-boundary autocad_equivalence_claim=false \
  --require-request-boundary requires_returned_autocad_png=true \
  --require-request-boundary requires_viewspace_match=true
```

`acad_reference_request_run.py` writes `run_summary.json/md` and a run-level
`artifact_index.json`. These carry both `case_action_counts` and
`case_action_domain_counts`, plus `recommended_next_action.domain`, so the run
summary itself distinguishes input/recapture gates from renderer-candidate
work before a separate route report is generated. The run summary and run-level
artifact index keep returned-reference intake warnings visible even when the
matched-view compare itself passes. By default those warnings remain a review
lane rather than a hard failure; pass `--fail-on-input-review` when an
unattended job should exit `2` if the run's recommended action is in the
`input-review` domain.
The run summary and run-level
artifact index also surface route-level `route_count`, `route_kind_counts`,
`route_status_counts`,
`route_recommended_action_counts`, and
`route_recommended_action_domain_counts`, so operators can inspect the routed
artifact topology without opening `route_summary.json`. When compare artifacts
are present, the same run summary and artifact index also surface
`route_compare_case_count`, `route_compared_count`, `route_triage_bucket_counts`,
`route_viewspace_status_counts`, and `route_x3_band_counts`, so operators can
see whether the compare portion is matched, recapture-required, or an X3
failure distribution without drilling into the nested route summary. The wrapper
prints those same route compare distributions to stdout when they are present,
so CI logs also show the compare portion without opening uploaded artifacts.
It also prints the run-level `route_summary.md` path, matching the batch and
compare CLIs. It also writes
`case_actions.tsv` for spreadsheet-friendly per-case sorting/filtering by action
code, domain, source, triage bucket, view-space status, X3 band, and resolved
handoff artifact. Each `case_actions` JSON row and TSV row includes the
original action artifact plus `artifact_resolved` / `artifact_exists` when a
handoff file is available.
When returned AutoCAD PNGs are still missing, `acad_reference_batch.py` writes
`missing_references.tsv` beside the JSON/Markdown report so the expected
source DXF, optional source hash, output filenames, paths, capture method, view
contract, and expected size can be handed off in spreadsheet form. The
Markdown handoff shows the same source SHA column, so a human can verify source
identity without opening JSON or TSV. The `acad_reference_request_run.py`
wrapper also surfaces that TSV in its run summary and artifact index when the
request is input-blocked.
The request validation report itself also records the requested expected size
per row, so operators can verify the capture-size contract before any returned
AutoCAD PNG exists.
Both request validation and returned-reference intake reports print
`issue_code_counts` at the top, so operators can see the issue classes without
scanning per-case tables. Returned-reference intake also prints the requested
expected size next to the actual returned PNG size and blocks with
`returned_png_size_mismatch` when a returned AutoCAD PNG does not match the
request-declared size; in that case the run stops before writing a compare
manifest. The intake Markdown table also prints a compact diagnostic-only
identity advisory (`returned=...`, `candidate=...`, optional
`aspect_delta=...`) so operators can spot likely wrong-file, blank-export, or
capture-window issues without opening `reference_intake.json`.
The request-validation, missing-reference, and intake Markdown tables escape
operator-supplied cells (`|`, newlines, and code-span edge cases), so drawing
IDs and output filenames cannot silently corrupt the table shape.
The one-command request-run Markdown summary applies the same escaping to its
case-action table and artifact links, keeping the top-level unattended-run
handoff safe for unusual drawing IDs or output paths.
The manifest-compare summary and generated recapture request tables use the
same safe Markdown table/code-cell formatting for case IDs, drawing IDs, and
requested output names.
Generated recapture request Markdown also surfaces the source DXF and candidate
PNG SHA256 values already stored in `reference_request.json`, so handoffs can
verify identity without opening the JSON first.
It also shows the current view-space status, current X3 band, and requested
expected size for each recapture case, so the handoff explains why a fresh
AutoCAD export is needed and what size contract it should satisfy.
Route Markdown reports also use safe code spans for action artifacts and count
summaries, so unusual artifact paths remain readable in the top-level route
handoff.
When a compare route recommends `recapture-autocad-or-provide-window`, the
route action artifact points directly at the generated `reference_request.md`
when that request exists.
The batch, compare, and request-run CLIs also print the recommended action
domain next to the action code, so CI logs can show the route class without
opening JSON artifacts.
When a recommended action has a handoff artifact, those CLIs also print the
artifact path, the resolved path, and whether it exists. The one-command
request-run wrapper also carries that resolution in `run_summary.json/md` and
the run-level `artifact_index.json`, so uploaded run artifacts and CI logs both
point directly at the handoff file.
For one-command request runs, per-case `case_actions` rows use the same
recapture handoff: a `recapture-autocad-or-provide-window` case points at
`compare/reference_request.md` when generated, while matched/pass review cases
still point at the compare summary.
The run-level artifact index and run summary also list
`compare_reference_request_json` and `compare_reference_request_markdown` when
the compare phase generated a recapture request, so automation can discover the
handoff without opening the nested compare artifact index first.
`acad_manifest_compare.py` also writes per-case `recommended_action_domain`
values into `summary.json`, `summary.tsv`, `summary.md`, and the compare
artifact index counts. A `viewspace_mismatch` case therefore remains an
`input` domain case even when its raw X3 pixels look bad.

These operator-facing tools are safe to rerun against the same generated
`--out-dir`; they clear their own known generated outputs before writing the new
run. `acad_manifest_compare.py` clears compare summaries, contact sheets,
reference requests, overlays, viewspace, semantic, and text diagnostics.
`acad_reference_request_run.py` clears run-level reports and the stale
`compare/` directory while leaving `input/` ownership to
`acad_reference_batch.py`, which clears and rewrites its own batch artifacts.
The legacy `autocad_batch_compare.py` clears its summaries, contact sheets, and
optional semantic/tile output directories. Do not place hand-authored files
inside these generated output directories if they need to survive a rerun.

`artifact_index.json` 与 `route_summary.json/md` 都是机器可读的操作入口：

- artifact indexes carry `boundary` metadata (`renders_dxf`,
  `compares_renders`, `changes_x3_scoring`, `changes_renderer`,
  `autocad_equivalence_claim`) so CI can tell whether an artifact is input
  prep, compare output, or a one-command run summary.
- route reports carry top-level `recommended_next_action`, including
  `fix-request-package`, `provide-returned-autocad-pngs`,
  `fix-returned-reference-input`, `recapture-autocad-or-provide-window`,
  `inspect-renderer-candidate`, and `review-x3-pass`.
- when the routed source artifact already contains a human-readable action
  report, route reports also surface it as `action_artifact`.
- every recommended action also carries `domain`, such as `input`,
  `renderer-candidate`, `pass-review`, or `continue`, so unattended jobs can
  distinguish "get better AutoCAD input" from "inspect renderer output" without
  parsing action-code strings.
- multi-route top-level actions prioritize input-package fixes and returned
  AutoCAD PNG input errors before renderer-candidate work; do not open renderer
  work while returned-reference intake is `blocked`.
- `acad_artifact_route.py --require-action <code>` exits `2` if the top-level
  action is not the expected one. Example CI guard:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-action review-x3-pass
```

When a script only needs to assert the action class, use
`--require-action-domain <domain>`. For example, this fails closed if a batch
routes to renderer work instead of an input/recapture gate:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-action-domain input
```

Use `--forbid-action-domain <domain>` when a mixed route must fail even if the
top-level action points somewhere else. This is useful for unattended input
runs that should not hide a `renderer-candidate` route behind a higher-priority
input repair:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-action-domain input \
  --forbid-action-domain renderer-candidate
```

Use `--forbid-action <code>` when a workflow should allow an action domain but
fail closed on a specific action code. For example, an input-domain gate can
still reject stale matched-view work that routes to
`recapture-autocad-or-provide-window`:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-action-domain input \
  --forbid-action recapture-autocad-or-provide-window
```

Use `--require-action-count <code=count>` when a workflow needs to assert the
exact routed action distribution. For multi-route payloads this checks
`recommended_action_counts`; for request-run payloads it checks
`case_action_counts`; for a single route it checks the top-level action as
count `1`.

Use `--require-action-domain-count <domain=count>` when a workflow needs to
assert the exact routed action-domain distribution. This is useful when an
operator gate must prove the route contains only the expected mix of `input`,
`renderer-candidate`, `pass-review`, and `continue` work without enumerating
every specific action code.

Use `--require-status <status>` / `--forbid-status <status>` when a workflow
needs to assert the routed status distribution itself, such as requiring
`viewspace_mismatch` in a recapture test or forbidding any nested `blocked`
artifact in a supposedly ready batch.

Use `--require-kind <kind>` / `--forbid-kind <kind>` when a workflow needs to
assert the routed artifact topology itself. This catches incomplete recursive
inputs, such as a run that accidentally uploads only the input batch artifacts
and never includes the compare artifact index.

Use `--require-route-count <n>` when a workflow also needs to prove the
recursive route discovered the expected number of artifact indexes. This catches
missing or extra extracted artifacts that still happen to include the expected
topology kinds.

When a workflow also needs to assert that the chosen action points at the
expected handoff artifact, use `--require-action-artifact <path-suffix>`.
Suffix matching keeps the guard stable across absolute CI paths:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-action provide-returned-autocad-pngs \
  --require-action-domain input \
  --require-action-artifact missing_references.md
```

Add `--require-action-artifact-exists` when the workflow should also prove the
handoff file is present. Relative action artifacts resolve from the source
`artifact_index.json` directory, not from the shell's current directory.
Route JSON, text, and Markdown also surface that same resolution as
`action_artifact_resolved` plus `action_artifact_exists`, so CI logs and
uploaded route reports can point directly at the handoff file without a second
artifact-index lookup.
Batch artifact indexes and route reports also surface
`reference_request_validation_issue_code_counts` and
`reference_intake_issue_code_counts` when those preflight reports exist. This
lets CI jobs that stop at the input stage show the exact request/intake issue
codes without opening nested JSON artifacts.
When routing multiple artifact indexes at once, the top-level route summary
aggregates those same issue-code counts across all nested routes.

Use `--require-issue-code <code>` or `--forbid-issue-code <code>` when a CI
route step must fail closed on specific request/intake issue classes. These
guards inspect only routed request/intake issue-code counts; they do not parse
action codes or triage buckets.

Use compare-distribution guards when a workflow needs to assert the compare
portion itself, even if a higher-priority input route controls the top-level
recommendation:

- `--require-compare-case-count <n>`;
- `--require-compared-count <n>`;
- `--require-triage-bucket <bucket=count>` /
  `--forbid-triage-bucket <bucket>`;
- `--require-viewspace-status <status=count>` /
  `--forbid-viewspace-status <status>`;
- `--require-x3-band <band=count>` / `--forbid-x3-band <band>`.

For example, this fails closed if any nested compare route still has a
view-space mismatch, even when the top-level action is an input repair:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-compare-case-count 1 \
  --require-compared-count 1 \
  --forbid-viewspace-status mismatch
```

And this asserts a matched renderer-candidate distribution exactly:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-compare-case-count 1 \
  --require-compared-count 1 \
  --require-triage-bucket renderer-candidate=1 \
  --require-viewspace-status match=1 \
  --require-x3-band fail=1
```

To assert source artifact boundaries as part of the same route step, repeat
`--require-source-boundary key=value`. For example, this guarantees every
routed source artifact explicitly says it is not an AutoCAD-equivalence claim:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-source-boundary autocad_equivalence_claim=false
```

When the workflow needs to prove the original AutoCAD recapture request also
survived the handoff, add `--require-request-boundary key=value`. The guard
checks every routed artifact that exposes `source_request_boundary`, ignores
compare-only routes that do not own the request package, and fails if no routed
artifact exposes the request boundary at all:

```bash
python3 tools/render_regression/acad_artifact_route.py <run-dir> \
  --recursive \
  --require-source-boundary autocad_equivalence_claim=false \
  --require-request-boundary autocad_equivalence_claim=false \
  --require-request-boundary requires_returned_autocad_png=true \
  --require-request-boundary requires_viewspace_match=true
```

这只是 route assertion：它不重新比较图、不渲染 DXF、不调整 X3 阈值，也不声称
AutoCAD 等价。`viewspace_mismatch` 仍然路由到重新导出 AutoCAD PNG 或提供明确
world window；只有 `viewspace_status=match` 且 X3 非 pass 的 case 才进入
renderer-candidate 桶。

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

When the case also provides `semantic_mask` and `semantic_report`,
`--tile-grid` additionally writes `semantic_tile_summary.json` and
`semantic_tile_summary.tsv`. Those rows split each local tile by the
candidate-renderer semantic classes emitted by `render_cli` (for example
`geometry`, `text`, `dimension`, `hatch`). AutoCAD still has no semantic mask,
so the values are candidate-class overlap with AutoCAD ink, not true
reference-vs-candidate semantic IoU.

测试：`python3 -m pytest tools/render_regression/tests -q`。测试数量随
evidence/operator hardening 增长，以 pytest 输出为准；这些测试使用合成图，
无需 render_cli。
