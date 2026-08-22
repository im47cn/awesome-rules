package com.acme.demo.app;

import com.acme.demo.client.PayClient;
import com.acme.demo.domain.order.OrderAgg;
import com.acme.demo.domain.order.OrderRepository;
import com.acme.demo.infra.mapper.OrderMapper;

public class OrderCreateCmdExe {

    private final OrderRepository orderRepository;
    private final OrderMapper orderMapper;
    private final PayClient payClient;

    public OrderCreateCmdExe(OrderRepository orderRepository, OrderMapper orderMapper, PayClient payClient) {
        this.orderRepository = orderRepository;
        this.orderMapper = orderMapper;
        this.payClient = payClient;
    }

    public com.acme.demo.client.dto.OrderCreateCO execute() {
        OrderAgg agg = new OrderAgg();
        orderRepository.save(agg);
        orderMapper.insert(agg);
        payClient.createPay();
        return new com.acme.demo.client.dto.OrderCreateCO();
    }
}
