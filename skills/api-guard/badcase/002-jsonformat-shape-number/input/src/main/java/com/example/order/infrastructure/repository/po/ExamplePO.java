package com.example.order.infrastructure.repository.po;

import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonFormat;

/**
 * PO 时间注解反例。
 */
@TableName("example")
public class ExamplePO {

    private Long id;

    // ❌ PO 禁止任何日期格式化注解（PO 不加日期注解，格式化由 DTO 层负责）
    @JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "+08:00")
    private java.util.Date createTime;
}
