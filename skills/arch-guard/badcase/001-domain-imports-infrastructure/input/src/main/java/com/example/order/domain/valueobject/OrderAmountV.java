package com.example.order.domain.valueobject;

// ✅ 值对象在 domain 层，后缀 V，无框架依赖，无 setter
public class OrderAmountV {
    private final java.math.BigDecimal amount;

    public OrderAmountV(java.math.BigDecimal amount) {
        this.amount = amount;
    }

    public OrderAmountV add(OrderAmountV other) {
        return new OrderAmountV(this.amount.add(other.amount));
    }
}
