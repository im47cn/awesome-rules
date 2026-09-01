# ddl-guard badcase — 组合-长度三连

check: ddl_check.py

## 说明

自动生成（gen_cases.py 正·组合）：组合-长度三连。生成即验证：实际检出 == 标注（与 ddl_check.py 同源，模板副作用由门禁拦截）。

来源: 组合模板

## 预期检查输出

- 脚本自动检出：表注释长度、varchar长度、必含字段缺失
