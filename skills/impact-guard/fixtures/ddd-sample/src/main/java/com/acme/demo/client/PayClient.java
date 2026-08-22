package com.acme.demo.client;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;

@FeignClient(name = "gtsp-pay", url = "http://gtsp-pay")
public interface PayClient {

    @PostMapping("/api/pay/create")
    String createPay();
}
