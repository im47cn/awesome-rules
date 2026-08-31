-- 1. 企业
CREATE TABLE gdc_plf_company ( -- 公司=co,企业=entp，下同，不再赘述
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    company_name        varchar(100)    NOT NULL DEFAULT '' COMMENT '企业名称',
    credit_code         varchar(18)     NOT NULL DEFAULT '' COMMENT '统一社会信用代码',-- 字段英:uscc
    biz_lines           varchar(128)    NOT NULL DEFAULT '' COMMENT '对接业务线,逗号分隔[10-物流,20-商贸]',-- 字段英:biz_line_code_list,字段中:业务线代码列表(逗号分隔)[10-物流,20-商贸],字段类型长度，10就够了
    contact_name        varchar(20)     NOT NULL DEFAULT '' COMMENT '联系人姓名',-- 字段英:coner_name
    contact_title       varchar(50)     NOT NULL DEFAULT '' COMMENT '联系人职位',-- 字段英:coner_pos,长度过长，调整为20是不是就够了
    contact_mobile      varchar(11)     NOT NULL DEFAULT '' COMMENT '联系手机',-- 字段英:coner_mobile,字段中:联系人手机号
    contact_email       varchar(128)    NOT NULL DEFAULT '' COMMENT '联系邮箱',-- 字段英:coner_email,字段中:联系人邮箱，长度调整为50就够了
    remark              varchar(500)    NOT NULL DEFAULT '' COMMENT '备注',-- 长度过长，调整为200是不是就够了
    register_source     tinyint(4)      NOT NULL DEFAULT 10 COMMENT '注册来源[10-管理员创建,20-自助注册]',-- 字段英:reg_src
    company_status      tinyint(4)      NOT NULL DEFAULT 10 COMMENT '企业状态[10-正常,20-停用]',-- 公司=co,企业=entp
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY idx_credit_code (credit_code),-- 同步调整索引名和索引字段名称
    KEY idx_company_name (company_name)-- 同步调整索引名和索引字段名称
) COMMENT='开放平台-企业'; -- 据推测，表注释叫“企业信息表”就可以，同时表名对应着改为“gdc_entp_info”

-- 2. 应用
CREATE TABLE gdc_plf_app (
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    company_id          bigint(20)      NOT NULL DEFAULT 0 COMMENT '所属企业id',-- 公司=co,企业=entp，
    app_id              varchar(64)     NOT NULL DEFAULT '' COMMENT 'AppID',        -- 类型的长度，36就够了吧。
    app_secret          varchar(128)    NOT NULL DEFAULT '' COMMENT 'AppSecret', 
    app_name            varchar(50)     NOT NULL DEFAULT '' COMMENT '应用名称',
    app_desc            varchar(200)    NOT NULL DEFAULT '' COMMENT '应用描述',-- 描述=dscr
    register_source     tinyint(4)      NOT NULL DEFAULT 10 COMMENT '来源[10-管理员创建,20-自助注册]', -- 字段英:reg_src,字段中:注册来源[10-管理员创建,20-自助注册]
    app_status          tinyint(4)      NOT NULL DEFAULT 10 COMMENT '状态[10-启用,20-停用]',-- 字段中:应用状态[10-启用,20-停用]
    auth_mode           tinyint(4)      NOT NULL DEFAULT 0 COMMENT '鉴权方式[0-未指定,1-指定]',-- 方式=mtd,模式=mode
    auth_handler        varchar(100)    NOT NULL DEFAULT '' COMMENT '鉴权handler', -- 鉴权=aut，handler=经办人。缺后缀，如果存的是名称，长度50就够了，并且要加上后缀“_name”
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    UNIQUE KEY uk_app_id (app_id),
    KEY idx_company_id (company_id)-- 同步调整索引名和索引字段名称
) COMMENT='开放平台-应用';  -- 据推测，表注释叫“应用信息表”就可以，同时表名对应着改为“gdc_app_info”

