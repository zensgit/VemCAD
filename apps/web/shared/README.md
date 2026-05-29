# VemCAD Web Shared

这个目录用于承接 `workbench` 与 `preview` 共用的 Web 模块。

适合收敛到这里的能力包括：

- shared adapters
- import normalization
- document / manifest 解析辅助
- shared state / contract helper
- Web 层通用测试夹具

不适合放入这里的能力包括：

- workbench 专属命令
- preview 专属入口装配
- desktop 壳层逻辑

共享模块的目标是减少重复，而不是重新做一个横向“超级公共目录”吞掉领域边界。
