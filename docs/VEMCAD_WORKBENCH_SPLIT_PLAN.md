# VemCAD Web Workbench 拆分计划

> **治理标注（2026-05-29）** — (事实) 本计划 Phase 1–3 在 `deps/cadgamefusion/tools/web_viewer/`
> **子模块内**执行，每步走 A→C 发布纪律（CADGameFusion PR + VemCAD 指针 bump）；`apps/web` 当前的
> facade 是 Phase 0 边界标记（纯转发、无隔离），不等于拆分已开始。(事实) `VEMCAD_POST_V0_DIRECTION_EVALUATION`
> 冻结了"拆分应由 solver 集成需求**驱动**，而非投机式全量按序拆"。(建议·待 owner 拍板) 据此把本计划的固定
> 全文件顺序视为**排序待修订**：先按需求抽（如 solver/bridge），**推迟 fillet/chamfer 与 break/join** 等
> 几何密集块。详见 [`VEMCAD_PLAN_PROGRESS_STATUS_20260528.md`](./VEMCAD_PLAN_PROGRESS_STATUS_20260528.md)。

## 文档目标

把 Web workbench 的拆分从“知道要拆”推进到“知道先拆什么、拆到哪一层、每一阶段如何收口”。

本计划只覆盖 3 个当前的上帝文件：

- `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`
- `deps/cadgamefusion/tools/web_viewer/preview_app.js`

同时给出 VemCAD 产品层的目标目录，确保后续模块最终能回到 `apps/web/*`，而不是继续停留在平台层目录里。

## 当前基线

本次研读对应的文件体量大致如下：

- `command_registry.js`: 5463 行
- `workspace.js`: 2909 行
- `preview_app.js`: 4422 行

现状并不是“完全没有模块化”，而是“已经拆出一批协作者，但主流程仍然集中在 3 个大文件里”。当前已经可复用的 seam 包括：

- `adapters/editor_import_adapter.js`
- `ui/layer_session_policy.js`
- `ui/selection_presenter.js`
- `document_preview_fallback.js`
- `desktop_settings.js`

后续拆分应延续这些 seam，不再回到“大文件里补一个 helper”。

## 三个文件分别要解决什么问题

| 文件 | 当前混合职责 | 拆分后保留职责 |
| --- | --- | --- |
| `command_registry.js` | 命令注册、undo/redo snapshot、选择/变换/修剪/倒角/圆角算法、source/insert group 语义、solver bridge、工具 payload helper | 只保留命令注册表、兼容导出和少量装配逻辑 |
| `workspace.js` | workbench bootstrap、DOM wiring、panel wiring、typed command 解析、debug hook、solver action 状态机、import/export、图层/空间/选择联动 | 只保留 bootstrap / composition / 稳定对外 API |
| `preview_app.js` | preview bootstrap、manifest/document/glTF 加载、text/line overlay、选择与 framing、document fallback、desktop settings/recent/batch/open handoff | 只保留 preview bootstrap 和稳定入口拼装 |

## 拆分原则

### 1. 先逻辑拆分，再物理迁移

当前运行时入口仍在 `deps/cadgamefusion/tools/web_viewer/`。为了降低风险，优先做逻辑拆分和兼容 facade，等模块边界稳定后再迁入 `apps/web/*`。

### 2. 先纯函数与契约，后 DOM wiring 与 desktop IO

优先迁出：

- 纯命令逻辑
- state transform
- manifest/document 解析
- shared helper

最后再迁：

- DOM 事件绑定
- panel 组装
- desktop bridge
- recent files / batch queue / diagnostics

### 3. 保持 4 个兼容面稳定

迁移期必须视为稳定契约的边界：

- `registerCadCommands(commandBus, context)`
- `computeRotatePayload()` / `computeScalePayload()`
- `bootstrapCadWorkspace()` 返回的 `{ destroy, state, commands, importPayload }`
- `window.__vemcadApp.switchToEditor(documentJson)`

另外，以下行为也应视为 smoke contract：

- `?debug=1` 的 `window.__cadDebug`
- `?manifest=` / `?gltf=` / `?mode=editor`
- preview 中的 document fallback 路径

### 4. 拆分按领域，不按文件段落

不建议把大文件机械拆成 `part1.js` / `part2.js`。目标应按产品语义落点：

- command domain
- panel domain
- selection domain
- source/insert group domain
- io / import-export domain
- preview runtime domain
- desktop bridge domain

## 目标目录

最终目标不是继续把产品逻辑放在 `deps/cadgamefusion/tools/web_viewer/`，而是收敛到如下产品层目录：

```text
apps/web/
├─ README.md
├─ workbench/
│  ├─ README.md
│  ├─ bootstrap/
│  ├─ commands/
│  │  ├─ shared/
│  │  ├─ entity/
│  │  ├─ selection/
│  │  ├─ groups/
│  │  └─ solver/
│  ├─ panels/
│  ├─ selection/
│  ├─ source-groups/
│  ├─ insert-groups/
│  ├─ io/
│  └─ solver/
├─ preview/
│  ├─ runtime/
│  ├─ manifest/
│  ├─ overlays/
│  └─ desktop/
└─ shared/
```