-- 3. API定义
CREATE TABLE gdc_plf_api (-- 定义=defin
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    api_code            varchar(10)     NOT NULL DEFAULT '' COMMENT '接口编码(默认生成,如1001)',-- 字段中:api编码 （即，字段名中的api，在注释中也写做api，不用翻译，下同，不再赘述）
    api_name            varchar(128)    NOT NULL DEFAULT '' COMMENT '接口名称',  -- 类型的长度，20应该就够了
    api_domain          varchar(256)    NOT NULL DEFAULT '' COMMENT '接口域名',  -- 字段英:api_domain_name  。类型的长度，是不是太长了
    api_path            varchar(256)    NOT NULL DEFAULT '' COMMENT '接口路径',  -- 类型的长度，200是不是够
    api_version         varchar(16)     NOT NULL DEFAULT 'V1' COMMENT '接口版本(V1/V2)',-- 字段英:api_ver_no,-- 字段中:api版本号(V1,V2)。类型的长度，10应该够了
    biz_line            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '所属业务线[10-物流,20-商贸]',-- 根据表一同义字段的经验，字段英:blng_biz_line_code 字段中：所属业务线代码
    group_tag           varchar(50)     NOT NULL DEFAULT '' COMMENT '分组标签',-- 字段英:grp_tag。类型的长度，10应该够了，标签不需要写很长，很长的话肯定不方便使用
    http_method         varchar(10)     NOT NULL DEFAULT 'POST' COMMENT 'HTTP请求方法',-- 字段英:http_req_mtd
    brief_desc          varchar(500)    NOT NULL DEFAULT '' COMMENT '简要描述',-- brief_dscr。类型的长度，200
    detail_desc         text                     COMMENT '详细说明',-- 字段英:detl_dscr
    req_example         text                     COMMENT '请求示例',-- 字段英:req_ex
    resp_example        text                     COMMENT '响应示例',-- 字段英:resp_ex
    api_status          tinyint(4)      NOT NULL DEFAULT 10 COMMENT '状态[10-草稿,20-已发布,30-已废弃,40-已下线]',--字段中:api状态[10-草稿,20-已发布,30-已废弃,40-已下线]
    owner_name          varchar(36)     NOT NULL DEFAULT '' COMMENT '负责人名称',-- 字段英:resper_name
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY idx_api_code (api_code)
) COMMENT='开放平台-API定义';   -- “API定义表”

-- 4. API参数
CREATE TABLE gdc_plf_api_param (-- 参数=para
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    api_id              bigint(20)      NOT NULL DEFAULT 0 COMMENT 'API主键',-- 字段中:API ID
    param_scope         tinyint(4)      NOT NULL DEFAULT 10 COMMENT '参数范围[10-Header,20-Param,30-Body请求,40-响应]',-- 字段英:para_range
    parent_id           bigint(20)      NOT NULL DEFAULT 0 COMMENT '父节点id,0为根',  -- 字段名中没有体现“节点”或注释中多了“节点”。2，“0分根”用圆括号括起来
    param_name          varchar(100)    NOT NULL DEFAULT '' COMMENT '参数名',-- 字段英:para_name。2，类型的长度，20应该够了
    param_type          tinyint(4)      NOT NULL DEFAULT 0 COMMENT '参数类型[10-string,20-int,30-number,40-boolean,50-object,60-array]',-- 字段英:para_type
    required_flag       tinyint(4)      NOT NULL DEFAULT 0 COMMENT '必填标志[0-否,1-是]',-- 字段英:must_fill_flag
    example_value       varchar(500)    NOT NULL DEFAULT '' COMMENT '示例值',-- 字段英:ex_value,长度过长，调整为200是不是就够了
    param_desc          varchar(500)    NOT NULL DEFAULT '' COMMENT '参数说明',-- 字段英:para_dscr,长度过长，调整为200是不是就够了
    sort_no             int(11)         NOT NULL DEFAULT 0 COMMENT '排序号',
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY idx_api_id (api_id)
) COMMENT='开放平台-API参数';  -- “API参数表”

-- 5. 权限点
CREATE TABLE gdc_plf_permission_point (-- 权限点=perm_pt
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    perm_name           varchar(50)     NOT NULL DEFAULT '' COMMENT '权限点名称',-- 字段英:perm_pt_name
    perm_code           varchar(128)    NOT NULL DEFAULT '' COMMENT '权限点编码',-- 字段英:perm_pt_code,长度过长，调整为36是不是就够了
    perm_group          varchar(15)     NOT NULL DEFAULT '' COMMENT '权限点分组',-- 缺后缀
    biz_line            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '所属业务线[10-物流,20-商贸]',-- 字段英:blng_biz_line_code 所属业务线代码
    visibility          tinyint(4)      NOT NULL DEFAULT 20 COMMENT '可见性[10-内部,20-外部]',-- 据推测，改为：vis_type 可见类型[10-内部,20-外部]
    perm_status         tinyint(4)      NOT NULL DEFAULT 10 COMMENT '状态[10-启用,20-停用]',-- 字段英:perm_pt_status,字段中:权限点状态[10-启用,20-停用]
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY idx_perm_code (perm_code)-- 同步调整索引名和索引字段名称
) COMMENT='开放平台-权限点';    -- 另外，“权限点”是什么意思，它和“权限”有区别吗？待此问题回答后，再定表名是否合适

