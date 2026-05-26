# VemCAD Project Runtime v0 动工计划

- 状态：**规格冻结，动工就绪（FROZEN / ready to build）**
- 日期：2026-05-25
- 范围目录：`apps/runtime`
- 关联文档：`docs/VEMCAD_MODULE_DESIGN.md`（Phase 1）、`docs/VEMCAD_DEVELOPMENT_PLAN.md`、`docs/VEMCAD_PROJECT_RUNTIME.md`

## Summary

当前阶段只开发 `apps/runtime`，把 Project Runtime 立为 VemCAD 的**工程真相来源**，并让 CADGF Document 成为**稳定、可校验的派生格式**。v0 不碰 Qt、不引入 OCCT、不拆 Web 大文件、不做 3D 特征建模；先完成格式、序列化、导入/派生、映射和验收基线。

本规格冻结以下动工约束：

- schema 校验从 `node --test` 拆成**独立 Python 校验步骤**，不污染纯 Node 测试。
- CADGF 文档字段按 **project-owned / passthrough-owned / deriver-owned** 三类归属。
- 单位**导入宽松降级、派生严格枚举**。
- 提交**黄金样本**防止工程格式无意漂移。
- 所有默认时间戳走**可注入固定时钟**，派生路径禁止 `Date.now()`。

## 范围

### 本轮做（in scope）

- `apps/runtime` 下纯 ESM Runtime 模块 + `node:test`。
- `VEMCAD-PROJECT` v1 格式：创建、解析、迁移、规范化、确定性序列化。
- `Project → CADGF Document` 稳定派生（可通过 `document.schema.json` 校验）。
- `CADGF Document → Project` **降级导入**。
- 唯一实体映射表（`point/line/polyline/circle/arc/text`）。
- Web bridge 薄桥（走 CADGF 语义）。

### 本轮不做（out of scope，进入后续阶段）

- Qt 主线改动（Qt 继续作为 fidelity inspector）。
- OpenCASCADE / BRep / 3D 特征建模。
- Web Workbench 大文件拆分（`command_registry.js` / `workspace.js`）。
- Router 直接依赖 Runtime（本轮只补 contract 说明）。
- `ellipse/spline/block/hatch/dimension` 的编辑语义（v0 仅 passthrough 保真）。

## Key Changes

### 1. Runtime 模块

新增纯 ESM Runtime 模块：

- `project`：创建、解析、迁移、规范化、确定性序列化 `VEMCAD-PROJECT`。
- `scene`：`deriveCadgfDocument(project, options)` 与 `importProjectFromCadgfDocument(cadgfDocument, options)`。
- `constraint`：v0 只保存和规范化约束，不求解。
- `feature`：v0 保存 feature 列表并生成 no-op rebuild plan。

统一结果对象：

```js
{ ok: true,  value, diagnostics: [] }
{ ok: false, error_code, error, diagnostics: [] }
```

### 2. Project v1 固定结构

```js
{
  header: { format: "VEMCAD-PROJECT", version: 1 },
  project: { id, name, units, createdAt, modifiedAt },
  layers: [],
  entities: [],
  constraints: [],
  features: [],
  resources: {
    cadgfPassthrough: {
      document: {},
      entities: []
    }
  },
  meta: {}
}
```

### 3. CADGF 文档字段归属（三类，冻结）

