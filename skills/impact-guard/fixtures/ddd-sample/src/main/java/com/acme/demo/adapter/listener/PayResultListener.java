package com.acme.demo.adapter.listener;

import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import com.acme.demo.app.OrderCreateCmdExe;

@RocketMQMessageListener(topic = "pay-result")
public class PayResultListener {

    private final OrderCreateCmdExe orderCreateCmdExe;

    public PayResultListener(OrderCreateCmdExe orderCreateCmdExe) {
        this.orderCreateCmdExe = orderCreateCmdExe;
    }

    public void onMessage() {
        orderCreateCmdExe.execute();
    }
}
