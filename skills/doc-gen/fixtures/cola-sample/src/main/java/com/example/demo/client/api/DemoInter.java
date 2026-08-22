package com.example.demo.client.api;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

@FeignClient(url = "${demo.service.url}", name = "demo-service",
             contextId = "demoInter", path = "/demo")
public interface DemoInter {

    @GetMapping("/v1/orders/{id}")
    DemoCO queryOrder(@PathVariable("id") Long id);
}
