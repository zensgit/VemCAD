# Preview Runtime

这个目录承接 preview 运行时的产品层 facade 和后续拆分模块。

当前已经落下的迁移入口包括：

- `preview_bootstrap.js`
  - 兼容导入当前 `deps/cadgamefusion/tools/web_viewer/preview_app.js`。
- `editor_handoff.js`
  - 统一 preview -> editor 的 `window.__vemcadApp.switchToEditor()` 桥接调用。
- `contracts/`
  - 记录迁移期必须保持稳定的入口 contract，并提供产品层导出入口。

后续真正迁移 preview runtime 时，应优先把 manifest/document/gltf 加载、overlay、desktop bridge 等逻辑逐步从 legacy 入口迁到这里，而不是继续扩张 `preview_app.js`。
