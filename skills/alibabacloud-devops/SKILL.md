---
name: alibabacloud-devops
description: 阿里云云效 DevOps 平台工具集（165+ 工具）。当用户提到以下任意意图时激活：云效、Yunxiao、Codeup、代码仓库、分支、合并请求、变更请求、流水线、CI/CD、运行部署、项目管理、工作项、需求、缺陷、任务、迭代、工时、制品、应用交付、部署单、发布流程、测试用例、测试计划。通过 mcporter CLI 按需调用，不在 Claude Code 中常驻注册。
---

# 阿里云云效 DevOps（mcporter 代理模式）

**红线：刻意不注册为 MCP server**（165+ 工具 schema 常驻约 15k token/轮）。
所有调用走 mcporter CLI 按需查询与执行，设计论证见 [README](README.md)。

## 前置：访问令牌与变量约定
- 令牌探测顺序：优先检查环境变量 `YUNXIAO_ACCESS_TOKEN`（用户可能在其他终端窗口 export，非交互 shell 中不可见），再查 `~/.yunxiao_token`、`~/.aliyun/` 等本地配置；历史会话的「无令牌」结论不可复用，每次操作前须重新确认。
- 云效 OpenAPI 令牌对 `codeup.aliyun.com/api/v4` 认证无效（返回 302 登录页），不能据此误判为令牌失效，应改走云效 OpenAPI 端点。

```bash
export YUNXIAO_ACCESS_TOKEN=<your-token>   # 云效个人设置中获取
# 下文以 $YX 代指令牌环境、$SRV 代指 server 启动命令：
SRV='npx -y alibabacloud-devops-mcp-server'
YX='--env YUNXIAO_ACCESS_TOKEN=$YUNXIAO_ACCESS_TOKEN'
```

## 工具调用三件套

```bash
# 1. 查工具（先查后用，不要猜工具名；配合业务域关键词缩小范围）
mcporter list --stdio "$SRV" $YX --schema | grep -i pipeline

# 2. 调工具（参数 key=value，含空格值用 key:"..."）
mcporter call --stdio "$SRV" $YX <tool_name> key1=value1 key2="value 2"
# 若 --env 不生效，改用 shell 前置：YUNXIAO_ACCESS_TOKEN=... mcporter call --stdio "$SRV" <tool> ...

# 3. 可选：daemon 模式（避免每次 npx 冷启动数秒）
mcporter config add yunxiao && mcporter daemon start
mcporter list yunxiao --schema && mcporter call yunxiao.<tool> key=value   # 秒级响应
```

## 业务域导航（缩小查询范围）

先按域定位关键词，再 `mcporter list | grep -i <关键词>` 确认。工具清单随上游版本
变化，**始终以 `mcporter list` 实时结果为准**，不依赖静态清单。

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

## 典型工作流（模式参考，工具名以实时查询为准）
- PR 评论复核闭环：`git fetch` 对齐远程基线并确认新提交范围 → 逐条按最新代码判定未解决评论（仍成立/已修复/误判）→ 误判评论调更新接口置 `resolved=true` 并追加更正评论给出推翻证据；复核中发现的新问题另行发评论。

```bash
# 代码审查：get_current_organization_info → list_change_requests ... state=opened
#           → create_change_request_comment organizationId=<org> repositoryId=<repo> localId=123 content="LGTM"
# 流水线：  list_pipelines → create_pipeline_run pipelineId=123456 branch=main
#           → get_latest_pipeline_run pipelineId=123456
# 工作项：  search_projects keyword=<kw> → create_work_item workitemTypeId=<type-id> subject="..."
```

## 注意
- Codeup PR 评论接口：`POST /oapi/v1/codeup/organizations/{orgId}/repositories/{repoId}/changeRequests/{localId}/comments`，仓库级 changeRequests 端点会 404，须走组织级；请求体 `comment_type` 无默认值且仅 `GLOBAL_COMMENT` / `INLINE_COMMENT` 两个合法枚举，`resolved` 必填；resolve 已有评论用 PUT `comments/{commentId}` 且须再次携带 `resolved` 字段。

- 创建变更评论 `POST /oapi/v1/codeup/organizations/{orgId}/repositories/{repoId}/changeRequests/{localId}/comments`：`comment_type` 必填且仅 `GLOBAL_COMMENT` / `INLINE_COMMENT` 合法（无默认值），`resolved` 不可为 null，须显式传布尔值。
- 拉取评论列表用 POST 空 body；将评论标记已解决用 `PUT .../comments/{id}` + `{"resolved": true}`。
- 默认端点 `openapi.aliyun.com` 为全球单节点，受限网络下 TLS 握手可能被静默丢弃；此时改用中心版端点 `openapi-rdc.aliyuncs.com`（`/oapi/v1/...` 路径一致，认证头同为 `x-yunxiao-token`），勿据此判定令牌失效或 API 不可用。
- `devops.cn-hangzhou.aliyuncs.com` RPC 网关（RAM 风格 Action 探测）不含 Codeup 模块，不要在此浪费探测。

- 参数值含空格或特殊字符须加引号；布尔/数字按 API 要求的类型传
- 官方文档：https://help.aliyun.com/zh/yunxiao/
