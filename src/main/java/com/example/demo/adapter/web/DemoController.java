package com.example.demo.adapter.web;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/demo/v1")
public class DemoController {

    @GetMapping("/orders/{id}")
    public DemoCO queryOrder(@PathVariable("id") Long id) {
        return new DemoCO();
    }

    @PostMapping("/orders")
    public Long createOrder(@RequestBody @Valid CreateOrderCmd cmd) {
        return 1L;
    }
}
