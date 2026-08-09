#!/usr/bin/env python3
"""
api_check.py 单元测试

覆盖所有检查函数：
- 路径结构、HTTP 方法、命名、动词后置、路径变量、版本段
- 时间注解（DTO shape=NUMBER、PO 任何@JsonFormat）
- 文件发现（Controller / Contract）
- 报告格式
"""

import json
import os
import sys
import unittest
from unittest.mock import mock_open, patch

# 确保脚本在 Python path 中
sys.path.insert(0, os.path.dirname(__file__))

from api_check import (
    ApiEndpoint,
    Issue,
    Severity,
    ALLOWED_ACTIONS,
    SKIP_DIRS,
    check_path_structure,
    check_http_method,
    check_kebab_case,
    check_action_verb,
    check_path_variable,
    check_version_segment,
    check_endpoint,
    check_time_annotation,
    strip_java_comments,
    extract_endpoints,
    format_report_text,
    format_report_json,
    is_controller,
    is_contract_file,
    find_controller_files,
    find_contract_files,
    CONTRACT_CLASS_RE,
    PO_CLASS_RE,
    JSONFORMAT_NUMBER_RE,
    JSONFORMAT_ANY_RE,
)

import api_check  # noqa: E402 —— main()/契约检查需模块级引用


# ── 辅助函数 ──────────────────────────────────────────────────────────────

def _ep(**kwargs) -> ApiEndpoint:
    """快捷创建 ApiEndpoint，提供合理默认值。"""
    return ApiEndpoint(
        http_method=kwargs.get("http_method", "POST"),
        path=kwargs.get("path", "/logistics/v1/waybill/sync"),
        class_path=kwargs.get("class_path", "/logistics/v1/waybill"),
        method_name=kwargs.get("method_name", "syncWaybill"),
        file_path=kwargs.get("file_path", "Test.java"),
        line=kwargs.get("line", 1),
    )


# ── 路径结构检查 ─────────────────────────────────────────────────────────

