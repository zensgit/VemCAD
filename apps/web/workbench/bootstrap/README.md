# Workbench Bootstrap

这个目录承接 editor workbench 的 bootstrap 和 composition 壳层。

## 适合放在这里的内容

- `bootstrapCadWorkspace()` 这一类稳定启动入口
- URL params、环境开关、全局对象暴露等壳层装配
- 跨 commands / panels / selection / io / solver 的初始化 wiring

## 不应继续堆在这里的内容

- 具体命令算法与 payload helper
- panel 细节实现
- 选择语义和 group 领域规则

## 当前迁移来源

- `deps/cadgamefusion/tools/web_viewer/ui/workspace.js`

## 当前 facade

- `workspace_bootstrap.js`
  - 暂时转发 `bootstrapCadWorkspace()`，为后续拆分提供产品层 import target。

bootstrap 层应尽量保持薄，只负责组装稳定接口，不重新承接领域逻辑。
