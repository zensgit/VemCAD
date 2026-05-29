# VemCAD 验证计划

## 文档目的

把 VemCAD 后续演进的验证方式从“模块各自有测试”收敛成“按产品流验证”。重点不是穷举所有测试，而是明确每一层该证明什么。

## VERIFICATION 通过的定义（gate, not run-log）

> 加于 2026-05-29：一次方案体检发现"VERIFICATION"在实践中漂移成了"本地跑了命令、贴了日志"——曾有阶段
> 带着 smoke 超时 + 校验失败仍被判为"已验证/完成"。为此钉死"通过"的含义：

一个阶段/特性算 **已验证**，必须同时满足：

- **针对具名验收标准给出显式 pass/fail**，不是粘贴 run-log。任一项 failing/partial → 阶段保持 OPEN，
  挂可追踪缺陷，不得标完成。
- **从可移植入口运行**：`npm test`（root `package.json`）或 CI workflow；禁止硬编码绝对路径（如
  `/Users/...`）、禁止临时 symlink 等单机手跑特征。run-log 归档到构建产物，文档只留"标准 + 判定"。
- **产品代码须落在 main 且有 CI 可见**：见 `.github/workflows/product_tests.yml`（core = 无子模块、
  PAT-free；web-integration = 子模块 + PAT）。注意 VemCAD 为 free-tier、无分支保护，CI 是**可见性、非强制门禁**。

