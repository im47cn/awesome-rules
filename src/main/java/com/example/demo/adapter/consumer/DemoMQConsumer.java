package com.example.demo.adapter.consumer;

import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;

@RocketMQMessageListener(topic = "demo-order-created", consumerGroup = "demo-cg")
public class DemoMQConsumer implements RocketMQListener<String> {
    @Override
    public void onMessage(String message) {
    }
}
