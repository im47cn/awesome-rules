"""InfrastructureDBExtractor 测试。

覆盖：class_to_table 后缀剥离、DO 类 @Table/@Column/@Id/@GeneratedValue 解析、
javadoc/行注释提取、Mapper 方法名→索引、MyBatis XML insert→表/列、
infrastructure 路径过滤、无字段返回 None。
"""

from scanner.infra_db import InfrastructureDBExtractor


def _write(tmp_path, rel, text):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return str(rel)


# ── class_to_table ───────────────────────────────────────────────────────────

def test_class_to_table_variants():
    assert InfrastructureDBExtractor.class_to_table("OrderDO") == "t_order"
    assert InfrastructureDBExtractor.class_to_table("OrderMainDO") == "t_order_main"
    assert InfrastructureDBExtractor.class_to_table("UserPo") == "t_user"
    assert InfrastructureDBExtractor.class_to_table("FooEntity") == "t_foo"
    assert InfrastructureDBExtractor.class_to_table("BarModel") == "t_bar"
    assert InfrastructureDBExtractor.class_to_table("NoSuffix") == "t_no_suffix"


# ── _extract_from_do ─────────────────────────────────────────────────────────

DO_JAVA = """package com.x.infra;
@Table(name = "t_order")
public class OrderDO {
    @Id
    @GeneratedValue
    private Long id;
    @Column(name = "order_code")
    private String orderCode;
    private static final long serialVersionUID = 1L;
}
"""


def test_extract_from_do_with_annotations(tmp_path):
    rel = _write(tmp_path, "src/infrastructure/OrderDO.java", DO_JAVA)
    ext = InfrastructureDBExtractor(str(tmp_path))
    table = ext._extract_from_do({"className": "OrderDO", "filePath": rel, "package": "com.x"})
    assert table is not None
    assert table.name == "t_order"
    assert "MyBatis @Table 声明" in table.comment
    cols = {c.name: c for c in table.columns}
    assert cols["id"].primaryKey is True
    assert cols["id"].defaultValue == "auto_increment"     # @GeneratedValue
    assert cols["id"].comment == "id"                      # 无注释 → 字段名
    assert cols["order_code"].type == "varchar(255)"
    assert cols["order_code"].comment == "orderCode"
    assert "serialVersionUID" not in cols                  # 跳过


def test_extract_from_do_filename_fallback(tmp_path):
    """无 @Table → class_to_table 兜底 + 字段上方行注释提取。"""
    java = "package x;\npublic class UserDO {\n  // 主键\n  private Long id;\n}\n"
    rel = _write(tmp_path, "src/infrastructure/UserDO.java", java)
    ext = InfrastructureDBExtractor(str(tmp_path))
    table = ext._extract_from_do({"className": "UserDO", "filePath": rel})
    assert table.name == "t_user"
    assert "推断" in table.comment
    assert table.columns[0].comment == "主键"


def test_extract_from_do_no_columns_returns_none(tmp_path):
    rel = _write(tmp_path, "src/infrastructure/EmptyDO.java",
                 "package x;\npublic class EmptyDO {}\n")
    ext = InfrastructureDBExtractor(str(tmp_path))
    assert ext._extract_from_do({"className": "EmptyDO", "filePath": rel}) is None


def test_extract_from_do_file_missing_returns_none():
    ext = InfrastructureDBExtractor("/tmp")
    assert ext._extract_from_do({"className": "XDO", "filePath": "no.java"}) is None


# ── Mapper 推断 + 合并 ────────────────────────────────────────────────────────

def test_infer_table_from_mapper():
    ext = InfrastructureDBExtractor("/tmp")
    t = ext._infer_table_from_mapper({"className": "OrderMapper"})
    assert t is not None and t.name == "t_order"
    assert ext._infer_table_from_mapper({"className": "Foo"}) is None


def test_merge_mapper_info_adds_index():
    ext = InfrastructureDBExtractor("/tmp")
    from doctypes import TableDoc
    table = TableDoc(name="t_order", columns=[])
    ext._merge_mapper_info(table, {"methods": [{"name": "selectByOrderNo"}]})
    assert any(i.name == "idx_order_no" for i in table.indexes)
    # 重复方法名不重复加索引
    ext._merge_mapper_info(table, {"methods": [{"name": "deleteByOrderNo"}]})
    assert sum(1 for i in table.indexes if i.name == "idx_order_no") == 1


# ── MyBatis XML ───────────────────────────────────────────────────────────────

def test_scan_mapper_xml_insert(tmp_path):
    xml = """<?xml version="1.0"?>
<mapper namespace="com.x.M">
  <resultMap id="BaseResultMap" type="O">
    <id column="id" property="id"/>
    <result column="name" property="name"/>
  </resultMap>
  <insert id="insert">
    INSERT INTO t_order (id) VALUES (#{id}), (#{dto.code})
  </insert>
</mapper>
"""
    _write(tmp_path, "M.xml", xml)
    tables = InfrastructureDBExtractor(str(tmp_path))._scan_mapper_xml()
    assert "t_order" in tables
    cols = {c for c, _ in tables["t_order"]}
    assert "id" in cols and "code" in cols


def test_scan_mapper_xml_ignores_target(tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "M.xml").write_text("<mapper></mapper>", encoding="utf-8")
    assert InfrastructureDBExtractor(str(tmp_path))._scan_mapper_xml() == {}


# ── extract 端到端（infrastructure 过滤）──────────────────────────────────────

def test_extract_skips_non_infrastructure(tmp_path):
    rel = _write(tmp_path, "src/domain/OrderDO.java", DO_JAVA)
    # filePath 不含 /infrastructure/ → 被跳过
    tables = InfrastructureDBExtractor(str(tmp_path)).extract(
        [{"className": "OrderDO", "filePath": rel}])
    assert tables == []
