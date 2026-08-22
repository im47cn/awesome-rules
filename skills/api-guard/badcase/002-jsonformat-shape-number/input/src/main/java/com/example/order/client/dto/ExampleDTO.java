package com.example.order.client.dto;

import com.fasterxml.jackson.annotation.JsonFormat;

/**
 * DTO 时间注解反例。
 */
public class ExampleDTO {

    private String orderNo;

    // ❌ 废弃：时间戳序列化（shape = NUMBER），须改为 ISO 8601 pattern
    @JsonFormat(shape = JsonFormat.Shape.NUMBER)
    private java.util.Date createTime;

    public String getOrderNo() { return orderNo; }
    public void setOrderNo(String orderNo) { this.orderNo = orderNo; }
}
