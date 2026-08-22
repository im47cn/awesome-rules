package com.example.order.application.executor;

import com.example.order.domain.entity.OrderE; // ✅ Application 依赖 Domain 允许

public class CreateOrderCmdExe {
    public void execute() {
        OrderE order = new OrderE(); // ✅ 走领域链路
    }
}