当前缺口：下方 Level 1/2/3 矩阵对**产品代码**（apps/**, services/**）尚未在 CI 落地；`product_tests.yml`
是第一步，其余（`router_contract_smoke`、`project_schema_roundtrip` 等）仍待补。

## 验证原则

### 1. 先验证边界，再验证功能

优先证明：

- 官方工程模型是否唯一。
- `Project -> Document -> Router Artifacts` 是否可预测。
- 本地桌面与远端服务是否共享同一契约。

### 2. 以产品流组织验证

验证主路径应围绕：

1. 导入
2. 派生场景
3. 编辑
4. 转换/预览
5. 桌面打开
6. 回归比较

### 3. 现有能力优先复用

当前仓库已经有较丰富的测试资产，应优先复用：

- CTest / C++ core tests
- DXF/DWG tools tests
- Qt tests
- Web viewer unit tests
- Web/Electron smoke scripts

## 当前可复用的验证资产

### Core / ABI / solver

- `deps/cadgamefusion/tests/core/*`
- `deps/cadgamefusion/tests/package_consumer/*`
- `deps/cadgamefusion/CMakeLists.txt`

已覆盖：

- `Document`
- layers / metadata / notifications
- solver baseline / conflicts / constraints
- mesh export
- C API 查询与 package consumer smoke

### Import / convert / router artifacts

- `deps/cadgamefusion/tests/tools/*`
- `deps/cadgamefusion/tests/plugin_data/*`
- `deps/cadgamefusion/CMakeLists.txt` 中的 `convert_cli_*` / `editor_assembly_*` / `solve_from_project_json_smoke`

已覆盖：

- DXF importer
- DWG importer plugin
- hatch / table / leader / mleader / insert attributes
- roundtrip
- metadata normalization
- convert_cli artifact smoke

### Qt fidelity / inspector

- `deps/cadgamefusion/tests/qt/*`

已覆盖：

- canvas
- property/layer/snap panels
- project roundtrip
- guide / gizmo / viewport

### Web / Electron workbench

- `deps/cadgamefusion/tools/web_viewer/tests/*`
- `deps/cadgamefusion/tools/web_viewer/scripts/*`
- `deps/cadgamefusion/tools/web_viewer_desktop/tests/*`

已覆盖：

- property panel
- selection helpers
- import normalization
- source group / insert group
- desktop settings / packaged desktop smoke
- editor roundtrip / ui flow / layer/session / selection summary

## 目标验证矩阵

## 1. Project Runtime 验证

### 要证明的事情

- 官方工程文件是唯一真相来源。
- save/load deterministic。
- migration 可重复。
- `Project -> Document` 派生稳定。

### 建议新增验证

- `project_schema_roundtrip`
- `project_migration_forward_only`
- `project_deterministic_save`
- `project_to_document_derivation`
- `project_solver_binding_contract`

### 失败信号

- 同一工程多次保存产生非稳定 diff
- 派生场景缺失实体/约束结果
- 前端状态和工程文件真相不一致

## 2. Scene / Document 验证

### 要证明的事情

- `CADGF Document` 仍可作为统一场景格式被 Web / Qt / Router 消费。
- import provenance / style / layout / metadata 不回退。

### 复用现有验证

- `convert_cli_smoke`
- `convert_cli_dxf_style_smoke`
- `convert_cli_mesh_metadata_smoke`
- `editor_assembly_roundtrip_*`
- `tests/tools/test_dxf_*`

### 建议新增门禁

- `project_derived_document_contract_smoke`
- `document_schema_contract_smoke`

## 3. Web Workbench 验证

### 要证明的事情

- Workbench 仍是唯一主编辑工作台。
- 大模块拆分后行为不回退。
- 命令、选择、图层、属性、source-group、insert-group 语义保持一致。

### 必跑项

- `deps/cadgamefusion/tools/web_viewer/tests/*`
- `editor_ui_smoke.sh`
- `editor_ui_flow_smoke.sh`
- `editor_roundtrip_smoke.js`
- `editor_current_layer_smoke.js`
- `editor_selection_summary_smoke.js`
- `editor_source_group_smoke.js`
- `editor_insert_group_smoke.js`
- `editor_insert_attribute_smoke.js`

### 拆分期额外要求

- 每次把命令从 `command_registry.js` 迁出时，必须补一层模块级单测。
- 每次把 UI wiring 从 `workspace.js` 迁出时，必须补一层 smoke 或 contract test。

### 拆分期专项验证策略

#### Command Registry 迁移门禁

- 迁移时把“命令 id、`canExecute` 语义、`commandResult` 结构、undo/redo 行为”视为固定 contract。
- `registerCadCommands()`、`computeRotatePayload()`、`computeScalePayload()` 在迁移期视为兼容导出，不因拆文件而直接消失。
- Phase 1 至少应覆盖：
  - `deps/cadgamefusion/tools/web_viewer/tests/editor_commands.test.js`
  - `deps/cadgamefusion/tools/web_viewer/tests/selection_contract.test.js`
  - `editor_roundtrip_smoke.js`
  - `editor_source_group_smoke.js`
  - `editor_insert_group_smoke.js`
  - `editor_insert_attribute_smoke.js`

#### Workspace Wiring 迁移门禁

- `bootstrapCadWorkspace()` 返回的 `{ destroy, state, commands, importPayload }` 视为稳定对外接口。
- `window.__cadDebug` 视为 smoke contract，拆分时不能回退核心调试入口。
- Phase 2 至少应覆盖：
  - `editor_ui_smoke.sh`
  - `editor_ui_flow_smoke.sh`
  - `editor_current_layer_smoke.js`
  - `editor_layer_session_smoke.js`
  - `editor_space_layout_smoke.js`
  - `editor_selection_summary_smoke.js`
  - `solver_action_panel_smoke.js`

#### Preview / Desktop 分流门禁

- `preview_app.js` 拆分时，把 `?manifest=`、`?gltf=`、document fallback、desktop open handoff 视为同一级 contract。
- `window.__vemcadApp.switchToEditor(documentJson)` 必须继续作为 preview -> editor 的稳定桥接路径。
- Phase 3 至少应覆盖：
  - `deps/cadgamefusion/tools/web_viewer/tests/document_preview_fallback.test.js`
  - `deps/cadgamefusion/tools/web_viewer/tests/desktop_settings.test.js`
  - `preview_provenance_smoke.js`
  - `desktop_live_settings_smoke.js`
  - `desktop_packaged_settings_smoke.js`
  - `desktop_packaged_document_fallback_smoke.js`
  - `desktop_packaged_open_handoff_smoke.js`
  - `desktop_packaged_drop_recent_smoke.js`
  - `desktop_packaged_resume_batch_recovery_smoke.js`
  - `desktop_packaged_assoc_multidrop_smoke.js`

#### 阶段性放行规则

- Phase 1 不通过，不进入 `workspace.js` 大规模 wiring 拆分。
- Phase 2 不通过，不进入 `preview_app.js` 的 desktop bridge 分流。
- Phase 3 不通过，不做 `apps/web/*` 目录提升或旧 facade 清理。

## 4. Desktop Shell 验证

### 要证明的事情

- 桌面壳仍然只是壳。
- 本地打包、运行时探测、Router 自启动、Open CAD File 不回退。

### 必跑项

- `desktop_live_settings_smoke.js`
- `desktop_packaged_settings_smoke.js`
- `desktop_packaged_open_handoff_smoke.js`
- `desktop_packaged_drop_recent_smoke.js`
- `desktop_packaged_assoc_multidrop_smoke.js`

### 建议新增门禁

- `desktop_router_contract_smoke`
- `desktop_runtime_detection_contract_smoke`

## 5. Router Service 验证

### 要证明的事情

- 本地桌面与远端服务使用同一 HTTP contract。
- convert / status / manifest / history 行为稳定。
- allowlist / auth / payload limits 不破坏桌面路径。

### 可复用入口

- `deps/cadgamefusion/tools/plm_router_service.py`
- `deps/cadgamefusion/tools/plm_smoke.sh`
- `deps/cadgamefusion/tools/plm_error_codes_smoke.sh`
- Electron `--smoke-dwg` 路径

### 建议新增验证

- `router_contract_smoke`
- `router_manifest_contract_smoke`
- `router_local_remote_parity_smoke`
- `router_auth_and_allowlist_smoke`

## 6. Qt Inspector 验证

### 要证明的事情

- Qt 继续承担 fidelity / regression 角色。
- 导入和渲染对照能力不回退。

### 必跑项

- `tests/qt/*`
- `tools/editor_gate.sh`
- `tools/local_ci.sh`

### 不建议新增的门禁方向

- 不再以 Qt 作为官方工程编辑主线做新功能门禁。

## 分层门禁建议

## Level 1: 提交前快速门禁

适用于日常开发：

- core 相关单测子集
- `convert_cli_smoke`
- Web 单测子集
- 一个 editor smoke

## Level 2: 合并前主线门禁

适用于 PR / merge：

- CTest core + tools 关键子集
- `editor_roundtrip_smoke.js`
- `editor_ui_flow_smoke.sh`
- `desktop_live_settings_smoke.js`
- `plm_error_codes_smoke.sh`

## Level 3: 夜间/版本门禁

适用于 release / nightly：

- `tools/local_ci.sh --strict`
- `tools/editor_gate.sh`
- 全量 DXF/DWG fixture matrix
- packaged desktop smokes
- local/remote router parity

## 验证产物要求

每类验证都应输出结构化结果，而不是只看终端日志。

### 建议统一保留

- summary json
- manifest json
- screenshots / baseline compare
- failing fixture path
- failure_code / failure_detail

### 原因

- 现有仓库已经在 desktop smoke、editor gate、router history 上大量使用结构化摘要，后续应统一延续。

## 本阶段建议直接执行的验证工作

1. 把验证描述从“模块自己的测试”升级为“产品流矩阵”。
2. 为 `Project Runtime` 预留独立验证组，而不是继续塞回 Web/solver bridge 测试里。
3. 为 Router 固定 contract smoke，保证本地桌面与远端服务行为一致。
4. 将 Web 大文件拆分与 smoke/contract test 绑定推进，避免重构期间失守。
5. 将 Qt 的验证目标锁定在 fidelity / regression，而不是产品主流程。
