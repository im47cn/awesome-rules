package com.example.demo.app.executors;

import org.apache.rocketmq.spring.core.RocketMQTemplate;

public class DemoCmdExe {
    private RocketMQTemplate rocketMQTemplate;

    public void execute() {
        rocketMQTemplate.syncSend("demo-order-created", "order-created-event");
    }
}
