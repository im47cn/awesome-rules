# 业务接口规范审查：api-guard

## 1. 背景

为配合业务系统接口规范的平稳落地，结合 AI 编程时代的特点，亟需一款指导 AI 编程工具更好设计业务接口、编写代码和审查质量的 Skill。

> 本技能聚焦**业务系统 Controller 接口**。对外 Open API（四段式结构、统一 POST、版本段等）属另一套规范，见 `steering/openapi-standards.md`，不在本技能检查范围。

## 2. 目标

- 在接口设计阶段符合业务接口设计规范和审查标准
- 自动完成业务接口设计的审查和整改

## 3. 它能检查什么

脚本自动覆盖以下业务接口规则（粗筛），AI 再补充人工判断（精审）：

| 类别 | 检查项 |
|---|---|
| 路径命名 | 全小写 kebab-case，禁止 camelCase 和下划线 |
| 动作收敛 | 末段须在固定动词集内：create/query/update/remove/cancel/sync/confirm/apply/push |
| 路径变量 | 禁止 path 中传 `{id}` 等唯一标识 |
| 时间注解 | DTO 禁 `shape=NUMBER`（须 ISO 8601 pattern）；PO 禁任何日期注解 |

> 不检查对外 Open API 的四段式结构、统一 POST、版本段（业务接口不强制以 domain 开头、不强制带版本号；属 `steering/openapi-standards.md`）。
> 人工补充规则（响应体、参数约定、错误码、字段强类型、安全脱敏等）见 `api-manual-rules.md`。

## 4. 特点

- **标准**：封装公司业务接口相关设计规范（响应信封、参数校验、错误码、时间格式、安全脱敏等）
- **敏捷**：支持插件化安装、渐进式加载
- **质量**：测试覆盖率 100%，pytest 90% 门禁守护，回归防退化
- **共创**：支持贡献 badcase；同时提供回归测试脚本，可以自己调优提示词后再提交代码仓库

## 5. 风险提示

本工具旨在减少审查交互次数、提前规避常见问题，不能完全替代技术方案评审环节。

## 6. 安装方法

见《【Skills Hub】awesome-rules 做懂技术集团的 AI 搭子》。

---

## 7. API 设计案例

### 案例 1：从需求到合规业务接口

**背景**：运营后台需要新增一个"运单同步"接口，把运单状态推给下游系统。

**第 1 步**：跟 AI 讨论需求

> 我需要一个运单同步接口，接收运单号和状态，同步给下游系统。

**第 2 步**：使用 `api-guard` 技能设计接口

AI 读取 `steering/gtsp/03-api-feign.md` 规范后，生成合规定义：

```java
@RestController
@RequestMapping("/waybill")
public class WaybillController {

    @PostMapping("/sync")
    public Result syncWaybill(@RequestBody WaybillSyncCmd cmd) {
        // cmd.orderNo: 运单号
        // cmd.status: 运单状态
        return Result.success();
    }
}
```

为什么这样设计？

| 检查项 | 是否合规 | 说明 |
|---|---|---|
| 路径命名 | ✅ | 全小写 kebab-case |
| 路径变量 | ✅ | 无 `{id}`，标识放请求体 |

**第 3 步**：脚本自检

```bash
python3 skills/api-guard/scripts/api_check.py src/ --format json
```

退出码 `0`，通过。

---

## 8. API 审查案例

### 案例 1：审查存量 Controller

**输入**（一段典型的不合规 Controller）：

```java
@RestController
@RequestMapping("/logistics/v1/waybill")
public class WaybillController {

    @PostMapping("/create")
    public Result createWaybill(@RequestBody WaybillDTO dto) { ... }

    @GetMapping("/query")
    public Result queryWaybill(@RequestParam String orderNo) { ... }

    @PostMapping("/syncWaybill")
    public Result syncWaybill(@RequestBody SyncDTO dto) { ... }

    @PostMapping("/cancel/{id}")
    public Result cancelWaybill(@PathVariable Long id) { ... }
}
```

**第 1 步**：运行脚本

```bash
python3 skills/api-guard/scripts/api_check.py src/ --format json
```

**审查结果**：

| # | 端点 | 问题 | 级别 | 规则 |
|---|---|---|---|---|
| 1 | `POST /syncWaybill` | camelCase + 动词前置，应收敛为 `/sync` | 强制 | 路径命名 + 动词后置 |
| 2 | `POST /cancel/{id}` | 禁止 path 传唯一标识 | 强制 | 路径变量 |

> 注：业务接口规范不检查 HTTP 方法（GET/POST）与四段式结构，这些属对外 Open API 规范。

**结论**：❌ 不可通过审核，2 项【强制】问题。

**第 2 步**：AI 补充人工判断

逐个端点核对 `api-manual-rules.md`，补充脚本未覆盖项（如：`@RequestBody` 参数是否有强类型 DTO、返回体是否符合统一格式）。

**第 3 步**：修复后版本

```java
@RestController
@RequestMapping("/logistics/v1/waybill")
public class WaybillController {

    @PostMapping("/create")
    public Result createWaybill(@RequestBody WaybillCreateCmd cmd) { ... }

    @PostMapping("/sync")
    public Result syncWaybill(@RequestBody WaybillSyncCmd cmd) { ... }

    @PostMapping("/cancel")
    public Result cancelWaybill(@RequestBody WaybillCancelCmd cmd) { ... }
}
```

| 改动 | 说明 |
|---|---|
| `/syncWaybill` → `/sync` | 去 camelCase，路径命名合规 |
| `/cancel/{id}` → `/cancel` | 标识移到 body |

重新自检，退出码 `0`，通过。

### 案例 2

众人拾柴火焰高——欢迎大家贡献。
