# arch-guard badcase 003 — 跨域依赖违规（order → logistics）

check: arch_check.py

## 预期检查输出

- 脚本自动检出：跨域依赖

## 背景说明

- order 域模块 pom.xml 依赖 logistics 域模块（如 order-app → logistics-client）
- 跨业务域应通过 `-client` 契约或事件解耦，禁止直接依赖其他域的实现模块 → 跨域依赖（强制）
