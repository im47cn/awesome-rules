package com.acme.demo.adapter.web;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import com.acme.demo.app.OrderCreateCmdExe;
import com.acme.demo.client.OrderCreateCO;

@RestController
public class OrderController {

    private final OrderCreateCmdExe orderCreateCmdExe;

    public OrderController(OrderCreateCmdExe orderCreateCmdExe) {
        this.orderCreateCmdExe = orderCreateCmdExe;
    }

    @PostMapping("/api/order/create")
    public OrderCreateCO create() {
        return orderCreateCmdExe.execute();
    }
}
