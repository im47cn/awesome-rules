"""POScanner (MyBatis-Plus) 测试。

覆盖：@TableName/@TableField/@TableId 解析、exist=false 跳过、驼峰转下划线、
javadoc/行注释 → comment、类型映射、后缀预筛、Mapper XML 遍历、静态辅助方法。
"""

from scanner.po_scanner import POScanner


def _write(tmp_path, rel, text):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return str(rel)


PO_JAVA = """package com.x.infra.po;
@TableName("t_msg")
public class MsgPO {
    @TableId
    private Long id;
    private String userCode;
    @TableField("nick_name")
    private String nickName;
    @TableField(exist = false)
    private String ignore;
    /**
     * 状态[0-待签,1-已签]
     */
    private Integer status;
    private Integer type; // 0-禁用 1-启用
}
"""


def test_po_basic_extraction(tmp_path):
    """@TableName 定表名；@TableId 主键；@TableField 改列名；exist=false 跳过；驼峰转下划线。"""
    rel = _write(tmp_path, "src/MsgPO.java", PO_JAVA)
    java_files = [{"className": "MsgPO", "filePath": rel}]
    tables = POScanner(str(tmp_path)).scan(java_files)
    assert len(tables) == 1
    t = tables[0]
    assert t.name == "t_msg"
    cols = {c.name: c for c in t.columns}
    assert cols["id"].primaryKey is True
    assert cols["id"].type == "bigint"                 # Long → bigint
    assert cols["user_code"].name == "user_code"       # 驼峰转下划线
    assert cols["nick_name"].name == "nick_name"       # @TableField
    assert cols["nick_name"].type == "varchar(255)"    # String
    assert "ignore" not in cols                        # exist=false 跳过
    assert cols["status"].comment == "状态[0-待签,1-已签]"   # javadoc
    assert cols["type"].comment == "0-禁用 1-启用"          # 行注释


def test_po_skip_without_tablename(tmp_path):
    """无 @TableName 的 PO 类被跳过（不回退命名约定）。"""
    rel = _write(tmp_path, "src/A.java", "package x;\npublic class APO { private Long id; }\n")
    tables = POScanner(str(tmp_path)).scan([{"className": "APO", "filePath": rel}])
    assert tables == []


def test_po_skip_non_persist_suffix(tmp_path):
    """非 PO/BO/DO/Entity 后缀不进入持久化预筛。"""
    rel = _write(tmp_path, "src/B.java",
                 "package x;\n@TableName(\"t_b\")\npublic class BService { Long id; }\n")
    tables = POScanner(str(tmp_path)).scan([{"className": "BService", "filePath": rel}])
    assert tables == []


def test_po_value_syntax_tablename(tmp_path):
    """@TableName(value = "x") 语法 + BO 后缀（GTSP 领域实体带 @TableName）。"""
    rel = _write(tmp_path, "src/C.java",
                 "package x;\n@TableName(value = \"t_c\")\npublic class OrderBO { Long id; }\n")
    tables = POScanner(str(tmp_path)).scan([{"className": "OrderBO", "filePath": rel}])
    assert len(tables) == 1 and tables[0].name == "t_c"


def test_camel_to_snake_static():
    assert POScanner._camel_to_snake("userCode") == "user_code"
    assert POScanner._camel_to_snake("id") == "id"


def test_rm_id_to_table_branches():
    """resultMap id → 表名推断各分支。"""
    assert POScanner._rm_id_to_table("BaseResultMap") == "t_base_result_map"
    assert POScanner._rm_id_to_table("userMap") == "t_user_map"
    assert POScanner._rm_id_to_table("t_foo") == "t_foo"          # 已有 t_ 前缀
    assert POScanner._rm_id_to_table("") is None


def test_scan_mapper_xml_extracts_columns(tmp_path):
    """修复后：resultMap id 从完整标签提取，列从 <id>/<result> column 属性收集。"""
    xml = """<?xml version="1.0"?>
<mapper namespace="com.x.M">
  <resultMap id="BaseResultMap" type="Msg">
    <id column="id" property="id"/>
    <result column="code" property="code"/>
  </resultMap>
</mapper>
"""
    _write(tmp_path, "Mapper.xml", xml)
    tables = POScanner(str(tmp_path))._scan_mapper_xml_for_po()
    # BaseResultMap → t_base_result_map
    assert "t_base_result_map" in tables
    cols = {c for c, _ in tables["t_base_result_map"]}
    assert {"id", "code"} <= cols


def test_po_scan_merges_xml_columns(tmp_path):
    """scan 端到端：PO 表与同表名 XML resultMap 合并，补充 PO 未声明列。"""
    po_rel = _write(tmp_path, "src/MsgPO.java",
                    "package x;\n@TableName(\"t_msg\")\npublic class MsgPO {\n"
                    "  @TableId\n  private Long id;\n}\n")
    xml = """<?xml version="1.0"?>
<mapper namespace="x">
  <resultMap id="Msg" type="Msg">
    <id column="id" property="id"/>
    <result column="extra_col" property="extraCol"/>
  </resultMap>
</mapper>"""
    _write(tmp_path, "M.xml", xml)
    tables = POScanner(str(tmp_path)).scan([{"className": "MsgPO", "filePath": po_rel}])
    t = next(t for t in tables if t.name == "t_msg")
    cols = {c.name for c in t.columns}
    assert "id" in cols               # PO 声明
    assert "extra_col" in cols        # XML 补充


def test_read_file_missing_returns_empty():
    assert POScanner("/tmp")._read_file("nope.java") == ""