-- 6. 权限点-API关联
CREATE TABLE gdc_plf_permission_api_rel (-- 权限点=perm_pt
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    perm_id             varchar(128)    NOT NULL DEFAULT '' COMMENT '权限点主键',-- 字段英:perm_pt_id,字段中:权限点ID,长度过长，且与下表中类型不一致
    api_id              bigint(20)      NOT NULL DEFAULT 0 COMMENT 'API主键',-- 字段中:API ID
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    PRIMARY KEY (id),
    UNIQUE KEY uk_perm_id_api_id (perm_id, api_id)-- 同步调整索引名和索引字段名称
) COMMENT='开放平台-权限点API关联';

-- 7. 应用-权限授权
CREATE TABLE gdc_plf_app_permission (-- 权限=perm
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    app_id              bigint(20)      NOT NULL DEFAULT '' COMMENT 'App主键',-- 字段中:App ID
    perm_id             bigint(20)      NOT NULL DEFAULT '' COMMENT '权限点主键',-- 字段英:perm_pt_id,字段中:权限点ID
    grant_status        tinyint(4)      NOT NULL DEFAULT 10 COMMENT '授权状态[10-未开通,20-已开通,30-审核中]',-- 字段英: auth_status
    grant_time          datetime                 DEFAULT NULL COMMENT '开通时间',-- 开通=open,授权=auth
    grant_by            varchar(36)     NOT NULL DEFAULT '' COMMENT '开通操作人id',-- 开通=open,授权=auth,操作人=oprter
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time          datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    PRIMARY KEY (id),
    UNIQUE KEY uk_app_id_perm_id (app_id, perm_id)-- 同步调整索引名和索引字段名称
) COMMENT='开放平台-应用权限';-- “应用权限表”

-- 8. 字段映射
CREATE TABLE gdc_plf_field_mapping (-- 映射=mapp
    id                  bigint(20)      NOT NULL AUTO_INCREMENT COMMENT '主键',
    app_id              bigint(20)      NOT NULL DEFAULT '' COMMENT 'App主键',-- 字段中:App ID
    api_id              bigint(20)      NOT NULL DEFAULT 0 COMMENT 'API主键',-- 字段中:API ID
    direction           tinyint(4)      NOT NULL DEFAULT 10 COMMENT '方向[10-请求参数,20-响应参数]',-- 业务名称不明确，方向=dir
    src_field_relpath   varchar(256)    NOT NULL DEFAULT '' COMMENT '源字段相对路径',-- 长度过长，库中128就够了，和库中保持一致
    tgt_field_relpath   varchar(256)    NOT NULL DEFAULT '' COMMENT '目标字段相对路径',-- 长度过长，库中128就够了，和库中保持一致
    field_type          varchar(32)     NOT NULL DEFAULT '' COMMENT '字段类型',-- 是代码类字段的话,注释加上码值以及码值描述，调整字段类型或者长度；或者调整为xx名称，且长度为10
    convert_name        varchar(50)     NOT NULL DEFAULT '' COMMENT '转换器名称',-- 字段英:conver_name
    convert_para        varchar(50)     NOT NULL DEFAULT '' COMMENT '转换器参数',-- 字段英:conver_para
    prior_value         varchar(100)    NOT NULL DEFAULT '' COMMENT '优先值/默认值',-- 选择一个业务总称，可以将“优先值/默认值”补充到括号里，比如xx(优先值,默认值)
    is_required         tinyint(4)      NOT NULL DEFAULT 0 COMMENT '是否必填[0-否,1-是]',-- 建议和上表保持一致:字段英:must_fill_flag,字段中:必填标志[0-否,1-是]
    creator_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '创建人id',
    create_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater_id          varchar(36)     NOT NULL DEFAULT '' COMMENT '最后更新人id',-- 字段英:last_updater_id
    update_time         datetime        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',-- 字段英:last_update_time
    del_flag            tinyint(4)      NOT NULL DEFAULT 0 COMMENT '删除标志[0-否,1-是]',
    PRIMARY KEY (id),
    KEY idx_app_id_api_id_direction (app_id, api_id, direction)-- 同步调整索引名和索引字段名称
) COMMENT='开放平台-字段映射';-- “字段映射表”