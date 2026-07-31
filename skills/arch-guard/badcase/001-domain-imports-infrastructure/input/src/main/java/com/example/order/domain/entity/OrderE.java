package com.example.order.domain.entity;

import org.springframework.stereotype.Service;       // ✅ 注解类 — domain_annotation_imports 白名单放行
import org.springframework.web.client.RestTemplate; // ❌ 框架业务类 — 禁止
import jakarta.persistence.Entity;                   // ✅ JPA 标注注解允许

@Entity
public class OrderE {
    private Long id;
    private String orderNo;
}
