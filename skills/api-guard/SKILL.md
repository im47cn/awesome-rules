---
name: api-guard
description: >
  业务接口规范设计与审查。当用户提到以下任意意图时激活：审查API、审查接口、
  API设计、接口设计、API规范、接口规范、检查API、检查接口、API审核、接口审核、
  审查Controller、业务接口审查、API合规检查。提供两类能力：
  (1) 按规范设计新 API，(2) 用脚本审查 Java Controller 中的业务接口合规性。
  仅检查业务接口通用规范（路径命名、动作收敛、禁止 path 传标识、时间注解），不检查对外 Open API 四段式规范。
---

# 业务接口规范设计与审查

本技能审查**业务系统 Controller**（`@RestController`）的 API 定义合规性。

## 审查工作流

收到审查请求后，按以下步骤执行。

> ⚠️ **直接运行脚本，不要手动搜索或逐个打开 Controller 文件。**
> 脚本会自动扫描目标路径中的全部 `@RestController` / `@Controller` 文件。

### 第 1 步：运行检查脚本

脚本位于本 SKILL.md 同级的 `scripts/` 子目录。请根据本文件的实际路径定位脚本（不是用户项目的当前工作目录）。将用户项目中待审查的文件或目录路径作为参数传入：

```bash
python3 scripts/api_check.py <目标文件或目录> [--format json]
```

- `<目标文件或目录>`：待审查路径；不传则默认扫描当前目录
- `--format`：`text`（默认）或 `json`
- 退出码：`0`=通过，`1`=有强制问题，`2`=运行错误
- 自动扫描 Java Controller，提取 `@PostMapping`/`@GetMapping` 等端点；扫描 DTO/PO 契约对象检查 `@JsonFormat`

### 第 2 步：补充人工判断

读取 [`api-manual-rules.md`](api-manual-rules.md)，逐个端点核对脚本无法覆盖的规则（响应信封、参数约定、安全、文档等）。

### 第 3 步：输出报告

将脚本自动检查结果与人工判断合并，输出完整审查报告；按
[`../../steering/review-report-standards.md`](../../steering/review-report-standards.md)
五段式输出（含证据边界段）。

## 设计新 API

读取 [`../../steering/gtsp/03-api-feign.md`](../../steering/gtsp/03-api-feign.md)（GTSP API 接口规范）按规范生成业务接口定义，再用上述脚本自检。
