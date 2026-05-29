# Workbench IO

这个目录承接 editor 专属的导入导出和 payload 归一化逻辑。

## 适合放在这里的内容

- import/export orchestration
- editor 侧 document payload、clipboard、文件桥接 helper
- 与 bootstrap 返回值 `importPayload` 相关的稳定数据装配

## 不应继续堆在这里的内容

- preview manifest / glTF runtime
- 通用 panel UI 细节
- 与命令域无关的全局 window 合约说明

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`
- `deps/cadgamefusion/tools/web_viewer/adapters/editor_import_adapter.js`

preview runtime 的 artifact/document 加载不属于这里，应留在 `apps/web/preview/`。
