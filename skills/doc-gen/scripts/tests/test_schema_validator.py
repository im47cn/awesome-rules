"""schema 契约校验器 + 退出码/receipt 契约测试

覆盖：
- validator.py 内置子集校验器的各关键字正反例（type/enum/const/required/
  additionalProperties/pattern/联合类型/跨文件 $ref）
- COLA fixture 端到端 golden test（生成 → 自检 → validate 通过）——
  schema 与生成器 drift 的防线（archify check:validators 的等价物）
- build_receipt / collect_evidence / build_astro 失败传播
"""

from __future__ import annotations  # 兼容 Python 3.9：延迟求值 PEP 604 联合类型注解

import json
import subprocess
from pathlib import Path

import pytest

from validator import validate_manifest_dir, validate_shard
from builder.writer import ManifestWriter, collect_evidence
from builder.astro import build_astro
from doc_gen import (
    build_receipt,
    _build_from_manifest,
    _check_manifest_contract,
    _finish,
    _stale_commits,
)

FIXTURE_ROOT = Path(__file__).resolve().parent.parent.parent / "fixtures" / "cola-sample"


# ── 校验器关键字 ───────────────────────────────────────────────────────────────


class TestValidatorKeywords:
    """内置子集校验器：每个支持的关键字至少一正一反"""

    def test_type_string_ok(self):
        assert validate_shard({"type": "string"}, "hello") == []

    def test_type_string_fail(self):
        errs = validate_shard({"type": "string"}, 42)
        assert len(errs) == 1 and "类型" in errs[0]

    def test_type_union_string_null(self):
        schema = {"type": ["string", "null"]}
        assert validate_shard(schema, None) == []
        assert validate_shard(schema, "x") == []
        assert validate_shard(schema, 1) != []

    def test_type_integer_rejects_bool(self):
        # Python bool 是 int 子类，必须显式排除
        assert validate_shard({"type": "integer"}, True) != []

    def test_const_ok_and_fail(self):
        assert validate_shard({"const": 1}, 1) == []
        assert validate_shard({"const": 1}, 2) != []

    def test_enum_ok_and_fail(self):
        assert validate_shard({"enum": ["a", "b"]}, "a") == []
        assert validate_shard({"enum": ["a", "b"]}, "c") != []

    def test_required_missing(self):
        schema = {"type": "object", "required": ["name"]}
        assert "缺少必填字段 'name'" in validate_shard(schema, {})[0]

    def test_additional_properties_rejects_unknown(self):
        schema = {"type": "object",
                  "properties": {"a": {"type": "string"}},
                  "additionalProperties": False}
        assert validate_shard(schema, {"a": "x"}) == []
        errs = validate_shard(schema, {"a": "x", "colour": 1})
        assert any("colour" in e for e in errs)

    def test_pattern(self):
        schema = {"type": "string", "pattern": "^[a-f0-9]{40}$"}
        assert validate_shard(schema, "a" * 40) == []
        assert validate_shard(schema, "xyz") != []

    def test_min_length(self):
        assert validate_shard({"type": "string", "minLength": 1}, "") != []
        assert validate_shard({"type": "string", "minLength": 1}, "a") == []

    def test_minimum(self):
        assert validate_shard({"type": "integer", "minimum": 0}, -1) != []
        assert validate_shard({"type": "integer", "minimum": 0}, 0) == []

    def test_min_items(self):
        assert validate_shard(
            {"type": "array", "minItems": 1, "items": {"type": "string"}}, []) != []

    def test_min_properties(self):
        assert validate_shard(
            {"type": "object", "minProperties": 1}, {}) != []

    def test_items_nested_error_path(self):
        schema = {"type": "array", "items": {"type": "object",
                                             "required": ["name"]}}
        errs = validate_shard(schema, [{"name": "a"}, {}])
        assert "[1]" in errs[0]

    def test_cross_file_ref(self):
        """跨文件 $ref：domain.schema.json 引 common.schema.json 的 $defs"""
        schema = {"$ref": "common.schema.json#/$defs/crossDomainDep"}
        ok = {"fromDomain": "order", "toDomain": "logistics",
              "type": "client-api"}
        assert validate_shard(schema, ok, "domain.schema.json") == []
        bad = dict(ok, type="nonsense")
        assert validate_shard(schema, bad, "domain.schema.json") != []


# ── Golden test：schema 与生成器 drift 防线 ───────────────────────────────────


