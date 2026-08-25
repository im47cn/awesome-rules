# 消融实验汇总

| 技能 | badcase | 臂 | 检出率 | 命中/期望 | 耗时(s) | prompt/输出 chars | 估算 token(chars/4) |
|---|---|---|---|---|---|---|---|
| ddl-guard | 001-forbidden-type-and-missing-comment | with | 0.6 | 3/5 | 124.3 | 4736/2445 | ~1795 |
| ddl-guard | 001-forbidden-type-and-missing-comment | without | 0.6 | 3/5 | 112.4 | 625/2064 | ~672 |
| ddl-guard | 004-bad-index | with | 0.833 | 5/6 | 152.1 | 9309/2316 | ~2906 |
| ddl-guard | 004-bad-index | without | 1.0 | 6/6 | 62.0 | 5198/2474 | ~1918 |
| api-guard | 001-wrong-http-method-and-naming | with | 1.0 | 3/3 | 118.3 | 3395/1519 | ~1228 |
| api-guard | 001-wrong-http-method-and-naming | without | 0.0 | 0/3 | 65.4 | 779/1073 | ~463 |

- WITH 平均 0.811 vs WITHOUT 平均 0.533，差 +0.278
- WITH 平均耗时 132s vs WITHOUT 80s
- WITH 平均估算 token 1976 vs WITHOUT 1018
