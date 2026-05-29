# Workbench Source Groups

这个目录承接 imported source-group 工作流和对应语义模块。

## 适合放在这里的内容

- source-group 识别、聚合、release/select/fit 相关规则
- grouped source provenance、anchor、text placement 语义
- source-group 专属的展示辅助和领域 helper

## 不应继续堆在这里的内容

- 通用 bootstrap 和 panel wiring
- insert-group 专属规则
- preview document fallback 或 artifact loading

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`

source-group 应作为独立领域落地，避免继续和 insert-group、panel 逻辑纠缠在同一个入口文件里。
