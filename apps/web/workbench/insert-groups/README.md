# Workbench Insert Groups

这个目录承接 imported insert-group 工作流和实例级语义模块。

## 适合放在这里的内容

- insert-group 识别、聚合、release/select/fit 相关规则
- imported `INSERT` 属性代理、peer instance、peer target 语义
- insert-group 专属 helper 和兼容行为封装

## 不应继续堆在这里的内容

- source-group 专属规则
- panel DOM 细节
- preview / desktop handoff

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
- `deps/cadgamefusion/tools/web_viewer/commands/insert_group.js`
- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`

insert-group 模块应保持实例语义集中，避免再次散落回命令注册和 UI 壳层。
