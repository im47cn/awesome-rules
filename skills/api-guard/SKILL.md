---
name: api-guard
description: >
  Open API 设计与规范审查。当用户提到以下任意意图时激活：审查API、审查接口、
  API设计、接口设计、API规范、接口规范、检查API、检查接口、API审核、接口审核、
  审查Controller、RESTful审查、开放平台规范、API合规检查。提供两类能力：
  (1) 按规范设计新 API，(2) 用脚本审查 Java Controller 中的 API 定义合规性。
---

# Open API 设计与审查

## 审查工作流

收到审查请求后，按以下步骤执行。

> ⚠️ **直接运行脚本，不要手动搜索或逐个打开 Controller 文件。**
> 脚本会自动扫描目标路径中的全部 `@RestController` / `@Controller` 文件。

### 第 1 步：运行检查脚本

脚本位于本 SKILL.md 同级的 `scripts/` 子目录。请根据本文件的实际路径定位脚本（不是用户项目的当前工作目录）。将用户项目中待审查的文件或目录路径作为参数传入：

```bash
python3 scripts/api_check.py <目标文件或目录> [--format json]
```

- `<目标文件或目录>`：用户项目中待审查的路径；不传则默认扫描当前目录
- 退出码：`0`=通过，`1`=有强制问题，`2`=运行错误
- 自动扫描 Java Controller，提取 `@PostMapping`/`@GetMapping` 等注解的端点定义
- 自动扫描 DTO/PO 契约对象，检查 `@JsonFormat` 时间注解合规性

### 第 2 步：补充人工判断

读取 [`api-manual-rules.md`](api-manual-rules.md)，逐个端点核对脚本无法覆盖的规则。

### 第 3 步：输出报告

将脚本自动检查结果与人工判断合并，输出完整审查报告。

## 设计新 API

读取 [`../../steering/openapi-standards.md`](../../steering/openapi-standards.md) 后按规范生成 API 定义，再用上述脚本自检。
