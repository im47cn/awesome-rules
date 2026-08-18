# arch-guard badcase 005 — 静态导入进 domain + 注释/字符串误报抑制

check: arch_check.py

## 预期检查输出

- 脚本自动检出：领域层纯净度、依赖方向、状态泄漏
- 人工补充：误报抑制负向断言（块注释 import、javadoc class 命名、字符串 "updateStatus()"、注释 setStatus 不触发）由 tests/test_arch_check.py 单测覆盖，runner 不比对

## 背景说明

- 静态导入 `import static ...TransactionSynchronizationManager.getCurrentTransactionName` 进 domain 必须报 DOMAIN_PURITY（强制）——静态成员的层归属跟随宿主类
- 内部包通配 `com.example.other.adapter.web.*` 恰好 1 条 STRUCTURAL_DEBT（依赖方向检查统一报告，领域层纯净度不双报），描述含"通配 import 无法定位目标类，待 ArchUnit 复核"，不计入 mandatory_count；第三方通配（`java.util.*` 等）保持忽略
- adapter 真实调用 `order.setStatus(PAID)` 报 STATE_FIELD_LEAKAGE（强制）
