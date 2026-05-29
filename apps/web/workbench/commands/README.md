# Workbench Commands

这个目录承接 editor 命令域模块，目标是把 `command_registry.js` 收敛为薄注册 facade。

## 适合放在这里的内容

- 命令 handler、命令注册表、共享命令 helper
- 兼容导出 `registerCadCommands()`
- 工具仍在依赖的 payload helper，例如旋转和缩放 payload 计算

## 不应继续堆在这里的内容

- workspace bootstrap 和 DOM wiring
- panel orchestration
- preview runtime 或 desktop handoff

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/commands/command_registry.js`
- `deps/cadgamefusion/tools/web_viewer/tools/rotate_tool.js`
- `deps/cadgamefusion/tools/web_viewer/tools/scale_tool.js`

## 当前 facade

- `registry.js`
  - 暂时转发 `registerCadCommands()`、`computeRotatePayload()`、`computeScalePayload()`。

兼容面说明见 [../contracts/README.md](../contracts/README.md)。
