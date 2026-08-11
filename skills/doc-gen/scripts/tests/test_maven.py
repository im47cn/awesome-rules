"""MavenScanner 测试。

覆盖：多模块 scan、_parse_pom（groupId/artifactId/modules/dependencies/parent 继承）、
_parse_dependency（无 artifactId 返回 None）、嵌套模块递归、无 pom/不可解析分支。
"""

import xml.etree.ElementTree as ET

from scanner.maven import MavenScanner


ROOT_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <groupId>com.x</groupId>
  <artifactId>parent</artifactId>
  <modules>
    <module>app</module>
    <module>missing</module>
  </modules>
  <dependencies>
    <dependency>
      <groupId>com.a</groupId><artifactId>lib-a</artifactId><version>1.0</version>
    </dependency>
  </dependencies>
</project>
"""

APP_POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent><groupId>com.x</groupId><artifactId>parent</artifactId><version>1</version></parent>
  <artifactId>app</artifactId>
  <modules><module>sub</module></modules>
</project>
"""

SUB_POM = """<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <parent><groupId>com.x</groupId><artifactId>app</artifactId><version>1</version></parent>
  <artifactId>app-sub</artifactId>
</project>
"""


def test_scan_multi_module(tmp_path):
    (tmp_path / "pom.xml").write_text(ROOT_POM, encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    (app / "pom.xml").write_text(APP_POM, encoding="utf-8")
    (app / "sub").mkdir()
    (app / "sub" / "pom.xml").write_text(SUB_POM, encoding="utf-8")

    info = MavenScanner(str(tmp_path)).scan()
    assert info["groupId"] == "com.x"
    assert info["artifactId"] == "parent"
    assert "app" in info["modules"]
    assert "app-sub" in info["modules"]               # 嵌套递归
    assert "missing" not in info["modules"]            # 无 pom 跳过
    # parent groupId 继承
    assert info["modules"]["app"]["groupId"] == "com.x"
    assert info["modules"]["app-sub"]["path"] == "app/sub"


def test_parse_pom_returns_dependencies(tmp_path):
    (tmp_path / "pom.xml").write_text(ROOT_POM, encoding="utf-8")
    parsed = MavenScanner(str(tmp_path))._parse_pom(tmp_path / "pom.xml")
    assert parsed["groupId"] == "com.x"
    assert parsed["modules"] == ["app", "missing"]
    assert parsed["dependencies"][0]["artifactId"] == "lib-a"


def test_scan_no_pom(tmp_path):
    info = MavenScanner(str(tmp_path)).scan()
    assert "error" in info


def test_scan_unparseable(tmp_path):
    (tmp_path / "pom.xml").write_text("<<<not xml>>>", encoding="utf-8")
    info = MavenScanner(str(tmp_path)).scan()
    assert "error" in info


def test_parse_dependency_without_artifactId(tmp_path):
    scanner = MavenScanner(str(tmp_path))
    dep = ET.fromstring("<dependency><groupId>x</groupId></dependency>")
    assert scanner._parse_dependency(dep) is None
    dep2 = ET.fromstring("<dependency><artifactId>y</artifactId></dependency>")
    assert scanner._parse_dependency(dep2) == {"artifactId": "y"}


def test_parse_parent(tmp_path):
    scanner = MavenScanner(str(tmp_path))
    parent = ET.fromstring(
        "<parent><groupId>g</groupId><artifactId>a</artifactId><version>1</version></parent>")
    out = scanner._parse_parent(parent)
    assert out == {"groupId": "g", "artifactId": "a", "version": "1"}
