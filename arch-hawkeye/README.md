# 架构鹰眼 (Arch Hawkeye)

> 全局架构观测与治理 — 消费各项目 doc-gen 产出的 `doc-manifest/`，把"多个项目的文档拼在一起"
> 升级为"全局观测 + 治理闭环"。

## 定位

| | doc-gen（生产者） | 架构鹰眼（本项目） |
|---|---|---|
| 目标 | 新人 5 分钟看懂一个项目 | 全公司看清架构健康度 |
| 范围 | 单项目入门文档（业务+技术全维度） | 多项目聚合 / 跨项目链路 / 治理闭环 |
| 交接物 | `doc-manifest/`（AH-MANIFEST 契约） | — |

## 当前能力（Phase 1 起步）

```bash
# 聚合多个项目 manifest 到架构鹰眼站点（渲染复用 doc-gen 的 Astro 模板）
python3 scripts/hawkeye.py aggregate projects.json --output site/ --build
```

`projects.json`：

```json
{
  "title": "公司架构全景",
  "projects": [
    {"id": "order-system", "name": "订单系统", "manifest": "./order/doc-manifest/", "repo": "..."}
  ]
}
```

产出：公司级全景拓扑图、跨项目依赖矩阵、合并 ER 图与 API 规范的静态站点。

## 路线图（EARS 需求见 [requirements.md](requirements.md)）

| 阶段 | 能力 | 关键需求 |
|---|---|---|
| Phase 1 | 联邦聚合：CI 自注册 + 增量聚合（`evidence.revision` 指纹） | AH-A02/A03 · D01/D02 |
| Phase 2 | 跨项目真实链路：跨仓库知识图谱 + 可查询架构图 + 变更影响分析 | AH-C01–C04 |
| Phase 3 | 治理闭环：责任归属 / 债务登记 / 超期告警 / 增量零容忍门禁 | AH-D03–D07 |
| Phase 4 | 双模式：本地运行（零 LLM token）+ 集中处理 | AH-B01–B03 |

## 目录结构

```
arch-hawkeye/
├── requirements.md      # EARS 需求规格
├── AH-MANIFEST.md       # 公共契约（真相源在 skills/doc-gen/schemas/）
└── scripts/
    ├── hawkeye.py       # CLI 入口
    ├── aggregate.py     # 多项目聚合（自 doc-gen 迁移）
    └── tests/           # pytest
```

## 相关文档

- 需求规格：[requirements.md](requirements.md)
- 数据契约：[AH-MANIFEST.md](AH-MANIFEST.md)
- 数据生产者：[../skills/doc-gen/SKILL.md](../skills/doc-gen/SKILL.md)
