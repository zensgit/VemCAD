# Preview Runtime Contracts

这个目录承接 preview runtime 在迁移期需要维持的入口 contract 说明。

## 当前稳定入口

- `window.__vemcadApp.switchToEditor(documentJson)`
  - preview / desktop renderer 切回 editor 的稳定桥接路径。
- `?manifest=`、`?gltf=`、`?mode=editor`
  - preview runtime 的兼容入口参数，拆分时不应改变现有消费路径。
- document fallback
  - preview 无法直接消费 artifact 时的兼容 fallback 路径，应与入口参数一起视为同一级 contract。

## 边界

- 这里记录 preview runtime 的入口和 handoff contract，不承接 workbench 命令或 editor 状态机。
- editor 侧兼容面说明见 [../../../workbench/contracts/README.md](../../../workbench/contracts/README.md)。

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/preview_app.js`
- `deps/cadgamefusion/tools/web_viewer/app.js`

## 当前导出入口

- `index.js`
  - 产品层聚合 preview runtime contract 常量、legacy bootstrap facade 和 editor handoff helper。
