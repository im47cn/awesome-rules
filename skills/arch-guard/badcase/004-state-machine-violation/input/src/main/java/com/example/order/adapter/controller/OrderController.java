package com.example.order.adapter.controller;

/**
 * badcase 004：adapter 层直接改写状态（状态泄漏）。
 * 期望规则：STATE_FIELD_LEAKAGE（强制）。
 */
public class OrderController {
    public void pay() {
        // 违规：adapter 层直接 setStatus，状态流转应收敛在 Domain 层
        setStatus(PAID);
    }

    public void setStatus(Object s) { }
}