class TestGoldenManifest:
    """COLA fixture 端到端：真实扫描生成的 manifest 必须通过全部 schema 分片。

    若生成器新增字段而 schema 未同步，additionalProperties:false 会在此报错。
    """

    def _generate(self, tmp_path: Path):
        from scanner.maven import MavenScanner
        from scanner.java import JavaScanner
        from scanner.ddl import DDLScanner
        from scanner.state_machine import StateMachineScanner
        from generator.manifest import ManifestGenerator

        root = str(FIXTURE_ROOT)
        maven_info = MavenScanner(root).scan()
        java_files = JavaScanner(root).scan_java_files()
        tables = DDLScanner(root).scan()
        sms = StateMachineScanner(root).scan(java_files)
        config = json.loads((FIXTURE_ROOT / ".doc-gen.json").read_text(encoding="utf-8"))
        manifest = ManifestGenerator(root, config).generate(
            java_files, maven_info, tables, state_machines=sms)
        writer = ManifestWriter(tmp_path)
        writer.write(manifest)  # write() 内含自检，异常即测试失败
        return tmp_path / "doc-manifest"

    def test_cola_sample_passes_all_shard_schemas(self, tmp_path):
        manifest_dir = self._generate(tmp_path)
        assert validate_manifest_dir(manifest_dir) == []

    def test_index_has_contract_schema_version(self, tmp_path):
        manifest_dir = self._generate(tmp_path)
        index = json.loads((manifest_dir / "index.json").read_text(encoding="utf-8"))
        assert index["schema_version"] == 1

    def test_evidence_written_when_provided(self, tmp_path):
        evidence = {"repo_url": "https://example.com/repo",
                    "revision": "a" * 40,
                    "generatedAt": "2026-08-14T00:00:00+00:00",
                    "dirty": False}
        from doctypes import DocManifest
        writer = ManifestWriter(tmp_path, evidence=evidence)
        writer.write(DocManifest(meta={"project": {}}))
        meta = json.loads(
            (tmp_path / "doc-manifest" / "meta.json").read_text(encoding="utf-8"))
        assert meta["evidence"] == evidence

    def test_writer_self_check_raises_on_invalid_component(self, tmp_path):
        """违反契约的 component（className 空）→ write() 自检抛 RuntimeError"""
        from doctypes import DocManifest, DomainDoc, LayerDoc, ComponentDoc
        domain = DomainDoc(name="order")
        domain.layers["adapter"].components.append(
            ComponentDoc(type="controller", className=""))
        manifest = DocManifest(meta={"project": {}}, domains=[domain])
        with pytest.raises(RuntimeError, match="schema 自检失败"):
            ManifestWriter(tmp_path).write(manifest)

    def test_writer_self_check_raises_on_failed_domain_write(self, tmp_path):
        """域分片写入失败（并发池内异常）必须显式失败而非静默丢域"""
        from doctypes import DocManifest, DomainDoc
        manifest = DocManifest(meta={"project": {}}, domains=[DomainDoc(name="order")])
        writer = ManifestWriter(tmp_path)

        def _boom(domain):
            raise OSError("disk full")
        writer._write_domain_file = _boom
        with pytest.raises(RuntimeError, match="写入失败"):
            writer.write(manifest)


# ── Receipt 与退出码契约 ───────────────────────────────────────────────────────


class TestReceiptContract:
    def test_ok_when_no_fail(self):
        receipt = build_receipt({"maven": {"status": "ok"},
                                 "database": {"status": "warn"}})
        assert receipt["ok"] is True  # warn 是事实降级，不阻断

    def test_fail_when_any_fail(self):
        receipt = build_receipt({"build": {"status": "fail"}})
        assert receipt["ok"] is False

    def test_schema_version_pinned(self):
        assert build_receipt({})["schema_version"] == 1


class TestCollectEvidence:
    def test_no_git_degrades_to_null(self, tmp_path):
        ev = collect_evidence(tmp_path, {})
        assert ev["revision"] is None
        assert ev["dirty"] is False
        assert ev["repo_url"] is None

    def test_repo_url_from_config(self, tmp_path):
        ev = collect_evidence(tmp_path, {"project_repo": "https://x/y"})
        assert ev["repo_url"] == "https://x/y"


