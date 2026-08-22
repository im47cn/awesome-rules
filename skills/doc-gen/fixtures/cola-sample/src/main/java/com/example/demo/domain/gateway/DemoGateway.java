package com.example.demo.domain.gateway;

import com.example.demo.domain.DemoEntity;

public interface DemoGateway {
    DemoEntity load(String id);
}
