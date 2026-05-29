# Workbench Selection

这个目录承接选择状态、选择展示和选择派生语义。

## 适合放在这里的内容

- selection summary / detail facts / quicklook 生成
- 选择上下文归一化、派生 action 上下文
- 选择和 panel 之间共享的展示级 helper

## 不应继续堆在这里的内容

- 命令注册和命令执行
- group 释放/复制等领域实现本身
- workbench 启动壳层

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/ui/selection_presenter.js`
- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`

选择层重点是稳定语义和展示格式，而不是新增全局入口。
