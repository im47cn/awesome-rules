# 提示词集

- 巡检这个项目，domain 层有没有引入框架依赖？
- 帮我检查这个 Java 项目的架构分层违规。
- 这个项目的 import 写法有没有问题？

## 已知问题

- 静态导入（import static）曾绕过领域层纯净度检查：正则只捕获到 "static" 标记，宿主框架类漏报。
- 内部包通配 import（xxx.*）曾捕获到包名，层归属失真。
- 注释/javadoc 里的 `class XxxDTO`、字符串里的 `"updateStatus()"` 曾误触发命名与状态泄漏规则。
