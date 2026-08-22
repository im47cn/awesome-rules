-- 违规 1: id 字段重复建索引
CREATE TABLE t_order_bad_index (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    order_status        tinyint(4)      NOT NULL DEFAULT 10 COMMENT '订单状态[10-待支付,20-已支付]',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY ix_order_no (order_no),
    KEY ix_buyer_id (buyer_id),
    KEY ix_id_status (id, order_status),  -- 违规: id 已有主键索引，无需再建
    KEY ix_buyer_status (buyer_id, order_status),
    KEY ix_create_time (create_time),
    KEY ix_status_time (order_status, create_time),
    KEY ix_extra1 (extra_field1),
    KEY ix_extra2 (extra_field2),
    KEY ix_extra3 (extra_field3)
) COMMENT='订单表-索引设计不当';

-- 违规 2: 联合索引字段数 > 5
CREATE TABLE t_order_too_many_cols (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    product_id          bigint(20)      NOT NULL COMMENT '商品id',
    shop_id             bigint(20)      NOT NULL COMMENT '店铺id',
    category_id         bigint(20)      NOT NULL COMMENT '分类id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY ix_order_no (order_no),
    KEY ix_multi_cols (order_no, buyer_id, product_id, shop_id, category_id, extra_field)
) COMMENT='订单表-联合索引字段过多';

-- 违规 3: 唯一索引命名不规范（未以 uk_ 开头）
CREATE TABLE t_order_bad_uk (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_no (order_no),
    UNIQUE KEY unique_buyer_id (buyer_id),  -- 违规: 唯一索引未以 uk_ 开头
    KEY ix_buyer_id (buyer_id)
) COMMENT='订单表-唯一索引命名不规范';

-- 违规 4: 普通索引命名不规范（未以 ix_ 开头）
CREATE TABLE t_order_bad_ix (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY ix_order_no (order_no),
    KEY idx_buyer_id (buyer_id),  -- 违规: 普通索引未以 ix_ 开头
    KEY idx_create_time (create_time)  -- 违规: 普通索引未以 ix_ 开头
) COMMENT='订单表-普通索引命名不规范';

-- 违规 5: 索引名长度超过 64
CREATE TABLE t_order_long_index (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY ix_order_no (order_no),
    KEY ix_this_is_a_very_long_index_name_that_exceeds_sixty_four_characters (buyer_id)
) COMMENT='订单表-索引名过长';