说明：

- `apps/web/workbench/` 是编辑工作台的产品层目录。
- `apps/web/preview/` 是只读预览与桌面预览壳的产品层目录。
- `apps/web/shared/` 只承接 Web 内部共享逻辑，不反向吞掉 workbench / preview 的领域边界。

## Phase 0: 冻结边界，建立迁移前提

### 目标

在真正拆代码前，先把“不该再继续增长的大文件”标出来，并固定迁移使用的兼容面。

### 本阶段动作

- 明确 `command_registry.js` / `workspace.js` / `preview_app.js` 只接受 bugfix 和 seam 抽离，不再作为新功能默认落点。
- 固定 `registerCadCommands`、`bootstrapCadWorkspace`、`switchToEditor` 为迁移期兼容面。
- 在 `apps/web/` 建立产品层 README 与 workbench 落点说明。

### 收口条件

- 团队对目标目录和兼容边界有统一认知。
- 后续拆分 PR 可以明确声明属于 Phase 1 / 2 / 3 中的哪一步。

## Phase 1: 拆 `command_registry.js`

### 目标

先把命令系统从“大文件承载所有编辑语义”收敛成“薄注册层 + 领域命令模块”。

这是第一优先级，因为：

- `workspace.js` 直接依赖命令表。
- 多个工具和 smoke 已经依赖 `registerCadCommands` 及 payload helper。
- 如果命令边界不先稳定，后续 workspace 拆分只能继续把 wiring 和业务逻辑绑在一起。

### 目标模块

- `apps/web/workbench/commands/shared/snapshot.js`
  - `nowMs`
  - `emitPerfProfile`
  - `captureState`
  - `restoreState`
  - `withSnapshot`
- `apps/web/workbench/commands/shared/selection.js`
  - `hasSelection`
  - `selectedEntities`
  - read-only / whole-group transform helper
- `apps/web/workbench/commands/entity/create.js`
- `apps/web/workbench/commands/selection/transform.js`
  - move / copy / rotate / scale / offset
- `apps/web/workbench/commands/selection/trim_extend.js`
- `apps/web/workbench/commands/selection/break_join.js`
- `apps/web/workbench/commands/selection/fillet_chamfer.js`
- `apps/web/workbench/commands/selection/property_patch.js`
- `apps/web/workbench/commands/groups/source_group.js`
- `apps/web/workbench/commands/groups/insert_group.js`
- `apps/web/workbench/commands/solver/bridge.js`
- `apps/web/workbench/commands/registry.js`

### 迁移顺序

1. 先迁纯 helper 和 snapshot/history wrapper。
2. 再迁 `entity.create`、`selection.propertyPatch`、solver bridge 这类低 UI 耦合命令。
3. 再迁 source/insert group 相关命令，因为它们已经依赖 `insert_group.js` 这类较成熟协作者。
4. 然后迁 move/copy/rotate/scale/offset。
5. 最后迁 break/join/trim/extend/fillet/chamfer 这类几何密集命令。
6. 收尾时把 `command_registry.js` 压缩成薄 facade，只负责导入模块并注册。

### 兼容要求

- 命令 id 不变。
- `commandResult` 语义不变。
- undo/redo 和 snapshot 粒度不变。
- `computeRotatePayload()` / `computeScalePayload()` 继续保留兼容导出，直到现有工具完成切换。

### 本阶段完成标志

- `command_registry.js` 不再承载大块几何算法。
- 新命令默认只落到领域模块，不再回到 registry 文件。

## Phase 2: 拆 `workspace.js`

### 目标

把 `workspace.js` 收敛成真正的 bootstrap / composition 层，不再同时承担状态机、面板协作、键盘策略、导入导出和 debug API。

### 目标模块

- `apps/web/workbench/bootstrap/workspace_bootstrap.js`
  - `bootstrapCadWorkspace()` 的壳层
- `apps/web/workbench/bootstrap/keyboard_shortcuts.js`
  - undo/redo
  - solver flow shortcut
  - grid/snap/ortho toggle
- `apps/web/workbench/bootstrap/debug_hooks.js`
  - `window.__cadDebug`
- `apps/web/workbench/io/import_export.js`
  - `createImporter`
  - `downloadJson`
  - `importPayload`
  - export/import wiring
- `apps/web/workbench/selection/view_fit.js`
  - `computeDocumentExtents`
  - `fitViewToExtents`
  - `fitViewToDocument`
- `apps/web/workbench/selection/source_text_focus.js`
  - `resolveSourceTextGuideForSelection`
- `apps/web/workbench/panels/workspace_panels.js`
  - toolbar / statusbar / layer / property / snap / solver panels 组装
