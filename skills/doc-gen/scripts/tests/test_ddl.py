"""DDLScanner 测试。

覆盖：CREATE TABLE 解析、列/类型、NOT NULL→nullable、DEFAULT、COMMENT、
主键标记、UNIQUE/普通索引、IF NOT EXISTS 语法、表注释、跳过 SKIP_DIRS、
空目录、损坏文件不抛异常。
"""

import pytest

from scanner.ddl import DDLScanner


SQL = """
CREATE TABLE `t_order` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键',
  `order_no` varchar(64) NOT NULL DEFAULT '' COMMENT '订单号',
  `amount` decimal(18,2) DEFAULT NULL,
  `status` int(11) DEFAULT '0',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_order_no` (`order_no`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB COMMENT='订单表';
"""


def test_extract_table_basic(tmp_path):
    """完整 DDL：表名/注释/列/主键/nullable/索引(唯一与普通)。"""
    (tmp_path / "schema.sql").write_text(SQL, encoding="utf-8")
    tables = DDLScanner(str(tmp_path)).scan()
    assert len(tables) == 1
    t = tables[0]
    assert t.name == "t_order"
    assert t.comment == "订单表"

    cols = {c.name: c for c in t.columns}
    assert cols["id"].primaryKey is True
    assert cols["id"].comment == "主键"
    assert cols["order_no"].nullable is False          # NOT NULL
    assert cols["amount"].nullable is True             # 无 NOT NULL
    assert cols["status"].defaultValue == "'0'"

    idx = {i.name: i for i in t.indexes}
    assert idx["uk_order_no"].unique is True
    assert idx["idx_status"].unique is False
    assert idx["idx_status"].columns == ["status"]


def test_create_table_if_not_exists(tmp_path):
    """IF NOT EXISTS 语法 + 无 ENGINE 仅分号结尾。"""
    sql = ("CREATE TABLE IF NOT EXISTS t_simple (`id` int NOT NULL, "
           "`name` varchar(50) COMMENT '名称');")
    (tmp_path / "a.sql").write_text(sql, encoding="utf-8")
    tables = DDLScanner(str(tmp_path)).scan()
    assert len(tables) == 1
    assert tables[0].name == "t_simple"
    assert tables[0].columns[0].name == "id"


def test_skip_dirs_excluded(tmp_path):
    """target/ 等跳过目录下的 .sql 不扫描。"""
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "build.sql").write_text(SQL, encoding="utf-8")
    assert DDLScanner(str(tmp_path)).scan() == []


def test_no_sql_files_returns_empty(tmp_path):
    """无 .sql 文件 → 空列表。"""
    assert DDLScanner(str(tmp_path)).scan() == []


def test_malformed_file_does_not_raise(tmp_path):
    """编码/解析异常的文件被静默跳过（except Exception: pass）。"""
    # 乱写内容 + 故意制造 read 异常：写入非法 utf-8 字节
    bad = tmp_path / "bad.sql"
    bad.write_bytes(b"\xff\xfe CREATE TABLE")
    # 不应抛异常
    tables = DDLScanner(str(tmp_path)).scan()
    assert tables == []          # 无有效 CREATE TABLE


def test_extract_tables_directly():
    """直接调用 _extract_tables 覆盖无表注释分支。"""
    sql = "CREATE TABLE t_x (`id` int NOT NULL, PRIMARY KEY (`id`));"
    scanner = DDLScanner("/tmp")
    res = scanner._extract_tables(sql)
    assert len(res) == 1
    assert res[0].comment == ""            # 无 COMMENT='...'
