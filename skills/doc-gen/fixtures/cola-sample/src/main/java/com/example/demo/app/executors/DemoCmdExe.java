package com.example.demo.app.executors;

import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;

public class DemoCmdExe {
    private RocketMQTemplate rocketMQTemplate;

    private StringRedisTemplate stringRedisTemplate;

    public void execute() {
        rocketMQTemplate.syncSend("demo-order-created", "order-created-event");
        stringRedisTemplate.opsForValue().set("order:detail:v2", "demo");
    }
}
