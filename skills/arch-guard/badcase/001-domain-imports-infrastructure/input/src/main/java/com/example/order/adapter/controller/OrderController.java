package com.example.order.adapter.controller;

import com.example.order.domain.entity.OrderE; // ❌ Adapter 禁止直接引用领域对象

public class OrderController {
    public OrderE getOrder(String id) { // ❌ 领域对象泄漏到 Adapter
        return null;
    }
}
