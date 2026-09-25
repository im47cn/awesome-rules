CREATE TABLE t_order_detail (
    id bigint NOT NULL AUTO_INCREMENT,
    order_no varchar(32) NOT NULL,
    remark text,
    amount decimal(10,2) DEFAULT '0.00',
    status tinyint DEFAULT '0',
    del_flag tinyint NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id)
);
