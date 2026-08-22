-- 违规 1: 表名使用拼音
CREATE TABLE t_danpai_jixiao (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    danpai_jixiao_name  varchar(100)    NOT NULL COMMENT '单排效果名称',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='单排效果表';

-- 违规 2: 表名使用名词复数
CREATE TABLE t_user_orders (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_no            varchar(36)     NOT NULL COMMENT '订单编号',
    user_id             bigint(20)      NOT NULL COMMENT '用户id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='用户订单表';

-- 违规 3: 表名使用泛化词「关联」「业务」
CREATE TABLE t_order_business_rel (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_id            bigint(20)      NOT NULL COMMENT '订单id',
    business_id         bigint(20)      NOT NULL COMMENT '业务id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单业务关联表';

-- 违规 4: 字段名使用拼音
CREATE TABLE t_product_info (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    chanpin_mingcheng   varchar(100)    NOT NULL COMMENT '产品名称',
    jiage               decimal(10,2)   NOT NULL COMMENT '价格',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='产品信息表';

-- 违规 5: 字段名使用泛化词「关联」「业务」
CREATE TABLE t_order_detail (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_id            bigint(20)      NOT NULL COMMENT '订单id',
    business_type       varchar(50)     NOT NULL COMMENT '业务类型',
    associate_id        bigint(20)      NOT NULL COMMENT '关联id',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单详情表';

-- 违规 6: 字段名含义不清
CREATE TABLE t_config (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    field1              varchar(100)    NOT NULL COMMENT '字段1',
    field2              varchar(100)    NOT NULL COMMENT '字段2',
    data1               text            COMMENT '数据1',
    data2               text            COMMENT '数据2',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='配置表';

-- 违规 7: 表名围绕非核心主体设计
CREATE TABLE t_order_process_log (
    id                  bigint(20)      NOT NULL COMMENT '主键',
    order_id            bigint(20)      NOT NULL COMMENT '订单id',
    process_name        varchar(100)    NOT NULL COMMENT '流程名称',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_updater_id     varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',
    last_update_time    datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后更新时间',
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
) COMMENT='订单处理日志表';