# ddl-guard eval 007 — 合规 DDL（放行型）

check: ddl_check.py

## 说明

本 case 为**放行型**评估样本：input/ 为完全合规的 DDL（必含字段齐全、命名规范、
索引规范、注释规范），预期**零检出**。用于打分器 precision 侧验证——
「该拦的拦到 + 该放的放行」。

## 预期检查输出

（本 case 无脚本自动检出项——预期 ddl_check.py 检出为空）
