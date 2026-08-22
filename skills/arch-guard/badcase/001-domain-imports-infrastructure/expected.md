# arch-guard badcase 001 — domain 层 import 框架类 + 逆向依赖 + Adapter 直引领域对象

check: arch_check.py

## 预期检查输出

- 脚本自动检出：领域层纯净度、依赖方向、Adapter 隔离

## 背景说明

- `OrderE`（domain/entity）import `org.springframework.web.client.RestTemplate` → 领域层纯净度（强制）；`@Service`/JPA 注解走白名单放行
- `CreateOrderCmdExe`（application）import domain/entity 与 domain/valueobject 属合法方向，不计违规
- `OrderController`（adapter）import domain/entity/OrderE → Adapter 隔离（强制）