- `apps/web/workbench/solver/solver_action_runtime.js`
  - solver action state
  - request/event state
  - flow banner / console sync

### 迁移顺序

1. 先迁纯 view-fit、typed command parse、JSON import/export 这类 utility。
2. 再迁 `importPayload()` 及相关 document/session 同步逻辑。
3. 再迁 debug hook 构建逻辑，保证 smoke 仍有稳定观测面。
4. 再迁 solver action runtime 与键盘快捷键。
5. 最后迁 panel wiring 和 workspace bootstrap。
6. 收尾时让 `workspace.js` 只保留状态初始化、协作者组装、对外 API 暴露。

### 兼容要求

- `bootstrapCadWorkspace()` 返回结构不变。
- `importPayload(payload, { fitView })` 继续是 editor/desktop bridge 的稳定入口。
- `window.__cadDebug` 的关键能力不回退：
  - 选择读取/设置
  - layer 读取/设置
  - command 执行
  - view / overlay 状态读取

### 本阶段完成标志

- `workspace.js` 里的领域逻辑主要变成调用外部模块。
- 新增 UI wiring 不再默认进 `workspace.js`。

## Phase 3: 拆 `preview_app.js`

### 目标

把 preview runtime、artifact loading、document fallback、desktop integration 分开，避免只读预览和桌面壳继续纠缠在同一个文件里。

### 为什么放在第三阶段

- preview/editor 之间目前通过 `app.js` 和 `window.__vemcadApp.switchToEditor()` 互相协作。
- 只有在 command/workspace 对外契约稳定后，preview 侧的 editor handoff 才能安全固化。
- `preview_app.js` 还包含最多的 desktop-specific 行为，回归面最大，不适合最先动。

### 目标模块

- `apps/web/preview/manifest/manifest_loader.js`
  - manifest 获取
  - artifact URL 解析
  - meta 提取
- `apps/web/preview/runtime/scene_loader.js`
  - glTF load
  - scene reset / frame / selection hit
- `apps/web/preview/overlays/text_overlay.js`
- `apps/web/preview/overlays/line_overlay.js`
- `apps/web/preview/runtime/document_fallback.js`
  - 基于 `document_preview_fallback.js` 的 fallback orchestration
- `apps/web/preview/desktop/settings_controller.js`
- `apps/web/preview/desktop/recent_files.js`
- `apps/web/preview/desktop/batch_queue.js`
- `apps/web/preview/desktop/open_bridge.js`
- `apps/web/preview/runtime/bootstrap.js`

### 迁移顺序

1. 先迁 manifest/document/meta 解析与 artifact loader。
2. 再迁 text/line overlay 相关状态和渲染协作者。
3. 再迁 scene selection / framing / fallback orchestration。
4. 最后迁 desktop settings、recent files、batch queue、drop/open handoff。
5. 收尾时把 `preview_app.js` 压缩成薄 bootstrap。

### 兼容要求

- `?manifest=`、`?gltf=`、`?mode=editor` 路径不变。
- desktop renderer 仍可通过 `window.__vemcadApp.switchToEditor(documentJson)` 把 preview 切到 editor。
- document fallback preview 保持现有触发条件和状态提示语义。

### 本阶段完成标志

- preview runtime 与 desktop integration 可以分别测试、分别迭代。
- `preview_app.js` 不再同时承载 preview UI 和 desktop 壳状态机。

## Phase 4: 从当前 runtime 路径提升到 `apps/web/*`

### 目标

当模块边界已经稳定，再把稳定模块从当前运行时目录提升到产品层目录。

### 建议做法

1. 先保持模块命名和导出形状稳定。
2. 为旧路径保留短期 facade，避免一次性改掉全部 import。
3. 按领域逐步切换 import，而不是大规模 rename。
4. 等 smoke 与单测都稳定后，再删旧 facade。

### 不建议的做法

- 不建议在 Phase 1 就直接对 3 个大文件做物理移动。
- 不建议把“逻辑拆分”和“构建系统切换”放进同一个 PR。

## 推荐的总迁移顺序

1. `command_registry.js`
   - 先稳定命令边界和 undo/redo 契约。
2. `workspace.js`
   - 再把 workbench 变成组合层。
3. `preview_app.js`
   - 最后做 preview / desktop / editor handoff 分流。
4. `apps/web/*` 物理提升
   - 在模块形状稳定后再切目录。

这个顺序的核心原因是：workspace 建在 command 之上，preview 又依赖 editor handoff，所以命令边界必须先稳定，preview 则应该最后处理。

## 迁移期间的约束

- 禁止继续把新产品逻辑直接堆进这 3 个文件。
- 禁止同一批改动同时重写命令系统、workspace wiring、desktop bridge。
- 拆分 PR 必须声明：
  - 本次迁移的领域
  - 兼容面是否变更
  - 对应验证项
- 任何时候都不让 `apps/web/` 继续停留在“只有一个空 README”的状态。
