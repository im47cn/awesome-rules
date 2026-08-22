package com.acme.demo.domain.order;

public interface OrderRepository {
    void save(OrderAgg agg);
}
