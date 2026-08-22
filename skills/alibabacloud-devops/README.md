# alibabacloud-devops

阿里云云效 DevOps 平台工具集（165+ 工具），经 mcporter CLI 按需代理调用。

## 设计说明：为何不注册为 MCP server

本技能**刻意不**通过 `.mcp.json` 注册云效 MCP server。该 server 暴露 165+ 工具，
注册后所有工具 schema 会常驻上下文（约 15k token/轮；使用第三方模型代理时
Claude Code 的 Tool Search 可能被禁用，无法按需加载）。改用 mcporter CLI 代理后：

- 工具定义**不进上下文**，需要时用 `mcporter list` 动态查询（真正的渐进式披露）
- 调用走 `mcporter call`，与模型供应商、代理环境无关

## 典型工作流（完整命令版）

### 代码审查（合并请求）

```bash
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN get_current_organization_info
mcporter call --stdio "$SRV" --env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN \
  list_change_requests organizationId=<org> repositoryId=<repo> state=opened
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

## 相关文件

- 技能定义（AI 操作指引）：[SKILL.md](SKILL.md)