class TestFinishExitCodeContract:
    """_finish 是退出码契约的执行点：fail 必须 exit(1)，绝不静默成功"""

    def test_ok_prints_and_exits_zero(self, tmp_path, capsys):
        _finish(build_receipt({"build": {"status": "ok"}}), tmp_path, "done")
        assert "✅ done" in capsys.readouterr().out

    def test_fail_exits_one_and_writes_receipt(self, tmp_path):
        receipt = build_receipt({"build": {"status": "fail"}})
        with pytest.raises(SystemExit) as e:
            _finish(receipt, tmp_path, "done")
        assert e.value.code == 1
        written = json.loads((tmp_path / "receipt.json").read_text(encoding="utf-8"))
        assert written["ok"] is False
        assert written["checks"]["build"]["status"] == "fail"


class TestManifestContractGate:
    """消费端 schema 门禁：v1 严格校验，legacy 宽松跳过"""

    def _write_shards(self, md: Path, index_extra: dict | None = None):
        md.mkdir(parents=True, exist_ok=True)
        index = {"schema_version": 1, "domainCount": 0, "componentCount": 0,
                 "tableCount": 0, "domains": []}
        index.update(index_extra or {})
        (md / "index.json").write_text(json.dumps(index), encoding="utf-8")
        (md / "meta.json").write_text(json.dumps({"project": {}}), encoding="utf-8")
        (md / "database.json").write_text(
            json.dumps({"tables": []}), encoding="utf-8")
        (md / "state-machines.json").write_text("[]", encoding="utf-8")
        (md / "cross-domain.json").write_text("[]", encoding="utf-8")

    def test_v1_valid_passes(self, tmp_path):
        self._write_shards(tmp_path)
        assert _check_manifest_contract(tmp_path)["status"] == "ok"

    def test_v1_invalid_exits_one(self, tmp_path):
        self._write_shards(tmp_path, index_extra={"unknownField": 1})
        with pytest.raises(SystemExit) as e:
            _check_manifest_contract(tmp_path)
        assert e.value.code == 1

    def test_legacy_without_schema_version_warns_not_fails(self, tmp_path):
        self._write_shards(tmp_path, index_extra={"schema_version": None})
        check = _check_manifest_contract(tmp_path)
        assert check["status"] == "warn"


class TestLegacyConversionContract:
    def test_legacy_invalid_data_exits_one(self, tmp_path, monkeypatch):
        """旧版单文件数据违反 schema（type 空）→ 转换后自检失败 → exit 1"""
        legacy = {"meta": {"project": {}},
                  "domains": [{"name": "d", "layers": {"domain": {
                      "components": [{"type": "", "className": "E"}]}}}]}
        legacy_file = tmp_path / "old.json"
        legacy_file.write_text(json.dumps(legacy), encoding="utf-8")
        monkeypatch.setattr("doc_gen.build_astro", lambda o, m: True)
        with pytest.raises(SystemExit) as e:
            _build_from_manifest(str(legacy_file), str(tmp_path / "site"))
        assert e.value.code == 1


