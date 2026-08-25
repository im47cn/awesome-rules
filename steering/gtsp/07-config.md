---
title: 配置文件规范
scenario: bootstrap/application.yml
---

# 配置文件规范

> 适用：服务配置文件清单、必须项、敏感信息处理。

## 1. 配置文件清单

每个服务包含：`bootstrap.yml`（Nacos 注册/配置中心）、`application.yml`（服务基础配置）、`application-local.yml`（本地开发覆盖）。

## 2. application.yml 必须项

- `server.port` — 服务端口
- `server.servlet.context-path` — 必须与 `spring.application.name` 一致
- `spring.application.name` — 显式声明
- `spring.main.allow-bean-definition-overriding: true`
- `wlyd.trace.enabled: true` — 链路追踪必须开启

## 3. bootstrap.yml 与敏感信息
- 凭证按权限级别专用：面向客户端的公开凭证（如前端 anon key）不得用于服务端/CI 任务，服务端须使用对应的特权凭证（service_role/secret key）；行级安全（RLS）场景下低权限凭证会静默返回空数据集而非报错，此类静默错误比显式失败更难发现

- Nacos：`server-addr`（环境变量 `${NACOS_SERVER_ADDR:localhost:8848}`）、`discovery.namespace`、`config.file-extension: yaml`、`config.namespace`
- 敏感信息（Nacos 账密等）不硬编码，通过环境变量或配置中心注入；`bootstrap-local.yml` 本地密码不得提交生产分支
