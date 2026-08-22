# arch-guard badcase 004 — adapter 层直接改写状态 + 状态机治理缺失

check: arch_check.py

## 预期检查输出

- 脚本自动检出：状态泄漏、状态机治理

## 背景说明

- `OrderController`（adapter）真实调用 `setStatus(...)` → 状态泄漏（强制）；状态流转应收敛在 Domain 层
- 存在状态枚举 `OrderStatus` 但全项目无状态机框架 import → 状态机治理（推荐）
