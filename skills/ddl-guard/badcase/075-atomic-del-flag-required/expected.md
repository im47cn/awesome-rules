# ddl-guard badcase — 违规-逻辑删除字段缺失

check: ddl_check.py

## 说明

业务表五项必含字段齐全但缺逻辑删除字段（del_flag 及等价别名均无）→ 【强制】逻辑删除字段缺失。
来源: steering/database-design-specification.md §逻辑删除字段【强制】（2026-09-24 del_flag 口径 A 接线）。
日志/流水表豁免（表名含 _log/_flow/_journal）。

## 预期检查输出

- 脚本自动检出：逻辑删除字段缺失
