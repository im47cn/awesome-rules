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

## Codeup 工作项（projex）OpenAPI 实测知识

REST 直连层知识（2026-08-26 破案沉淀，`.factory/forge` 全量实测；mcporter 工具
走同一后端，字段语义通用）。**排错第一信源：MCP server 仓的 swagger schema，
其次官方文档；黑盒探针路径形态成本极高**（实测 13 种形态全拒后才定位到正解）。

### 创建工作项（CreateWorkitem）五层要点

`POST /oapi/v1/projex/organizations/{orgId}/workitems`：

1. **API 本体必填仅 4 项**：`assignedTo` / `spaceId` / `subject` / `workitemTypeId`
   （swagger `CreateWorkitemRequest`）。帮助文档示例里看到的其它字段全可选。
2. **模板层必填字段走 `customFieldValues` 平面对象** `{"fieldId":"value"}`——
   数组形态报 `Invalid format`；不传模板必填字段报中文错误（如「字段【计划
   开始时间】不能为空」）。**不要用 gmtStart/startDate/startTime 等键名探针**：
   create API 没有时间本体字段。
3. **fieldId 从字段配置接口发现**：`GET /oapi/v1/projex/organizations/{org}/projects/{spaceId}/workitemTypes/{wit}/fields`（注意是 `projects/{spaceId}` 形态；`spaces/...`、直接 `workitemTypes/{id}/fields` 均 404）。返回项含 `id`（fieldId）、`name`、`type`（`NativeField`/`SystemCustomField`/`CustomField`）、`format`、`required`、`options`。
4. **value 形态**：`date`=ISO 日期串；`float`=小数字符串（`"0.5"` 过、`"1h"` 拒）；
   `list`=**option 的 id**（非文本——传「低」拒、传 option id `c18e89…` 过，
   options 数组里每项有 `value`/`displayValue`/`id`）；`NativeField` 不进
   customFieldValues（走本体字段）。
5. **assignedTo 是 24-hex 完整用户 id**（工作项详情 `assignedTo.id` 形态；
   截断 id 报 `Invalid.UserAccountId`）。成员查询端点不可达（多个候选 404/HTML），
   自动解析当前用户无门——从任一现有工作项详情取 `assignedTo.id` 或 `creator.id`。

### 其它工作项接口形态

- 详情：`GET .../workitems/{24-hex-id}`——按 `serialNumber`（如 `KFPT-16`）取需先
  `POST .../workitems:search`（`category` 必填如 `Task`；`workitemTypeId` 过滤被拒）。
- 评论写：`POST .../workitems/{id}/comments` + `{"content","contentType":"markdown"}`。
- 评论读：`GET .../workitems/{id}/comments`（需令牌含对应 scope，403 时报
  `Current token has no permission to api`）。
- 删除：`DELETE .../workitems/{id}`（200 空体）。
- labels：Task 类型常无 labels 字段（PUT 报 `workitem does not contains field`，
   非权限）——等价载体是 description 尾部 HTML 注释块（富文本完整保留注释）。
- 写操作可返回 200+空 body，按长度守卫解析为 `{}`，勿裸 `json.load`。

### 权限矩阵实测（个人令牌，2026-08-26）

| 面 | 结果 | 备注 |
| --- | --- | --- |
| 工作项读/搜索 | ✅ | 详情/列表/字段配置 |
| 工作项写（update/labels） | ✅ | description 模式标签全通 |
| 工作项创建/删除 | ✅ | 需上述五层正确姿势 |
| 工作项评论读/写 | ✅ | 令牌需项目管理评论 scope（此前 403，放开后全通） |
| Codeup MR 全套 | ✅ | 列表/详情/评论/diff/merge |

令牌权限变更后**必须复验**——403 结论有时效性（本技能两次实测口径相反即为证）。

## 注意

- **Codeup PR（changeRequest）评论**：`POST /oapi/v1/codeup/organizations/{orgId}/repositories/{repoId}/changeRequests/{localId}/comments`，仓库级 changeRequests 端点会 404，须走组织级；请求体 `comment_type` 必填且仅 `GLOBAL_COMMENT` / `INLINE_COMMENT` 合法（无默认值），`resolved` 不可为 null 须显式传布尔；拉取评论列表用 `POST .../comments/list`（body：`{"patchSetBizIds":[],"commentType":"GLOBAL_COMMENT","state":"OPENED","resolved":<bool>}`，resolved 两态各拉一次取全集）；resolve 已有评论用 `PUT .../comments/{commentBizId}` + `{"resolved": true}`（列表返回的主键字段名是 `comment_biz_id`）。
- **Codeup MR 列表**：组织级端点 `GET /oapi/v1/codeup/organizations/{org}/changeRequests`（**无** `/repositories` 段），URL query 传 `projectIds={repoId}` 过滤（POST/body 形态被拒）；摘要行无 status 字段，开合过滤交给服务端 `state` 参数。
- 默认端点 `openapi.aliyun.com` 为全球单节点，受限网络下 TLS 握手可能被静默丢弃；此时改用中心版端点 `openapi-rdc.aliyuncs.com`（`/oapi/v1/...` 路径一致，认证头同为 `x-yunxiao-token`），勿据此判定令牌失效或 API 不可用。公司网关对快速连续 TLS 握手偶发 RST（SSLEOFError）——握手失败=请求未发出，重试皆安全，建议 3 次退避。
- `devops.cn-hangzhou.aliyuncs.com` RPC 网关（RAM 风格 Action 探测）不含 Codeup 模块，不要在此浪费探测。
- 参数值含空格或特殊字符须加引号；布尔/数字按 API 要求的类型传。
- 官方文档：https://help.aliyun.com/zh/yunxiao/ ；OpenAPI 精确 schema 见 [alibabacloud-devops-mcp-server](https://github.com/aliyun/alibabacloud-devops-mcp-server) 仓 `docs/*.swagger.json`（比帮助文档表格更结构化，字段必填性/类型一查便知）。
