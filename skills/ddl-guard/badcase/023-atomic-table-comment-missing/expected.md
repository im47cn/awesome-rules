# ddl-guard badcase — 违规-表注释缺失

check: ddl_check.py

## 说明

自动生成（gen_cases.py 正·原子）：违规-表注释缺失。生成即验证：实际检出 == 标注（与 ddl_check.py 同源，模板副作用由门禁拦截）。

来源: 规则「表注释缺失」违规模板

## 预期检查输出

- 脚本自动检出：表注释缺失