class TestOptionalReportShards:
    """risks/adrs/articles 可选分片：含数据正例 + 篡改反例 + 缺失合法"""

    def _manifest_dir(self, tmp_path):
        from doctypes import DocManifest
        ManifestWriter(tmp_path).write(DocManifest(meta={"project": {}}))
        return tmp_path / "doc-manifest"

    def test_risks_with_data_passes(self, tmp_path):
        md = self._manifest_dir(tmp_path)
        (md / "risks.json").write_text(json.dumps({
            "passed": False, "totalIssues": 1, "criticalCount": 1,
            "warningCount": 0, "infoCount": 0, "summary": {},
            "issues": [{"file": "src/A.java", "line": 10, "severity": "BLOCKER",
                        "level": "critical", "rule": "layer-purity",
                        "ruleCode": "G001", "description": "x", "suggestion": "y"}],
        }), encoding="utf-8")
        assert validate_manifest_dir(md) == []

    def test_risks_error_branch_passes(self, tmp_path):
        md = self._manifest_dir(tmp_path)
        (md / "risks.json").write_text(json.dumps(
            {"error": "arch_check.py 执行超时", "issues": [], "summary": {}}),
            encoding="utf-8")
        assert validate_manifest_dir(md) == []

    def test_risks_bad_level_rejected(self, tmp_path):
        md = self._manifest_dir(tmp_path)
        (md / "risks.json").write_text(json.dumps(
            {"issues": [{"file": "a", "level": "fatal"}]}), encoding="utf-8")
        assert any("risks.json" in e for e in validate_manifest_dir(md))

    def test_adrs_with_data_passes(self, tmp_path):
        md = self._manifest_dir(tmp_path)
        (md / "adrs.json").write_text(json.dumps({
            "total": 1, "adrs": [{"number": 1, "title": "用云效",
                                  "status": "accepted", "date": "2026-08-16",
                                  "filename": "adr/001.md", "sourcePath": "adr/001.md"}],
        }), encoding="utf-8")
        assert validate_manifest_dir(md) == []

    def test_adrs_missing_status_rejected(self, tmp_path):
        md = self._manifest_dir(tmp_path)
        (md / "adrs.json").write_text(json.dumps(
            {"adrs": [{"title": "x"}]}), encoding="utf-8")
        assert any("adrs.json" in e for e in validate_manifest_dir(md))

    def test_articles_with_data_passes(self, tmp_path):
        md = self._manifest_dir(tmp_path)
        (md / "articles.json").write_text(json.dumps({
            "total": 1, "categories": {"guide": 1},
            "articles": [{"slug": "intro", "title": "入门", "summary": "s",
                          "category": "guide", "wordCount": 100,
                          "sourcePath": "docs/intro.md", "link": "/articles/intro",
                          "body": "---\n---\n正文", "searchText": "正文"}],
        }), encoding="utf-8")
        assert validate_manifest_dir(md) == []

    def test_articles_unknown_field_rejected(self, tmp_path):
        md = self._manifest_dir(tmp_path)
        (md / "articles.json").write_text(json.dumps(
            {"articles": [{"slug": "x", "title": "y", "bogus": 1}]}),
            encoding="utf-8")
        assert any("articles.json" in e for e in validate_manifest_dir(md))

    def test_all_missing_still_valid(self, tmp_path):
        assert validate_manifest_dir(self._manifest_dir(tmp_path)) == []


class TestStaleCommits:
    def test_no_meta_returns_none(self, tmp_path):
        assert _stale_commits(tmp_path) is None

    def test_revision_without_git_returns_none(self, tmp_path):
        md = tmp_path / "doc-manifest"
        md.mkdir()
        (md / "meta.json").write_text(json.dumps(
            {"evidence": {"revision": "a" * 40}}), encoding="utf-8")
        assert _stale_commits(md) is None


class TestBuildAstroFailurePropagation:
    """npm 三条失败路径必须返回 False（退出码契约的根基）"""

    def _run_once(self, tmp_path):
        (tmp_path / "doc-manifest").mkdir(exist_ok=True)

    def test_npm_missing_returns_false(self, monkeypatch, tmp_path):
        self._run_once(tmp_path)

        def fake_run(*a, **k):
            raise FileNotFoundError()
        monkeypatch.setattr("builder.astro.subprocess.run", fake_run)
        assert build_astro(tmp_path) is False

    def test_npm_install_failure_returns_false(self, monkeypatch, tmp_path):
        self._run_once(tmp_path)

        def fake_run(*a, **k):
            raise subprocess.CalledProcessError(1, "npm install")
        monkeypatch.setattr("builder.astro.subprocess.run", fake_run)
        assert build_astro(tmp_path) is False

    def test_npm_build_failure_returns_false(self, monkeypatch, tmp_path):
        self._run_once(tmp_path)
        calls = {"install": False}

        def fake_run(cmd, **k):
            if cmd[1] == "install":
                calls["install"] = True
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            raise subprocess.CalledProcessError(2, "npm run build")
        monkeypatch.setattr("builder.astro.subprocess.run", fake_run)
        assert build_astro(tmp_path) is False
        assert calls["install"] is True

    def test_success_returns_true(self, monkeypatch, tmp_path):
        self._run_once(tmp_path)

        def fake_run(cmd, **k):
            if cmd[1] == "run":
                (tmp_path / "dist").mkdir(exist_ok=True)
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        monkeypatch.setattr("builder.astro.subprocess.run", fake_run)
        assert build_astro(tmp_path) is True

    def test_zero_exit_without_dist_returns_false(self, monkeypatch, tmp_path):
        self._run_once(tmp_path)

        def fake_run(cmd, **k):
            return subprocess.CompletedProcess(cmd, 0, b"", b"")
        monkeypatch.setattr("builder.astro.subprocess.run", fake_run)
        assert build_astro(tmp_path) is False
