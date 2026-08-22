# 业务上下文

## 客户
- **示例客户**：cola-sample 演示项目的虚拟客户

## 角色
- **ADMIN**：管理员（用于验证与代码 @PreAuthorize 合并为 hybrid）

## 业务场景
- **创建订单**：(demo) 客户提交订单创建命令
- **查询订单**：(demo) 客户按 ID 查询订单详情

## 业务流程
### 订单处理流程
1. 创建订单 → CreateOrderCmdExe
2. 查询订单 → QueryOrderCmdExe
