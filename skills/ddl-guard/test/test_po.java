package com.example.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;

/**
 * 测试用 PO 类 — 含多种规范违规
 */
@TableName("T_Order__Info")
public class TestOrderPO {

    @TableId
    private Long id;

    @TableField("order_no")
    private String orderNo;

    @TableField("Select")
    private String orderStatus;

    @TableField(exist = false)
    private String tempField;

    private String veryLongFieldNameThatExceedsThirtyCharacters;

    // 缺少必含字段: creator_id, create_time, last_updater_id, last_update_time, del_flag
}
