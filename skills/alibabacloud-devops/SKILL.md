---
name: alibabacloud-devops
description: 阿里云云效 DevOps 平台工具集（165+ 工具）。当用户提到以下任意意图时激活：云效、Yunxiao、Codeup、代码仓库、分支、合并请求、变更请求、流水线、CI/CD、运行部署、项目管理、工作项、需求、缺陷、任务、迭代、工时、制品、应用交付、部署单、发布流程、测试用例、测试计划。通过 mcporter CLI 按需调用，不在 Claude Code 中常驻注册。
---

# 阿里云云效 DevOps（mcporter 代理模式）

## 设计说明：为何不注册为 MCP server

本 Skill **刻意不**通过 `.mcp.json` 注册云效 MCP server。该 server 暴露 165+ 工具，注册后所有工具 schema 会常驻上下文（约 15k token/轮，且在使用第三方模型代理时 Claude Code 的 Tool Search 会自动关闭，无法按需加载）。改用 mcporter CLI 代理后：

- 工具定义**不进上下文**，需要时用 `mcporter list` 动态查询（真正的渐进式披露）
- 调用走 `mcporter call`，与模型供应商、代理环境无关

## 前置：访问令牌

```bash
# 必需：在云效个人设置中获取访问令牌
export YUNXIAO_ACCESS_TOKEN=<your-token>
```

下文以 `$YX` 代指令牌，`$SRV` 代指 server 启动命令：

```bash
SRV='npx -y alibabacloud-devops-mcp-server'
```

## 工具调用三件套

### 1. 查工具（先查后用，不要猜工具名）

```bash
mcporter list --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN --schema
```

配合业务域关键词缩小范围（见下方导航表）：

```bash
mcporter list --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN --schema | grep -i pipeline
```

### 2. 调工具

```bash
mcporter call --stdio "$SRV" \
  --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  <tool_name> key1=value1 key2=value2
```

- 参数格式：`key=value` 或 `key:"含空格的值"`
- 若 `--env` 不生效，改用 shell 前置：`YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN mcporter call --stdio "$SRV" <tool> ...`

### 3. 可选：daemon 模式（避免每次 npx 冷启动）

每次 `--stdio` 会重新拉起 npx（冷启动数秒）。高频使用时注册为命名 server 走 keep-alive：

```bash
mcporter config add yunxiao          # 按交互提示填入 stdio 命令与 env
mcporter daemon start
mcporter list yunxiao --schema       # 之后用「别名」调用，秒级响应
mcporter call yunxiao.<tool> key=value
```

## 业务域导航（缩小查询范围）

先按域定位关键词，再 `mcporter list | grep -i <关键词>` 确认工具名。工具清单随上游版本变化，**以实时查询为准**，不依赖静态清单。

| 业务域 | 关键词 |
| --- | --- |
| 组织 / 身份 | `organization`、`user` |
| 代码仓库 | `repository`、`branch`、`commit`、`file` |
| 合并请求 | `change_request` |
| 项目 / 迭代 / 工作项 | `project`、`sprint`、`work_item` |
| 工时 | `effort` |
| 流水线 | `pipeline` |
| 主机部署 | `vm_deploy` |
| 制品 | `package`、`artifact` |
| 应用交付 | `app`、`orchestration`、`change_order`、`release` |
| 测试 | `testcase`、`test_plan`、`test_result` |

## 典型工作流

### 代码审查（合并请求）

```bash
# 1. 取当前组织信息
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN get_current_organization_info

# 2. 列出待审核的合并请求
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  list_change_requests organizationId=<org> repositoryId=<repo> state=opened

# 3. 添加审查评论
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  create_change_request_comment organizationId=<org> repositoryId=<repo> localId=123 content="LGTM"
```

### 运行流水线并查看结果

```bash
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN list_pipelines organizationId=<org>
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  create_pipeline_run organizationId=<org> pipelineId=123456 branch=main
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  get_latest_pipeline_run organizationId=<org> pipelineId=123456
```

### 项目管理（工作项）

```bash
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  search_projects organizationId=<org> keyword=my-project
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  create_work_item organizationId=<org> workitemTypeId=<type-id> subject="实现新功能"
```

## 注意

- 参数值含空格或特殊字符须加引号；布尔/数字按 API 要求的类型传
- 工具清单随上游 `alibabacloud-devops-mcp-server` 版本变化，**始终以 `mcporter list` 实时结果为准**
- 官方文档：https://help.aliyun.com/zh/yunxiao/