派生 `Project → CADGF Document` 时，每个 CADGF 字段的取值来源固定如下三类。完整性/一致性对 `document.schema.json` 的核对见[附录 A](#附录-acadgf-字段归属对-schema-的完整性核对)。

| CADGF 字段 | 归属 | 取值规则 |
|---|---|---|
| `cadgf_version` | **deriver-owned** | 永远写**派生目标版本**，不从 passthrough 回吐 |
| `schema_version` | **deriver-owned** | 永远写**派生目标版本**，不从 passthrough 回吐 |
| `schema_migrated_at` | **deriver-owned** | 源版本 == 目标版本时保留 passthrough；源版本不同时写入注入时钟 `clock.now()`（派生即迁移事件） |
| `document_id` | project-owned | 来自 `project.id` |
| `metadata.label` | project-owned | 来自 `project.name` |
| `metadata.unit_name` | project-owned | 来自 `project.units`（见单位规则） |
| `settings.unit_scale` | project-owned | 来自 `project.units`（见单位规则） |
| `feature_flags` | passthrough-owned | 视为"源文档能力/声明"保留 |
| `metadata.author` | passthrough-owned | 保留 |
| `metadata.company` | passthrough-owned | 保留 |
| `metadata.comment` | passthrough-owned | 保留 |
| `metadata.created_at` | passthrough-owned | 保留 |
| `metadata.modified_at` | passthrough-owned | 保留 |
| `metadata.meta` | passthrough-owned | 保留 |

补充规则：

- **新建 Project（无 passthrough）** 时合成完整默认 CADGF 字段；其中 `metadata.created_at/modified_at` 必须来自 `project.createdAt/project.modifiedAt`，缺失时才使用注入的 `clock.now()`，**派生路径禁止直接调用 `Date.now()`**。
- `feature_flags` v0 视为"源文档能力/声明"保留；新建 Project 写当前 CADGF schema 需要的安全默认值，**不表示 JS 派生器实际运行 earcut/clipper2**。
- `project.meta` 是 **VemCAD 私有命名空间**，**不**回吐到 CADGF `metadata.meta`（二者是不同命名空间）。
- 导入项目的 `metadata.created_at`（passthrough，源 CADGF 创建时间）与 `project.createdAt`（VemCAD 工程创建时间）会合法地不同——语义本就不同，符合预期。

### 4. 单位规则（导入/派生分开）

- **派生方向（严格）**：仅支持 `mm/cm/m/in/ft` 到 `metadata.unit_name + settings.unit_scale` 的固定换算表；未知 Project 单位返回 `ok:false`。
- **导入方向（宽松降级）**：先按 `metadata.unit_name` 归一化匹配，再按 `settings.unit_scale` 近似匹配；仍失败则**回落 `mm`**、写入 diagnostic，并把**原始 `unit_name/unit_scale` 保存在 passthrough**。导入只降级、不拒绝。

### 5. passthrough 输出过滤

`resources.cadgfPassthrough.document` 输出前按目标 CADGF schema 过滤 key：

- 目标 schema 固定为当前 `deps/cadgamefusion/schemas/document.schema.json`。
- 当前 schema 不允许的 passthrough root key **不吐回** CADGF Document，只保留在 Project 文件里。
- 源 schema 不匹配时返回 diagnostic，**仍按当前目标 schema 安全派生，且版本字段写目标版本**。

### 6. 唯一实体映射表

- `Project entity kind ↔ CADGF numeric type` 是**唯一权威**，由 `apps/runtime/scene` 内一个映射模块统一维护。
- Web bridge 走 CADGF 语义，不单独维护 `Project ↔ Web` 平行映射；**开工估算前先核实现有 Web 是否已有 `DocumentState → CADGF 数字快照` 导出方向**。
- v0 支持 `point/line/polyline/circle/arc/text`；`ellipse/spline/block/hatch/dimension/unknown` 进入 passthrough，不丢弃。
- 新建实体无 `cadgfId` 时，numeric id 按规范化后的**稳定顺序**分配；已有 CADGF id 优先保留，**冲突时报 diagnostic**。

### 7. 确定性契约

- `normalizeProjectModel()` 与 `serializeProjectModel()` **不自动改** `createdAt/modifiedAt`。
- `deriveCadgfDocument()` 合成默认 CADGF 字段时只使用 Project 时间戳或注入时钟，**不使用活时间**。
- `layers / entities / constraints / features / resources.cadgfPassthrough.entities` **全部按 id 稳定序列化**。
- 提交一个固定输入的**黄金 Project 文件**，测试输出字节必须等于黄金文件。

### 8. CADGF 导入是降级导入

- 函数名使用 `importProjectFromCadgfDocument`，**不**命名为反向 derive（二者不是数学逆函数）。
- 导入结果默认 `constraints: []`、`features: []`。
- diagnostics 明确报告：CADGF 不携带 VemCAD constraints/features；CADGF 往返还可能归一化可选字段（例如 `document_id` 从无变有）；**Project 原生 save/load 才是唯一无损路径**。

## Test Plan

### 纯 Node 测试（不调 Python）

```bash
node --test apps/runtime/tests/*.test.js apps/web/tests/*.test.js
```

| 测试文件 | 覆盖点 |
|---|---|
| `project_schema_roundtrip.test.js` | v1 roundtrip、v1 migration no-op、未知未来版本拒绝 |
| `project_golden_serialization.test.js` | 固定输入序列化结果等于提交进仓库的黄金文件 |
| `project_deterministic_save.test.js` | 重复序列化字节一致；normalize/serialize/derive 都不调用活时间；所有集合按 id 稳定排序 |
| `cadgf_document_meta_ownership.test.js` | deriver-owned 写目标版本；project-owned 被覆盖；passthrough-owned 被保留；schema mismatch 时 `schema_migrated_at` 来自注入时钟 |
| `cadgf_units_import_export.test.js` | 派生严格拒绝未知单位；导入未知单位不拒绝，回落 `mm` 并保留原始单位信息 |
| `cadgf_entity_vocab_mapping.test.js` | Project kind ↔ CADGF numeric type；已有 cadgfId 保留；新建 numeric id 稳定分配 |
| `cadgf_import_loss_diagnostics.test.js` | CADGF 导入产生降级 diagnostics，constraints/features 不伪造 |
| `runtime_web_bridge.test.js` | 在确认 Web 导出方向存在后，验证 Web CADGF snapshot → Project → CADGF snapshot 基础可视实体稳定，unsupported passthrough 不丢 |

### Schema 校验（独立验收步骤，已实现 S6）

```bash
bash apps/runtime/tools/run_schema_acceptance.sh
```

- `emit_cadgf_fixtures.mjs`（Node）从代表性 project 派生 CADGF 到临时目录，时间戳由固定时钟产生，保证可复现（rich / edge-malformed / round-trip 三份）。
- `validate_cadgf_document.py` 用 `deps/cadgamefusion/schemas/document.schema.json` + Python `jsonschema` 校验。
- **不进 `node --test`**；Python 依赖缺失只让本步失败（退出码 3 + 安装提示），不污染纯 Node runtime 测试。

## Assumptions

- `apps/runtime` 是绿地实现，无迁移风险（当前仅 5 个 README 占位文件）。
- CADGF 目标 schema 是当前 `deps/cadgamefusion/schemas/document.schema.json`。
- v0 的无损路径只有 Project save/load；CADGF 往返只保证场景可恢复和 passthrough 尽力保真。
- 2–4 周估算包含：schema 独立校验、字段归属表、黄金样本、稳定 id 分配、passthrough 过滤、宽松导入单位、可注入固定时钟与 diagnostics。

## 建议起手顺序

1. **`apps/runtime/scene` 唯一实体映射表 + `deriveCadgfDocument` 骨架**——含 deriver-owned 三字段规则、project/passthrough 合成、可注入 `clock`，先让 `point/line/polyline/circle/arc/text` 跑通、其余进 passthrough。
2. **`validate_cadgf_document.py` 轻量独立校验脚本 + Node 侧 fixture 生成**——打通 schema 验收这条独立步骤。
3. **黄金序列化测试脚手架**——固定输入 + 提交黄金文件。

## 实施清单 / Checklist

> 规则：**完成判据 = 对应测试通过**，不是主观勾选。顺序含依赖；`(起手N)` 标注对应上节"建议起手顺序"。S1 是其余阶段的隐式地基。

### P0 — 动工前预检 ✅ 2026-05-25

- [x] 核实现有 Web 导出方向：`deps/cadgamefusion/tools/web_viewer/adapters/cadgf_document_adapter.js` 已提供 `exportCadgfDocument(documentState)`（DocumentState → CADGF 数字快照）与 `importCadgfDocument`；`editor_import_adapter.js` 提供 `resolveEditorImportPayload`/`applyResolvedEditorImport` 加载路径。→ **S7 桥是薄适配**，无需新写 CADGF export adapter。

### S1 — `project` 模块（地基）✅ 2026-05-25

- [x] `createProjectModel` / `parseProjectModel` / `normalizeProjectModel` / `serializeProjectModel` / `migrateProjectModel`（`apps/runtime/project/index.js`）
- [x] 确定性：normalize/serialize 不碰 `createdAt/modifiedAt`；`layers/entities/constraints/features/passthrough.entities` 全部按 id 稳定序列化
- [x] 未知未来版本拒绝；v1 migration no-op
- [x] 结构校验（写边界）：错类型集合/对象 → `INVALID_PROJECT_FORMAT`（拒绝静默丢弃，P1）；Project-owned 集合要求 id 存在且唯一（消除重复/缺失 id 的排序歧义，P2）。缺失字段仍按默认补全；`parse` 保持 envelope-only，结构校验落在 `normalize`/`serialize`
- **完成判据**：`project_schema_roundtrip.test.js`、`project_deterministic_save.test.js` 通过（21 runtime 用例全绿，与既有 web 测试合跑 38/38）

### S2 — `constraint` / `feature` 桩 ✅ 2026-05-25

- [x] `constraint`（`apps/runtime/constraint/index.js`）：`normalizeConstraintSet()` — 校验 + 稳定排序 + 诊断容器（恒空，v0 不求解）
- [x] `feature`（`apps/runtime/feature/index.js`）：`normalizeFeatureList()` + `buildRebuildPlan()`（确定性 no-op：稳定 id 序、`steps:[]`、`noop:true`）
- [x] 抽出 `apps/runtime/shared/ordering.js`：单一权威排序/去重规则（`compareIds` 相等性 ⟺ 去重键），constraint/feature/project 三者共用，消除重复（P2 教训落到架构层）
- **完成判据**：原计划无独立测试（由 S3 间接覆盖），实际加了 `runtime_constraint_feature.test.js` 烟雾测试（7 用例）；project 并入共享工具后全套 45/45 无回归

### S3 — 黄金序列化（起手3）✅ 2026-05-25

- [x] 提交固定输入的黄金 Project 文件 `apps/runtime/tests/fixtures/project_golden_v1.json`（覆盖 layers/entities/constraints/features/passthrough/meta）
- [x] `project_golden_serialization.test.js`（3 用例）：黄金字节相等；黄金自身 parse→serialize 往返一致；乱序等价输入仍产出同一黄金。带 `UPDATE_GOLDEN=1` 逃生舱用于有意改格式后再生成
- **完成判据**：`project_golden_serialization.test.js` 通过（全套 49/49）

### S4 — `scene.deriveCadgfDocument`（起手1）✅ 2026-05-25

- [x] 唯一实体映射表（kind ↔ numeric type，`apps/runtime/scene/index.js`）：`point=1/line=2/polyline=0/arc=3/circle=4/text=7` 建模翻译，其余经 passthrough 原样 emit；几何按 CADGF 形状透传，信封字段（id→numeric、kind→type、layerId→layer_id、补 name）翻译
- [x] deriver-owned 三字段：`cadgf_version`/`schema_version` 写目标；`schema_migrated_at` **三态**（无源→省略 / 源==目标→保留 / 源≠目标→`clock.now()`+diagnostic）
- [x] project-owned / passthrough-owned 合成（passthrough 读**嵌套** `document.metadata.*`）；新建时间戳取 `project.*`，**可注入 `clock`，禁 `Date.now()`**
- [x] 派生单位严格枚举（`mm/cm/m/in/ft` → unit_name+unit_scale；未知 → `ok:false UNSUPPORTED_PROJECT_UNIT`）
- [x] passthrough.document key 过滤：derive 只读 schema-known 字段并合成，未知 root key 不吐回（留在 Project 文件）
- [x] passthrough 实体也校验 CADGF 四必填（id/type/layer_id/name）→ 不合格 diagnostic+跳过；id 分配（cadgfId 优先、最小未用非负整数、冲突 diagnostic+重分配）；entities/layers 按 id 排序
- **完成判据**：`cadgf_document_meta_ownership.test.js`(8) + `cadgf_units_import_export.test.js`(派生半,2) + `cadgf_derive_entities.test.js`(6) 通过（全套 65/65）

### S5 — `scene.importProjectFromCadgfDocument`（降级导入）✅ 2026-05-25

- [x] 反向映射复用同一套规则：`TYPE_TO_KIND` 由 `KIND_TO_TYPE` 反推、同一 `UNITS` 表反查；清洗只在 derive 出口做（import 只结构映射，畸形由 re-derive 兜底——不开第二套规则）
- [x] 实体：supported type → 建模（数字 id → `e<id>`，**保留 `cadgfId`**，每个导入实体都带源 id）；`ellipse/spline/block/unknown` → `cadgfPassthrough.entities` 原样保留 + diagnostic
- [x] 导入单位宽松降级（`unit_name` 大小写无关归一化 → `unit_scale` 近似 → 回落 `mm` + `UNIT_FALLBACK` diagnostic；原始值随源 metadata/settings 完整存入 passthrough）
- [x] 源文档级字段（`document_id/schema_migrated_at/cadgf_version/schema_version/feature_flags/metadata/settings`）**完整落** `cadgfPassthrough.document`，供 derive 按归属取回
- [x] 降级 diagnostics：`DEGRADED_IMPORT`（CADGF 不携带 constraints/features，恒 `[]` 不伪造）；`document_id` 缺失回落稳定默认 id
- **完成判据**：`cadgf_import_loss_diagnostics.test.js`(5) + `cadgf_units_import_export.test.js`(导入半,3) + `cadgf_entity_vocab_mapping.test.js`(4) 通过（全套 91/91）。端到端验证：`derive→import→derive` 实体字节一致，再 derive 输出通过真实 `document.schema.json` 校验

### S6 — schema 独立校验（起手2，依赖 S4）✅ 2026-05-25

- [x] `apps/runtime/tools/validate_cadgf_document.py`：按真实 `document.schema.json` 校验给定 JSON；缺 `jsonschema` → 退出码 3 + 明确安装提示
- [x] `apps/runtime/tools/emit_cadgf_fixtures.mjs`：从代表性 project 派生 CADGF（rich / edge-malformed / round-trip 三份），固定时钟、写临时目录
- [x] `apps/runtime/tools/run_schema_acceptance.sh`：node 生成 → python 校验；**不进 `node --test`**，Python 缺失只让本步失败
- **完成判据**：三份派生文档（含全 6 实体、passthrough、被清洗的畸形 edge、derive→import→derive 往返）全部通过 `deps/cadgamefusion/schemas/document.schema.json` 校验；`node --test` 仍为纯 Node 且全绿

### S7 — Web bridge（依赖 P0 结论、S4、S5）✅ 2026-05-25

- [x] `apps/web/shared/runtime_bridge.js`：`exportRuntimeProjectFromDocumentState`（`exportCadgfDocument` → `importProjectFromCadgfDocument`）与 `importRuntimeProjectToDocumentState`（`deriveCadgfDocument` → `resolveEditorImportPayload`/`applyResolvedEditorImport`）。**纯组合现有 adapter，全程走 CADGF**，Runtime 不耦合编辑器内部实体形状
- [x] 确定性：`exportCadgfDocument` 注入 wall-clock 两处（metadata 时间戳 + `web-${Date.now()}` document_id）；注入 `clock` 时桥把两者都钉死（document_id 取 `options.documentId` 或固定默认），无 clock 则继承 wall-clock（已注明非确定）
- [x] 单一契约：编辑器 import adapter 对坏输入会 throw → 桥 try/catch 转 `BRIDGE_LOAD_FAILED`，不破坏 `{ok,...}` 契约
- **完成判据**：`runtime_web_bridge.test.js`(6) 通过；端到端 `DocumentState → Project → DocumentState` 往返实体数/图层数/类型/**几何**（line 端点 `[0,0]→[10,0]`）一致；注入 clock 时跨 8ms 间隔字节一致；非法入参与 derive 失败均正确返回

### 全绿验收 ✅ 2026-05-25

- [x] `node --test apps/runtime/tests/*.test.js apps/web/tests/*.test.js` 全绿（85/85，基于 `origin/main` 干净基线）
- [x] schema 独立校验步骤通过（`bash apps/runtime/tools/run_schema_acceptance.sh` → PASS）

---

## 附录 A：CADGF 字段归属对 schema 的完整性核对

冻结归属表前，对 `document.schema.json` 的 required 字段逐项核对，确认三类归属**无字段双归、无悬空**——否则派生会过不了 `additionalProperties: false` 的校验。

**顶层 required**：`cadgf_version`(deriver) · `schema_version`(deriver) · `feature_flags`(passthrough) · `metadata`(合成) · `settings`(合成) · `layers`(project entities) · `entities`(project entities) → 全覆盖。

**`metadata` 8 项 required**：`label`(project) · `author`(pass) · `company`(pass) · `comment`(pass) · `created_at`(pass) · `modified_at`(pass) · `unit_name`(project) · `meta`(pass) → 8 个无漏无重。

**`settings.unit_scale`**(project) · **`document_id`**（可选, project） · **`schema_migrated_at`**（可选, deriver 条件） → 齐。

结论：三类划分干净，完整覆盖 schema required 字段，无双归无悬空。

## 附录 B：评审收口记录

本规格经多轮评审收口，已锁定的关键修正：

1. schema 校验**拆出** `node --test`，做成独立 Python 步骤（贴合现有 `validate_*.py` 模式，保持 Node 测试自洽）。
2. CADGF 文档级字段引入 `resources.cadgfPassthrough.document` 落点，避免派生丢失。
3. 实体三套词汇（Project kind / CADGF numeric type / Web）收敛为**唯一权威映射表**。
4. 确定性契约**显式排除时间戳**，并补回"所有集合按 id 稳定排序"。
5. CADGF 导入**改名 + 明确降级**（`importProjectFromCadgfDocument`，非反向 derive）。
6. `cadgf_version/schema_version/schema_migrated_at` 从 passthrough-owned **改判 deriver-owned**（版本字段描述"派生器产出什么"，不由导入源决定；否则不匹配路径会产出"自我描述撒谎"的文档）。
7. 单位**导入宽松降级、派生严格枚举**分开定义。
8. 提交**黄金样本**防格式漂移；默认时间戳走**可注入固定时钟**。
