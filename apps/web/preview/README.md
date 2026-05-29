# VemCAD Web Preview

这个目录用于承接只读预览入口与产物消费逻辑。

当前可运行实现仍主要位于 `deps/cadgamefusion/tools/web_viewer/preview_app.js`，后续应按 [docs/VEMCAD_WORKBENCH_SPLIT_PLAN.md](../../../docs/VEMCAD_WORKBENCH_SPLIT_PLAN.md) 中的 preview 分流方案逐步迁入本目录。

## 目标

- manifest / document / glTF 加载入口
- preview-only overlays 与 framing
- provenance 展示
- preview 到 editor 的稳定桥接
- desktop preview 壳层消费入口

## 约束

- 不在这里承接 workbench 专属命令与编辑状态机。
- preview 与 desktop bridge 的共享能力应在本目录内稳定，而不是继续堆回单一入口文件。

## 入口文档

- [Preview Runtime Contracts](./runtime/contracts/README.md)

## 当前 facade 入口

- `./runtime/preview_bootstrap.js`
- `./runtime/editor_handoff.js`
- `./runtime/contracts/index.js`
