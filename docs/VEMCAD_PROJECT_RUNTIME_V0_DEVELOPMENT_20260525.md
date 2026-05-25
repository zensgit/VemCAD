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

### Schema 校验（独立验收步骤）

- Node 测试或 fixture 脚本生成 CADGF fixture 到临时目录，fixture 时间戳由固定时钟产生，保证可复现。
- 独立命令使用 CADGameFusion 现有 Python 校验模式，或新增轻量 `validate_cadgf_document.py`，校验 `deps/cadgamefusion/schemas/document.schema.json`。
- **Python 依赖缺失只影响 schema 验收步骤，不污染纯 Node runtime 测试。**

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

### P0 — 动工前预检

- [ ] 核实现有 Web 是否已有 `DocumentState → CADGF 数字快照` 导出方向（决定 S7 工作量；见 §6）。

### S1 — `project` 模块（地基）

- [ ] `createProjectModel` / `parseProjectModel` / `normalizeProjectModel` / `serializeProjectModel` / `migrateProjectModel`
- [ ] 确定性：normalize/serialize 不碰 `createdAt/modifiedAt`；`layers/entities/constraints/features/passthrough.entities` 全部按 id 稳定序列化
- [ ] 未知未来版本拒绝；v1 migration no-op
- **完成判据**：`project_schema_roundtrip.test.js`、`project_deterministic_save.test.js` 通过

### S2 — `constraint` / `feature` 桩

- [ ] `constraint`：normalize + 诊断容器，不求解
- [ ] `feature`：保存列表 + no-op rebuild plan
- *（无独立测试；服务于序列化确定性，由 S3 黄金样本间接覆盖——故须早于 S3）*

### S3 — 黄金序列化（起手3）

- [ ] 提交固定输入的黄金 Project 文件（含 `constraints/features`，依赖 S2）
- **完成判据**：`project_golden_serialization.test.js` 通过

### S4 — `scene.deriveCadgfDocument`（起手1）

- [ ] 唯一实体映射表（kind ↔ numeric type）：`point/line/polyline/circle/arc/text` 跑通，其余进 passthrough
- [ ] deriver-owned 三字段：`cadgf_version`/`schema_version` 写目标版本；`schema_migrated_at` 条件（源≠目标→注入时钟）
- [ ] project-owned / passthrough-owned 合成；**可注入 `clock`，禁 `Date.now()`**
- [ ] 派生单位严格枚举（`mm/cm/m/in/ft`；未知 → `ok:false`）
- [ ] `passthrough.document` 输出按目标 schema 过滤 key
- **完成判据**：`cadgf_document_meta_ownership.test.js`、`cadgf_units_import_export.test.js`（派生半）通过

### S5 — `scene.importProjectFromCadgfDocument`（降级导入）

- [ ] 实体反向映射；unsupported → passthrough 不丢
- [ ] 导入单位宽松降级（`unit_name` 归一化 → `unit_scale` 近似 → 回落 `mm` + diagnostic + 存原始）
- [ ] 已有 `cadgfId` 保留、新建稳定分配、冲突报 diagnostic
- [ ] 降级 diagnostics：`constraints/features` 不伪造；`document_id` 从无变有
- **完成判据**：`cadgf_import_loss_diagnostics.test.js`、`cadgf_units_import_export.test.js`（导入半）、`cadgf_entity_vocab_mapping.test.js` 通过

### S6 — schema 独立校验（起手2，依赖 S4）

- [ ] `validate_cadgf_document.py`（或复用现有 Python 校验模式）
- [ ] Node/fixture 脚本生成 CADGF fixture 到临时目录，时间戳走固定时钟
- [ ] Python 依赖缺失只影响本步，不污染 `node --test`
- **完成判据**：派生 CADGF Document 通过 `deps/cadgamefusion/schemas/document.schema.json` 校验

### S7 — Web bridge（依赖 P0 结论、S4、S5）

- [ ] `exportRuntimeProjectFromDocumentState` / `importRuntimeProjectToDocumentState` 薄桥，走 CADGF 语义
- **完成判据**：`runtime_web_bridge.test.js` 通过

### 全绿验收

- [ ] `node --test apps/runtime/tests/*.test.js apps/web/tests/*.test.js` 全绿
- [ ] schema 独立校验步骤通过

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
