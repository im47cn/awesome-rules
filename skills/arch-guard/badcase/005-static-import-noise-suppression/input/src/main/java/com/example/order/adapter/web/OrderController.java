package com.example.order.adapter.web;

public class OrderController {
    public void sync(Object order) {
        // 字符串字面量里的状态改写 —— 不应触发 STATE_FIELD_LEAKAGE
        log.info("call updateStatus() failed, retry later");
        // order.setStatus(PAID); —— 注释里的状态改写不应触发
        order.setStatus(PAID); // 真实调用：期望规则 STATE_FIELD_LEAKAGE（强制）
    }
}
