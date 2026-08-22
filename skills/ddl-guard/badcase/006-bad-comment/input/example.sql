-- 违规 1: 表注释缺失
CREATE TABLE t_order_no_comment (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
);

-- 违规 2: 表注释长度超过 64
CREATE TABLE t_order_very_long_comment (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的表注释，达到了七十个字符以上，超过了64个字符的限制';

-- 违规 3: 字段注释缺失
CREATE TABLE t_order_missing_field_comment (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL,
    buyer_id            bigint(20)      NOT NULL,
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单表-字段注释缺失';

-- 违规 4: 字段注释长度超过 128
CREATE TABLE t_order_long_field_comment (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常，这是一个非常长的字段注释，达到了一百四十个字符以上，超过了128个字符的限制',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单表-字段注释过长';

-- 违规 5: 字段注释含全角字符
CREATE TABLE t_order_fullwidth_comment (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号（订单号）',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id（买家ID）',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单表-注释含全角字符';

-- 违规 6: 注释使用 # 符号
CREATE TABLE t_order_hash_comment (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单表' -- 使用了 # 注释符号
    -- 这行使用了 # 注释
    # 这行也使用了 # 注释
;

-- 违规 7: -- 注释后缺少空格
CREATE TABLE t_order_no_space_comment (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单表'--注释后没有空格
    --这行注释后也没有空格
;

-- 违规 8: 逻辑删除字段注释不规范
CREATE TABLE t_order_bad_del_flag (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    buyer_id            bigint(20)      NOT NULL COMMENT '买家id',
    is_deleted          tinyint(4)      NOT NULL DEFAULT 0 COMMENT '是否删除[0-否,1-是]',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    PRIMARY KEY (id)
) COMMENT='订单表-逻辑删除字段不规范';