class TestCheckPathStructure(unittest.TestCase):
    """检查路径结构 /{domain}/{version}/{resource}/{action}。"""

    def test_valid_four_segments(self):
        issues = []
        check_path_structure(_ep(path="/logistics/v1/waybill/sync"), issues)
        self.assertEqual(len(issues), 0)

    def test_three_segments(self):
        issues = []
        check_path_structure(_ep(path="/logistics/v1/waybill"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "路径结构不完整")
        self.assertEqual(issues[0].severity, Severity.MANDATORY)

    def test_two_segments(self):
        issues = []
        check_path_structure(_ep(path="/waybill/sync"), issues)
        self.assertEqual(len(issues), 1)
        self.assertIn("2 不足", issues[0].description)

    def test_one_segment(self):
        issues = []
        check_path_structure(_ep(path="/waybill"), issues)
        self.assertEqual(len(issues), 1)


# ── HTTP 方法检查 ─────────────────────────────────────────────────────────

class TestCheckHttpMethod(unittest.TestCase):
    """统一用 POST。"""

    def test_post_allowed(self):
        issues = []
        check_http_method(_ep(http_method="POST"), issues)
        self.assertEqual(len(issues), 0)

    def test_get_rejected(self):
        issues = []
        check_http_method(_ep(http_method="GET"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "统一POST")

    def test_put_rejected(self):
        issues = []
        check_http_method(_ep(http_method="PUT"), issues)
        self.assertEqual(len(issues), 1)

    def test_delete_rejected(self):
        issues = []
        check_http_method(_ep(http_method="DELETE"), issues)
        self.assertEqual(len(issues), 1)

    def test_patch_rejected(self):
        issues = []
        check_http_method(_ep(http_method="PATCH"), issues)
        self.assertEqual(len(issues), 1)

    def test_empty_method(self):
        issues = []
        check_http_method(_ep(http_method=""), issues)
        self.assertEqual(len(issues), 0)


# ── 命名检查 ──────────────────────────────────────────────────────────────

class TestCheckKebabCase(unittest.TestCase):
    """路径全小写 kebab-case，禁止 camelCase 和下划线。"""

    def test_valid_kebab(self):
        issues = []
        check_kebab_case(_ep(path="/logistics/v1/waybill/sync"), issues)
        self.assertEqual(len(issues), 0)

    def test_camel_case_rejected(self):
        issues = []
        check_kebab_case(_ep(path="/logistics/v1/waybill/syncWaybill"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "路径命名")

    def test_underscore_rejected(self):
        issues = []
        check_kebab_case(_ep(path="/logistics/v1/way_bill/sync"), issues)
        self.assertEqual(len(issues), 1)
        self.assertIn("下划线", issues[0].description)

    def test_path_variable_ignored(self):
        """路径变量 {id} 应被忽略。"""
        issues = []
        check_kebab_case(_ep(path="/logistics/v1/waybill/{id}"), issues)
        self.assertEqual(len(issues), 0)


# ── 动词后置检查 ──────────────────────────────────────────────────────────

class TestCheckActionVerb(unittest.TestCase):
    """末段（action）须使用收敛动词集。"""

    def test_valid_action(self):
        """单字有效动词（sync）不应被标记为动词前置。"""
        issues = []
        check_action_verb(_ep(path="/logistics/v1/waybill/sync"), issues)
        self.assertEqual(len(issues), 0)

    def test_all_allowed_actions(self):
        """验证所有允许的动词作为末段时均能通过（不标记动词前置）。"""
        for action in ALLOWED_ACTIONS:
            issues = []
            check_action_verb(_ep(path=f"/logistics/v1/waybill/{action}"), issues)
            # 单字有效动词不应被标记为动词前置
            verb_issues = [i for i in issues if i.rule == "动词后置"]
            self.assertEqual(len(verb_issues), 0, f"Expected {action} not to be flagged as verb-prefixed")

    def test_action_set_contains_expected_verbs(self):
        """验证动词集包含所有规范中声明的动词。"""
        expected = {"create", "query", "update", "remove", "cancel", "sync", "confirm", "apply", "push"}
        self.assertEqual(ALLOWED_ACTIONS, expected)

    def test_camel_case_sync_waybill(self):
        """syncWaybill 应被识别为动词前置。"""
        issues = []
        check_action_verb(_ep(path="/logistics/v1/waybill/syncWaybill"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "动词后置")
        self.assertIn("名词-动词序", issues[0].description)
        self.assertIn("sync", issues[0].suggestion)

    def test_multi_word_camel_case(self):
        """getWaybillList 中 get 不在动词集中，但 Waybill 也不在，应标记为不在动词集。"""
        issues = []
        check_action_verb(_ep(path="/logistics/v1/waybill/getWaybillList"), issues)
        # get 不在 ALLOWED_ACTIONS 中，所以不会触发动词后置，应标记为动作不收敛
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "动作收敛")

    def test_update_waybill_list(self):
        """updateWaybillList 中 update 在动词集中，应标记动词前置。"""
        issues = []
        check_action_verb(_ep(path="/logistics/v1/waybill/updateWaybillList"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "动词后置")
        self.assertIn("名词-动词序", issues[0].description)
        self.assertIn("/waybilllist/update", issues[0].suggestion)

    def test_unknown_action_not_in_set(self):
        """不在动词集中的单字动作应被标记为推荐级（动作不收敛）。"""
        issues = []
        check_action_verb(_ep(path="/logistics/v1/waybill/receive"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, Severity.RECOMMENDED)
        self.assertEqual(issues[0].rule, "动作收敛")
        self.assertIn("receive", issues[0].description)

    def test_two_segments_with_valid_action(self):
        """两段路径且末段为有效动词，check_action_verb 不报错（路径结构检查会单独报段数不足）。"""
        issues = []
        check_action_verb(_ep(path="/waybill/sync"), issues)
        self.assertEqual(len(issues), 0)


# ── 路径变量检查 ──────────────────────────────────────────────────────────

class TestCheckPathVariable(unittest.TestCase):
    """禁止 path 中传递唯一标识。"""

    def test_no_path_variable(self):
        issues = []
        check_path_variable(_ep(path="/logistics/v1/waybill/sync"), issues)
        self.assertEqual(len(issues), 0)

    def test_path_variable_rejected(self):
        issues = []
        check_path_variable(_ep(path="/logistics/v1/waybill/{id}"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "禁止path传标识")

    def test_multiple_path_variables(self):
        issues = []
        check_path_variable(_ep(path="/logistics/v1/order/{orderId}/item/{itemId}"), issues)
        self.assertEqual(len(issues), 1)


# ── 版本段检查 ────────────────────────────────────────────────────────────

class TestCheckVersionSegment(unittest.TestCase):
    """第二段须为版本号（v1, v2...）。"""

    def test_valid_version(self):
        issues = []
        check_version_segment(_ep(path="/logistics/v1/waybill/sync"), issues)
        self.assertEqual(len(issues), 0)

    def test_valid_version_v2(self):
        issues = []
        check_version_segment(_ep(path="/logistics/v2/waybill/sync"), issues)
        self.assertEqual(len(issues), 0)

    def test_invalid_version(self):
        issues = []
        check_version_segment(_ep(path="/logistics/api/waybill/sync"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "版本段")

    def test_missing_version(self):
        """路径段数刚好 2 时，第二段 'sync' 不是有效版本号，应被标记。"""
        issues = []
        check_version_segment(_ep(path="/waybill/sync"), issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "版本段")


# ── 综合检查 ──────────────────────────────────────────────────────────────

class TestCheckEndpoint(unittest.TestCase):
    """对单个端点执行全部检查。"""

    def test_compliant_endpoint(self):
        """完全合规的端点应无问题。"""
        ep = _ep(path="/logistics/v1/waybill/sync", http_method="POST")
        issues = check_endpoint(ep)
        self.assertEqual(len(issues), 0)

    def test_compliant_endpoint_json_format(self):
        """验证 JSON 格式输出。"""
        ep = _ep(path="/logistics/v1/waybill/sync", http_method="POST")
        result = format_report_json(ep.file_path, check_endpoint(ep))
        data = json.loads(result)
        self.assertEqual(data["summary"]["total"], 0)

    def test_non_compliant_endpoint(self):
        """不合规端点应检测到多个问题。"""
        ep = _ep(path="/logistics/v1/waybill/syncWaybill/{id}", http_method="GET")
        issues = check_endpoint(ep)
        # 应检测到：HTTP 方法、路径变量、动词后置、路径结构
        mandatory = [i for i in issues if i.severity == Severity.MANDATORY]
        self.assertGreater(len(mandatory), 0)


# ── 注释剥离 ──────────────────────────────────────────────────────────────

class TestStripJavaComments(unittest.TestCase):
    """Java 注释剥离，保留行号。"""

    def test_single_line_comment(self):
        result = strip_java_comments("public void foo() { // comment\n}")
        self.assertNotIn("comment", result)
        self.assertIn("\n", result)

    def test_multi_line_comment(self):
        result = strip_java_comments("""
/* line 1
   line 2
   line 3 */
public void foo() {}
""")
        self.assertNotIn("line 1", result)
        self.assertNotIn("line 2", result)
        self.assertNotIn("line 3", result)

    def test_preserves_line_count(self):
        """注释中的换行应被保留以保持行号。"""
        content = "/* line1\nline2\nline3 */\nfoo"
        result = strip_java_comments(content)
        self.assertEqual(result.count("\n"), content.count("\n"))


# ── 端点提取 ──────────────────────────────────────────────────────────────

class TestExtractEndpoints(unittest.TestCase):
    """从 Java 文件提取 API 端点。"""

    def test_simple_post_mapping(self):
        java = """
@RestController
@RequestMapping("/logistics/v1/waybill")
public class WaybillController {
    @PostMapping("/sync")
    public Result syncWaybill(@RequestBody WaybillDTO dto) {
        return Result.success();
    }
}
"""
        endpoints = extract_endpoints(java, "Test.java")
        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].http_method, "POST")
        self.assertEqual(endpoints[0].path, "/logistics/v1/waybill/sync")

    def test_get_mapping_rejected(self):
        java = """
@RestController
@RequestMapping("/logistics/v1/waybill")
public class WaybillController {
    @GetMapping("/query")
    public Result queryWaybill(@RequestParam String orderNo) {
        return Result.success();
    }
}
"""
        endpoints = extract_endpoints(java, "Test.java")
        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].http_method, "GET")

    def test_request_mapping_with_method(self):
        java = """
@RestController
@RequestMapping(value = "/logistics/v1/waybill", method = RequestMethod.POST)
public class WaybillController {
    @RequestMapping(value = "/sync", method = RequestMethod.GET)
    public Result syncWaybill() {
        return Result.success();
    }
}
"""
        endpoints = extract_endpoints(java, "Test.java")
        self.assertEqual(len(endpoints), 1)
        self.assertEqual(endpoints[0].http_method, "GET")

    def test_no_mapping(self):
        java = """
@Service
public class WaybillService {
    public void sync() {}
}
"""
        endpoints = extract_endpoints(java, "Test.java")
        self.assertEqual(len(endpoints), 0)


# ── 时间注解检查 ──────────────────────────────────────────────────────────

class TestCheckTimeAnnotation(unittest.TestCase):
    """检查 DTO/PO 时间字段注解。"""

    def test_dto_shape_number_rejected(self):
        java = """
public class ExampleDTO {
    @JsonFormat(shape = JsonFormat.Shape.NUMBER)
    private java.util.Date createTime;
}
"""
        issues = check_time_annotation("ExampleDTO.java", java)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "时间注解")

    def test_dto_shape_number_short_rejected(self):
        java = """
public class ExampleDTO {
    @JsonFormat(shape = NUMBER)
    private java.util.Date createTime;
}
"""
        issues = check_time_annotation("ExampleDTO.java", java)
        self.assertEqual(len(issues), 1)

    def test_dto_iso8601_pattern_allowed(self):
        java = """
public class ExampleDTO {
    @JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "+08:00")
    private java.util.Date createTime;
}
"""
        issues = check_time_annotation("ExampleDTO.java", java)
        self.assertEqual(len(issues), 0)

    def test_po_any_jsonformat_rejected(self):
        java = """
@TableName("example")
public class ExamplePO {
    @JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "+08:00")
    private java.util.Date createTime;
}
"""
        issues = check_time_annotation("ExamplePO.java", java)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "PO禁日期注解")

    def test_po_in_po_path_rejected(self):
        """位于 /infrastructure/repository/po/ 路径下的文件视为 PO。"""
        java = """
public class ExamplePO {
    @JsonFormat(pattern = "yyyy-MM-dd", timezone = "+08:00")
    private java.util.Date createTime;
}
"""
        issues = check_time_annotation(
            "src/main/java/com/example/order/infrastructure/repository/po/ExamplePO.java",
            java,
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "PO禁日期注解")

    def test_no_jsonformat(self):
        java = """
public class ExampleDTO {
    private String orderNo;
}
"""
        issues = check_time_annotation("ExampleDTO.java", java)
        self.assertEqual(len(issues), 0)


# ── 报告格式 ──────────────────────────────────────────────────────────────

class TestReportFormat(unittest.TestCase):
    """报告格式输出。"""

    def test_text_no_issues(self):
        result = format_report_text("Test.java", [])
        self.assertIn("检查通过", result)

    def test_text_with_issues(self):
        issues = [
            Issue(
                file="Test.java", endpoint="/waybill/sync", http_method="GET",
                severity=Severity.MANDATORY, rule="统一POST",
                location="路径:/waybill/sync 方法:GET",
                description="使用了 GET，规范要求统一 POST",
                suggestion="所有 API 统一使用 POST 请求方式",
            )
        ]
        result = format_report_text("Test.java", issues)
        self.assertIn("【强制】问题: 1 项", result)
        self.assertIn("统一POST", result)

    def test_json_with_issues(self):
        issues = [
            Issue(
                file="Test.java", endpoint="/waybill/sync", http_method="GET",
                severity=Severity.MANDATORY, rule="统一POST",
                location="路径:/waybill/sync 方法:GET",
                description="使用了 GET，规范要求统一 POST",
                suggestion="所有 API 统一使用 POST 请求方式",
            )
        ]
        result = format_report_json("Test.java", issues)
        data = json.loads(result)
        self.assertEqual(data["file"], "Test.java")
        self.assertEqual(data["summary"]["total"], 1)
        self.assertEqual(data["summary"]["mandatory"], 1)
        self.assertEqual(data["summary"]["recommended"], 0)

    def test_json_no_issues(self):
        result = format_report_json("Test.java", [])
        data = json.loads(result)
        self.assertEqual(data["summary"]["total"], 0)


# ── 文件发现 ──────────────────────────────────────────────────────────────

class TestFileDiscovery(unittest.TestCase):
    """Controller 和 Contract 文件发现。"""

    def test_is_controller(self):
        java = """
@RestController
public class WaybillController {}
"""
        mock_file = mock_open(read_data=java)
        with patch("builtins.open", mock_file):
            self.assertTrue(is_controller("Test.java"))

    def test_is_not_controller(self):
        java = """
@Service
public class WaybillService {}
"""
        mock_file = mock_open(read_data=java)
        with patch("builtins.open", mock_file):
            self.assertFalse(is_controller("Test.java"))

    def test_is_contract_dto(self):
        java = """
public class WaybillDTO {
    private String orderNo;
}
"""
        mock_file = mock_open(read_data=java)
        with patch("builtins.open", mock_file):
            self.assertTrue(is_contract_file("WaybillDTO.java"))

    def test_is_contract_po(self):
        java = """
@TableName("waybill")
public class WaybillPO {
    private Long id;
}
"""
        mock_file = mock_open(read_data=java)
        with patch("builtins.open", mock_file):
            self.assertTrue(is_contract_file("WaybillPO.java"))

    def test_is_not_contract(self):
        java = """
@RestController
public class WaybillController {}
"""
        mock_file = mock_open(read_data=java)
        with patch("builtins.open", mock_file):
            self.assertFalse(is_contract_file("WaybillController.java"))

    def test_contract_class_re_pattern(self):
        """验证 CONTRACT_CLASS_RE 能匹配常见后缀。"""
        self.assertTrue(CONTRACT_CLASS_RE.search("class WaybillDTO"))
        self.assertTrue(CONTRACT_CLASS_RE.search("class WaybillPO"))
        self.assertTrue(CONTRACT_CLASS_RE.search("class WaybillCommand"))
        self.assertTrue(CONTRACT_CLASS_RE.search("class WaybillQuery"))
        self.assertFalse(CONTRACT_CLASS_RE.search("class WaybillController"))

    def test_po_class_re_pattern(self):
        """验证 PO_CLASS_RE 能匹配 PO 后缀。"""
        self.assertTrue(PO_CLASS_RE.search("class WaybillPO"))
        self.assertFalse(PO_CLASS_RE.search("class WaybillDTO"))


# ── 常量验证 ──────────────────────────────────────────────────────────────

class TestConstants(unittest.TestCase):
    """验证关键常量。"""

    def test_allowed_actions_contains_all_verbs(self):
        expected = {"create", "query", "update", "remove", "cancel", "sync", "confirm", "apply", "push"}
        self.assertEqual(ALLOWED_ACTIONS, expected)

    def test_skip_dirs_contains_common_build_dirs(self):
        self.assertIn("target", SKIP_DIRS)
        self.assertIn(".git", SKIP_DIRS)
        self.assertIn("node_modules", SKIP_DIRS)
        self.assertIn("test", SKIP_DIRS)


class TestContractAndMain(unittest.TestCase):
    """契约对象发现/检查 + main() CLI 端到端。"""

    def _tmpdir(self):
        import tempfile
        return tempfile.mkdtemp()

    def _run_main(self, argv):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        old = sys.argv
        sys.argv = argv
        buf = io.StringIO()
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                code = api_check.main()
        finally:
            sys.argv = old
        return code, buf.getvalue()

    # ── is_contract_file / find_contract_files ──────────────────────────────

    def test_is_contract_file_matches_dto(self):
        d = self._tmpdir()
        p = os.path.join(d, "OrderDTO.java")
        with open(p, "w", encoding="utf-8") as f:
            f.write("public class OrderDTO {}")
        self.assertTrue(api_check.is_contract_file(p))

    def test_is_contract_file_rejects_plain(self):
        d = self._tmpdir()
        p = os.path.join(d, "X.java")
        with open(p, "w", encoding="utf-8") as f:
            f.write("public class X {}")
        self.assertFalse(api_check.is_contract_file(p))

    def test_find_contract_files_in_dir(self):
        d = self._tmpdir()
        with open(os.path.join(d, "OrderDTO.java"), "w", encoding="utf-8") as f:
            f.write("public class OrderDTO {}")
        with open(os.path.join(d, "Other.java"), "w", encoding="utf-8") as f:
            f.write("public class Other {}")
        found = api_check.find_contract_files(d)
        self.assertTrue(any("OrderDTO.java" in p for p in found))
        self.assertFalse(any("Other.java" in p for p in found))

    def test_find_contract_files_single_file(self):
        d = self._tmpdir()
        p = os.path.join(d, "X.java")
        with open(p, "w", encoding="utf-8") as f:
            f.write("public class XxxDTO {}")
        self.assertEqual(api_check.find_contract_files(p), [p])

    # ── check_contract_file ─────────────────────────────────────────────────

    def test_check_contract_file_catches_time_annotation(self):
        dto = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "badcase",
            "002-jsonformat-shape-number", "input", "src", "main", "java",
            "com", "example", "order", "client", "dto", "ExampleDTO.java"))
        if not os.path.exists(dto):
            self.skipTest("badcase ExampleDTO 不存在")
        issues = api_check.check_contract_file(dto)
        self.assertTrue(any(i.rule in ("时间注解", "PO禁日期注解") for i in issues))

    # ── main() ──────────────────────────────────────────────────────────────

    def test_main_no_files_returns_2(self):
        code, _ = self._run_main(["api_check.py", self._tmpdir()])
        self.assertEqual(code, 2)

    def test_main_scans_controller_text_output(self):
        d = self._tmpdir()
        with open(os.path.join(d, "OrderController.java"), "w", encoding="utf-8") as f:
            f.write('@RestController\n@RequestMapping("/api/v1/orders")\n'
                    'public class OrderController {\n'
                    '  @PostMapping("/create")\n'
                    '  public String create() { return ""; }\n}')
        code, out = self._run_main(["api_check.py", d])
        self.assertIn(code, (0, 1))
        self.assertIn("总计", out)

    def test_main_json_format(self):
        d = self._tmpdir()
        with open(os.path.join(d, "C.java"), "w", encoding="utf-8") as f:
            f.write('@RestController @RequestMapping("/api/v1/c") '
                    'public class C { @PostMapping("/x") public String x() { return ""; } }')
        _, out = self._run_main(["api_check.py", d, "--format", "json"])
        stripped = out.strip()
        self.assertTrue(stripped.startswith("[") or stripped.startswith("{"))


# ── 运行 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main()
