#!/usr/bin/env python3
"""
DDD 架构分层守护脚本
检查 Java 项目分层依赖是否违反 COLA/DDD 架构规范。

用法:
  python3 arch_check.py <project_root> [--format json] [--strict] [--config .arch-guard.json]
  python3 arch_check.py <project_root> --baseline .arch-guard-baseline.json   # 仅报新增违规（存量偿还后基线自动收缩）
  python3 arch_check.py <project_root> --refreeze .arch-guard-baseline.json   # 有意重置债务线（唯一允许基线变大的路径）
  python3 arch_check.py <project_root> --baseline .arch-guard-baseline.json --frozen  # CI 模式（缺失/损坏 → exit 2；空基线=零债务放行）
  python3 arch_check.py --mode graph          # 输出 Tier 2 知识图谱 Cypher 查询清单
  python3 arch_check.py <root> --mode archunit --output <dir>  # 生成 ArchUnit 测试/properties/接入指引（Java 8 兼容）
  python3 arch_check.py <root> --mode archunit --verify         # 生成物漂移校验（不一致 → exit 1）

退出码: 0=通过, 1=有强制问题, 2=运行错误
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ── 配置默认值 ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "project_package_prefix": "",
    "layer_paths": {
        "adapter":        ["/adapter/"],
        "client":         ["/client/"],
        "application":    ["/application/"],
        "domain":         ["/domain/"],
        "infrastructure": ["/infrastructure/"],
    },
    # COLA 4.0 原生 web 层命名为 interfaces（开箱即用，无需配置）
    "layer_aliases": {
        "interfaces": "adapter",
    },
    "module_suffixes": {
        "adapter":        "adapter",
        "start":          "start",
        "client":         "client",
        "app":            "application",
        "domain":         "domain",
        "infrastructure": "infrastructure",
        "infra":          "infrastructure",
    },
    "domain_forbidden_pom": [
        "org.springframework.boot:spring-boot-starter",
        "org.springframework:spring-context",
        "org.mybatis:mybatis",
        "org.mybatis.spring.boot:mybatis-spring-boot-starter",
        "com.baomidou:mybatis-plus",
        "com.baomidou:mybatis-plus-boot-starter",
        "org.hibernate:hibernate-core",
    ],
    "domain_forbidden_imports": [
        "org.springframework",
        "org.mybatis",
        "com.baomidou.mybatisplus",
        "com.baomidou.mybatis",
        "org.hibernate",
        "org.apache.ibatis",
    ],
    "domain_allowed_imports": [
        "jakarta.persistence",
        "javax.persistence",
    ],
    # 务实 DDD：领域层允许使用的注解类框架包（仅注解，不含业务类）
    "domain_annotation_imports": [
        "org.springframework.stereotype",
        "org.springframework.transaction.annotation",
    ],
    # 状态机框架 import 前缀（识别形态 C，用于状态机治理检查）
    "state_machine_imports": [
        "org.springframework.statemachine",
        "com.alibaba.cola.statemachine",
    ],
}

SKIP_DIRS = {
    "target", "build", ".git", "node_modules", ".idea", ".vscode",
    ".gradle", ".mvn", "dist", "out", ".next", ".nuxt", "test", "tests",
}

MAVEN_NS = "http://maven.apache.org/POM/4.0.0"


# ── 规则代码（建议 fingerprint 纳入 code，中文 rule 保留为展示字段） ──────

DEP_DIRECTION    = "DEP_DIRECTION"
DOMAIN_PURITY    = "DOMAIN_PURITY"
DOMAIN_PURITY_POM = "DOMAIN_PURITY_POM"
NAMING           = "NAMING"
ADAPTER_ISOLATION = "ADAPTER_ISOLATION"
MAVEN_MODULE_DEP = "MAVEN_MODULE_DEP"
CROSS_DOMAIN_DEP = "CROSS_DOMAIN_DEP"
STATE_MACHINE       = "STATE_MACHINE"
STATE_FIELD_LEAKAGE = "STATE_FIELD_LEAKAGE"


class Severity(Enum):
    MANDATORY = "强制"
    RECOMMENDED = "推荐"
    STRUCTURAL_DEBT = "结构性债务"


@dataclass
class Issue:
    file: str
    line: int
    severity: Severity
    rule: str
    description: str
    rule_code: str = ""   # 英文字段，便于 CI/IDE 程序化解析（如 DEP_DIRECTION）
    suggestion: str = ""


# ── 调试/警告基础设施 ──────────────────────────────────────────────────────

_debug_enabled = False
_warnings: List[str] = []


def _debug(msg: str):
    if _debug_enabled:
        print(f"[DEBUG] {msg}", file=sys.stderr)


def _warn(msg: str):
    _warnings.append(msg)
    _debug(msg)


# ── 配置加载 ────────────────────────────────────────────────────────────────

def load_config(project_root: str, config_path: Optional[str] = None) -> Dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))

    if config_path is None:
        candidate = os.path.join(project_root, ".arch-guard.json")
        if os.path.isfile(candidate):
            config_path = candidate

    if config_path and os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as fp:
            overrides = json.load(fp)
        _deep_merge(cfg, overrides)

    return cfg


def _deep_merge(base: dict, overrides: dict):
    for k, v in overrides.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ── 层/域识别 ──────────────────────────────────────────────────────────────

def _build_layer_patterns(cfg: Dict) -> List[Tuple[str, re.Pattern]]:
    patterns = []
    for name, paths in cfg["layer_paths"].items():
        for p in paths:
            patterns.append((name, re.compile(re.escape(p))))
    return patterns


def identify_layer(file_path: str, layer_patterns: List[Tuple[str, re.Pattern]],
                   cfg: Dict) -> Optional[str]:
    for name, pattern in layer_patterns:
        if pattern.search(file_path):
            return name
    for alias, target in cfg["layer_aliases"].items():
        if f"/{alias}/" in file_path:
            return target
    return None


def _identify_module_layer(artifact_id: str, cfg: Dict) -> Optional[str]:
    for suffix, layer in cfg["module_suffixes"].items():
        if f"-{suffix}" in artifact_id or f"_{suffix}" in artifact_id or artifact_id.endswith(suffix):
            return layer
    return None


def _identify_business_domain(artifact_id: str, pom_rel_path: str, cfg: Dict) -> Optional[str]:
    parts = pom_rel_path.replace("\\", "/").split("/")
    all_suffixes = set(cfg["module_suffixes"].keys())
    exclude_dirs = {"src", "target", "build"}
    if len(parts) >= 2:
        candidate = parts[0]
        if candidate not in exclude_dirs and not any(
            candidate.endswith(f"-{s}") or candidate == s for s in all_suffixes
        ):
            return candidate
    for suffix in list(all_suffixes) + ["common"]:
        full = f"-{suffix}"
        if artifact_id.endswith(full):
            return artifact_id[:-len(full)]
    return None


# ── Maven pom 解析 ──────────────────────────────────────────────────────────

def _pom_tag(tag: str) -> str:
    return f"{{{MAVEN_NS}}}{tag}"


def _parse_artifact_id(pom_file: str) -> Optional[str]:
    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        artifact = root.find(_pom_tag("artifactId"))
        if artifact is not None and artifact.text:
            return artifact.text.strip()
        parent = root.find(_pom_tag("parent"))
        if parent is not None:
            artifact = parent.find(_pom_tag("artifactId"))
            if artifact is not None and artifact.text:
                return artifact.text.strip()
    except Exception as e:
        _debug(f"跳过 pom 解析 ({pom_file}): {e}")
    return None


def _parse_module_dependencies(pom_file: str) -> List[Tuple[str, str]]:
    deps = []
    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        for dep_elem in root.findall(f".//{_pom_tag('dependencies')}/{_pom_tag('dependency')}"):
            gid = dep_elem.find(_pom_tag("groupId"))
            aid = dep_elem.find(_pom_tag("artifactId"))
            if gid is not None and aid is not None and gid.text and aid.text:
                deps.append((aid.text.strip(), f"{gid.text.strip()}:{aid.text.strip()}"))
    except Exception as e:
        _debug(f"跳过 pom 依赖解析 ({pom_file}): {e}")
    return deps


def _collect_poms(project_root: str) -> List[str]:
    pom_files = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f == "pom.xml":
                pom_files.append(os.path.join(dirpath, f))
    return pom_files


# ── 模块内层推断（artifact-id 无层后缀时） ────────────────────────────────

def _infer_layer_from_packages(pom_file: str, layer_patterns: List[Tuple[str, re.Pattern]],
                               cfg: Dict) -> Optional[str]:
    module_dir = os.path.dirname(pom_file)
    src_java = os.path.join(module_dir, "src", "main", "java")
    if not os.path.isdir(src_java):
        return None

    found_layers: dict[str, int] = defaultdict(int)
    for dirpath, dirnames, _ in os.walk(src_java):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for d in dirnames:
            for name, _ in layer_patterns:
                if d == name:
                    found_layers[name] += 1

    if not found_layers:
        return None
    return max(found_layers, key=found_layers.get)


# ── Java 噪音剥离（注释/字符串/字符字面量，偏移保持） ──────────────────────

def _strip_java_noise(content: str) -> str:
    """剥离行注释/块注释/字符串/字符字面量的内容（偏移与行号保持不变）。

    被剥离字符替换为等长空格（换行保留），使 CLASS_PATTERN/_STATUS_WRITE_RE/
    import 提取不再命中注释与字符串字面量，且命中位置行号不变。逐字符状态机，
    处理转义（\\'、\\'' 等），不建 AST。
    """
    out: List[str] = []
    i, n = 0, len(content)
    _CODE, _LINE, _BLOCK, _STR, _CHAR = range(5)
    state = _CODE
    while i < n:
        c = content[i]
        nxt = content[i + 1] if i + 1 < n else ""
        if state == _CODE:
            if c == "/" and nxt == "/":
                out.append("  "); i += 2; state = _LINE
            elif c == "/" and nxt == "*":
                out.append("  "); i += 2; state = _BLOCK
            elif c == '"':
                out.append(" "); i += 1; state = _STR
            elif c == "'":
                out.append(" "); i += 1; state = _CHAR
            else:
                out.append(c); i += 1
        elif state == _LINE:
            out.append("\n" if c == "\n" else " ")
            if c == "\n":
                state = _CODE
            i += 1
        elif state == _BLOCK:
            if c == "*" and nxt == "/":
                out.append("  "); i += 2; state = _CODE
            else:
                out.append("\n" if c == "\n" else " "); i += 1
        elif state == _STR:
            if c == "\\":
                out.append(" ")
                if nxt:
                    out.append(" ")
                i += 2
            elif c == '"':
                out.append(" "); i += 1; state = _CODE
            else:
                out.append("\n" if c == "\n" else " "); i += 1
        else:  # _CHAR
            if c == "\\":
                out.append(" ")
                if nxt:
                    out.append(" ")
                i += 2
            elif c == "'":
                out.append(" "); i += 1; state = _CODE
            else:
                out.append("\n" if c == "\n" else " "); i += 1
    return "".join(out)


# ── import 提取（含行号） ──────────────────────────────────────────────────

# P0: 支持静态导入与通配导入（修复 ^import\s+([\w.]+) 捕获到 "static" 的漏报）：
# - import static x.y.Z.member → 宿主类 x.y.Z（静态成员的层归属跟随宿主类）
# - import static x.y.Z.*      → 宿主类 x.y.Z + ".*" 通配标记
# - import x.y.*               → x.y.*（通配标记，层归属降级为结构性债务）
IMPORT_PATTERN = re.compile(r"^import\s+(static\s+)?([\w.]+)", re.MULTILINE)


def extract_imports_with_lines(content: str) -> List[Tuple[str, int]]:
    """提取 (fqn, line)。通配导入以 ".*" 后缀标记；静态成员导入折算为宿主类 FQN。"""
    imports: List[Tuple[str, int]] = []
    for m in IMPORT_PATTERN.finditer(content):
        is_static = m.group(1) is not None
        fqn = m.group(2).rstrip(".")
        wildcard = m.end(2) < len(content) and content[m.end(2)] == "*"
        if wildcard:
            fqn += ".*"
        elif is_static and "." in fqn:
            fqn = fqn.rsplit(".", 1)[0]
        imports.append((fqn, content[:m.start()].count("\n") + 1))
    return imports


# ── suggestion 分流（按 callee 性质给不同修复方向） ───────────────────────

def _is_contract_object(imp_lower: str) -> bool:
    """判断 import 目标是否为契约对象（DTO/Command/Query）。

    单模块项目中这些类属于结构性债务——缺少独立 client 模块导致契约对象
    被其他层引用。不应与真正的层间逆向依赖混在一起报强制违规。
    """
    return any(kw in imp_lower for kw in (
        ".model.command.", ".model.dto.", ".model.query.",
        ".model.request.", ".model.response.",
        ".dto.", ".command.", ".query.", ".co.",
    ))


def _dep_direction_suggestion(source_layer: str, target_layer: str, imp: str) -> str:
    """根据被引用类的性质分流修复建议，避免误导（如对枚举建议"抽接口"）。"""
    imp_lower = imp.lower()

    # 契约对象（DTO/Command/Query）——单模块项目结构性债务
    if _is_contract_object(imp_lower):
        return (f"被引用的 {imp.split('.')[-1]} 是契约对象（Command/DTO/Query），"
                f"属于单模块结构性债务——应拆分为独立 client 模块后消除此依赖。"
                f"当前阶段不计入强制违规，但应列入拆分计划")

    # 业务数据型：异常、常量、枚举——不属于"服务依赖"范畴
    if any(kw in imp_lower for kw in (".exception.", ".exceptions.",
                                        ".constant.", ".constants.",
                                        ".enums.", ".enum.",
                                        ".errorcode", ".error_code",
                                        ".dict.", ".dictionary.")):
        return (f"被引用的 {imp.split('.')[-1]} 是业务数据型类（异常/常量/枚举），"
                f"应将其上移至 domain.shared 或拆分为独立模块，而非反向依赖")

    # 工具类 / 静态辅助方法
    if any(kw in imp_lower for kw in (".util.", ".utils.", ".helper.", ".helpers.")):
        return (f"被引用的 {imp.split('.')[-1]} 是工具类，应将其上移至 domain.shared.util，"
                f"或改为纯 JDK 实现（无第三方依赖）")

    # 领域服务类：编排应在 Application Executor
    if imp_lower.endswith("domainservice"):
        return f"编排应在 Application Executor 完成，{source_layer} 不直接依赖领域服务"

    # 默认：服务/组件类，建议反向依赖
    return f"反转依赖方向：{target_layer} 定义接口，{source_layer} 通过依赖注入使用"


def _domain_purity_suggestion(imp: str) -> str:
    """领域层纯净度违规的修复建议，按 import 性质分流。"""
    imp_lower = imp.lower()

    # MyBatis-Plus 注解类（@TableName、@TableField 等）——实体本身无法下沉
    if "com.baomidou.mybatisplus.annotation" in imp_lower:
        return ("MyBatis-Plus 实体注解（@TableName/@TableField）无法从领域实体移除。"
                "方案：(1) 改用 XML 映射，实体纯 POJO；(2) 接受此违规并在 baseline 中登记为已知例外")

    # Spring 事务注解
    if "transaction" in imp_lower and ("annotation" in imp_lower or "Transactional" in imp_lower):
        return ("@Transactional 属于 AOP 注解（不引入 Spring Bean 依赖），"
                "若团队接受领域层使用事务注解，请在 domain_annotation_imports 中添加此包")

    # 通用 Spring 工具
    if "org.springframework.util" in imp_lower or "org.springframework.beans" in imp_lower:
        return (f"引用 Spring 工具类 {imp}。"
                "若为纯工具方法（无 Bean 依赖），复制实现到 domain 或改用 JDK 等价写法")

    return "将框架相关逻辑下沉到 infrastructure 层，仓储实现通过依赖倒置接入"

def check_domain_purity(file_path: str, content: str, cfg: Dict) -> List[Issue]:
    issues = []
    forbidden = cfg["domain_forbidden_imports"]
    allowed = set(cfg["domain_allowed_imports"])
    annotations = set(cfg.get("domain_annotation_imports", []))

    prefix = cfg.get("project_package_prefix", "")

    for imp, line in extract_imports_with_lines(content):
        # P0: 内部包通配 import 无法定位目标类，不猜层——结构性债务由
        # check_dependency_direction 统一报告（所有层均执行该检查），
        # 此处跳过避免同一 import 双报
        if imp.endswith(".*") and _is_internal_import(imp, prefix):
            continue
        is_forbidden = any(imp.startswith(p) for p in forbidden)
        if not is_forbidden:
            continue
        if any(imp.startswith(p) for p in allowed):
            continue
        if any(imp.startswith(p) for p in annotations):
            continue
        issues.append(Issue(
            file=file_path, line=line, severity=Severity.MANDATORY,
            rule="领域层纯净度", rule_code=DOMAIN_PURITY,
            description=f"领域层禁止导入: {imp}",
            suggestion=_domain_purity_suggestion(imp),
        ))
    return issues


# ── 检查 2: 依赖方向（仅项目内部 import） ─────────────────────────────────

# 无 project_package_prefix 时用于排除第三方包（回退启发式）
_THIRD_PARTY_PREFIXES = (
    "java.", "javax.", "jakarta.", "org.springframework.", "org.mybatis.",
    "com.baomidou.", "org.hibernate.", "org.apache.", "com.fasterxml.",
    "com.google.", "lombok.", "org.slf4j.", "ch.qos.logback.", "io.swagger.",
    "io.github.", "cn.hutool.", "org.mapstruct.", "javax.annotation.",
    "org.junit.", "org.mockito.", "org.aspectj.", "net.bytebuddy.",
    "org.assertj.", "org.hamcrest.", "org.testng.",
    "org.springframework.boot.test", "org.springframework.test",
    "org.jetbrains.annotations", "javax.inject",
)


def _is_internal_import(imp: str, prefix: str) -> bool:
    if prefix:
        return imp.startswith(prefix)
    return not imp.startswith(_THIRD_PARTY_PREFIXES)


# Java import 层间依赖规则矩阵
# 含义：行（source_layer）的代码中 import 列（target_layer）的类，是否允许？
# 与 _MAVEN_DEP_MATRIX 的区别：本矩阵刻画 Java 文件级 import（同模块内），
# _MAVEN_DEP_MATRIX 刻画 Maven pom.xml 级依赖（跨模块）。
# 例如 client 层自身模块内可以互相 import (client→client=True)，
# 但跨模块时 client 不应依赖其他 client 模块 (client→client=False)。
_DEPENDENCY_RULES = {
    "adapter": {"client": True, "application": True, "domain": False, "infrastructure": False},
    "client": {"client": True, "application": False, "domain": False, "infrastructure": False},
    "application": {"domain": True, "infrastructure": True, "client": True, "adapter": False, "application": True},
    "domain": {"domain": True, "client": False, "adapter": False, "application": False, "infrastructure": False},
    "infrastructure": {"domain": True, "infrastructure": True, "adapter": False, "client": False, "application": False},
}

# Maven 模块依赖矩阵（pom.xml <dependency> 级，跨模块）
_MAVEN_DEP_MATRIX = {
    "adapter": {"client": True, "application": True, "domain": False, "infrastructure": False, "start": False},
    "start": {"adapter": True, "client": True, "application": True, "domain": True, "infrastructure": True, "start": False},
    "client": {"client": False, "application": False, "domain": False, "infrastructure": False, "adapter": False, "start": False},
    "application": {"domain": True, "infrastructure": True, "client": True, "adapter": False, "start": False, "application": False},
    "domain": {"domain": False, "application": False, "infrastructure": False, "client": False, "adapter": False, "start": False},
    "infrastructure": {"domain": True, "infrastructure": False, "client": False, "application": False, "adapter": False, "start": False},
}


def check_dependency_direction(file_path: str, source_layer: str, content: str,
                               layer_patterns: List, cfg: Dict) -> List[Issue]:
    """检查各层 Java import 逆向依赖（仅分析项目内部 import）。"""
    issues = []
    prefix = cfg.get("project_package_prefix", "")
    all_imports = extract_imports_with_lines(content)
    internal_imports = [(imp, line) for imp, line in all_imports
                        if _is_internal_import(imp, prefix)]

    for imp, line in internal_imports:
        # P0: 通配 import 无法定位目标类，不猜层，记结构性债务待 ArchUnit 复核
        if imp.endswith(".*"):
            issues.append(Issue(
                file=file_path, line=line, severity=Severity.STRUCTURAL_DEBT,
                rule="依赖方向", rule_code=DEP_DIRECTION,
                description=f"通配 import 无法定位目标类，待 ArchUnit 复核: import {imp}",
                suggestion="改为显式 import 目标类；或迁移 ArchUnit 后由字节码规则精确判定",
            ))
            continue
        imp_path = imp.replace(".", "/") + ".java"
        # P0-4: 复用 identify_layer 获得 alias 感知的 target 层识别
        target_layer = identify_layer(imp_path, layer_patterns, cfg)
        if target_layer is None or target_layer == source_layer:
            continue
        allowed = _DEPENDENCY_RULES.get(source_layer, {}).get(target_layer, True)
        if not allowed:
            # 契约对象（Command/DTO/Query）被跨层引用——单模块项目结构性债务，
            # 不是真正的服务依赖逆向。独立计数，不影响门禁。
            severity = Severity.STRUCTURAL_DEBT if _is_contract_object(imp.lower()) else Severity.MANDATORY
            description = (f"{source_layer} 层禁止依赖 {target_layer} 层: import {imp}"
                           if severity == Severity.MANDATORY else
                           f"[结构性债务] {source_layer} → {target_layer}: import {imp}"
                           f"（契约对象，缺少独立 client 模块）")
            issues.append(Issue(
                file=file_path, line=line, severity=severity,
                rule="依赖方向", rule_code=DEP_DIRECTION,
                description=description,
                suggestion=_dep_direction_suggestion(source_layer, target_layer, imp),
            ))
    return issues


# ── 检查 3: 命名后缀 ──────────────────────────────────────────────────────

CLASS_PATTERN = re.compile(r"(?:class|interface|enum|@interface)\s+(\w+)", re.MULTILINE)

# 后缀必须前接小写字母，避免误匹配
_SUFFIX_RULES = [
    # client 层契约对象（DTO/Command/Query 允许 client 或 adapter.web，见 02-naming §1）
    (re.compile(r"(?<=[a-z])Inter$"),          ("client",),                Severity.MANDATORY,   "Feign 接口应在 client 层"),
    (re.compile(r"(?<=[a-z])DTO$"),            ("client", "adapter"),      Severity.MANDATORY,   "DTO 应在 client 或 adapter 层"),
    (re.compile(r"(?<=[a-z])Command$"),        ("client", "adapter"),      Severity.RECOMMENDED, "Command 应在 client 或 adapter 层"),
    (re.compile(r"(?<=[a-z])Query$"),          ("client", "adapter"),      Severity.RECOMMENDED, "Query 应在 client 或 adapter 层"),
    # adapter 层
    (re.compile(r"(?<=[a-z])Controller$"),     ("adapter",),               Severity.MANDATORY,   "Controller 应在 adapter 层"),
    # application 层
    (re.compile(r"(?<=[a-z])AppService$"),     ("application",),           Severity.MANDATORY,   "应用服务应在 application 层"),
    (re.compile(r"(?<=[a-z])CmdExe$"),         ("application",),           Severity.MANDATORY,   "命令执行器应在 application 层"),
    (re.compile(r"(?<=[a-z])QryExe$"),         ("application",),           Severity.MANDATORY,   "查询执行器应在 application 层"),
    (re.compile(r"(?<=[a-z])Assembler$"),      ("application",),           Severity.RECOMMENDED, "装配器应在 application 层"),
    (re.compile(r"(?<=[a-z])Handler$"),        ("application",),           Severity.RECOMMENDED, "策略处理器应在 application 层"),
    (re.compile(r"(?<=[a-z])Manager$"),        ("application",),           Severity.RECOMMENDED, "流程编排应在 application 层"),
    # domain 层（实体/值对象无后缀，无法用后缀规则检查）
    (re.compile(r"(?<=[a-z])DomainService$"),  ("domain",),                Severity.MANDATORY,   "领域服务应在 domain 层"),
    (re.compile(r"(?<=[a-z])Repository$"),     ("domain",),                Severity.MANDATORY,   "仓储接口应在 domain 层"),
    (re.compile(r"(?<=[a-z])ExtPt$"),          ("domain",),                Severity.MANDATORY,   "扩展点接口应在 domain 层"),
    # infrastructure 层
    (re.compile(r"(?<=[a-z])RepositoryImpl$"), ("infrastructure",),        Severity.MANDATORY,   "仓储实现应在 infrastructure 层"),
    (re.compile(r"(?<=[a-z])Mapper$"),         ("infrastructure",),        Severity.MANDATORY,   "Mapper 应在 infrastructure 层"),
    (re.compile(r"(?<=[a-z])Converter$"),      ("infrastructure",),        Severity.RECOMMENDED, "PO 转换器应在 infrastructure 层"),
    (re.compile(r"(?<=[a-z])PO$"),             ("infrastructure",),        Severity.MANDATORY,   "持久化对象应在 infrastructure 层"),
    (re.compile(r"(?<=[a-z])Ext$"),            ("infrastructure",),        Severity.RECOMMENDED, "扩展点实现应在 infrastructure 层"),
    (re.compile(r"(?<=[a-z])Constant$"),       ("infrastructure",),        Severity.RECOMMENDED, "常量类应在 infrastructure 层"),
    (re.compile(r"(?<=[a-z])Exception$"),      ("infrastructure",),        Severity.RECOMMENDED, "异常类应在 infrastructure 层"),
    # 枚举按语义分层（02-naming §1）：领域状态枚举（*StatusEnum/*StateEnum，被 DomainService 引用）→ domain；
    # 技术分类枚举 → infrastructure。后者用 lookbehind 排除 Status/State，避免与状态枚举规则重叠。
    (re.compile(r"(?<=[a-z])(?:Status|State)Enum$"),       ("domain",),         Severity.MANDATORY,   "领域状态枚举应在 domain 层（放 infrastructure 会导致 domain 逆向依赖）"),
    (re.compile(r"(?<=[a-z])(?<!Status)(?<!State)Enum$"),  ("infrastructure",), Severity.RECOMMENDED, "技术分类枚举应在 infrastructure 层"),
]

_NAMING_EXCLUDE_STARTSWITH = (
    "Hibernate", "Abstract", "Base", "Simple", "Default", "Generic",
)


def check_naming(file_path: str, source_layer: str, content: str,
                 cfg: Dict) -> List[Issue]:
    issues = []
    for m in CLASS_PATTERN.finditer(content):
        class_name = m.group(1)

        if class_name.startswith(_NAMING_EXCLUDE_STARTSWITH):
            continue
        if len(class_name) <= 2:
            continue

        for suffix_re, expected_layers, severity, desc in _SUFFIX_RULES:
            if suffix_re.search(class_name):
                if source_layer not in expected_layers:
                    line = content[:m.start()].count("\n") + 1
                    allowed = "或".join(expected_layers)
                    issues.append(Issue(
                        file=file_path, line=line, severity=severity,
                        rule="命名规范", rule_code=NAMING,
                        description=f"{class_name}: {desc}，当前位置在 {source_layer} 层",
                        suggestion=f"将 {class_name} 移动到 {allowed} 层对应包",
                    ))
    return issues


# ── 检查 4: Adapter 隔离（仅项目内部 import） ─────────────────────────────

def check_adapter_isolation(file_path: str, content: str,
                            layer_patterns: List, cfg: Dict) -> List[Issue]:
    issues = []
    prefix = cfg.get("project_package_prefix", "")
    all_imports = extract_imports_with_lines(content)
    internal = [(imp, line) for imp, line in all_imports
                if _is_internal_import(imp, prefix)]

    for imp, line in internal:
        imp_path = imp.replace(".", "/") + ".java"
        if "/domain/" in imp_path and ("/entity/" in imp_path or "/valueobject/" in imp_path):
            issues.append(Issue(
                file=file_path, line=line, severity=Severity.MANDATORY,
                rule="Adapter 隔离", rule_code=ADAPTER_ISOLATION,
                description=f"Adapter 禁止直接引用领域对象: {imp}",
                suggestion="通过 Application Executor + Assembler 返回 DTO，禁止 domain 对象泄漏到 Adapter",
            ))
    return issues


# ── 检查: 状态泄漏与状态机治理 ────────────────────────────────────────────

# 状态改写方法名模式（Tier 1 正则与 ArchUnit 生成器共用，单一源）
_STATUS_WRITE_NAME_RE = r"(?:set|change|update|modify)\w*(?:Status|State)"
_STATUS_WRITE_RE = re.compile(r"\b" + _STATUS_WRITE_NAME_RE + r"\s*\(")
# 状态枚举命名（形态 A 锚点）
_STATUS_ENUM_RE = re.compile(r"\benum\s+\w*(?:Status|State)\b")


def check_state_field_leakage(file_path: str, source_layer: str, content: str,
                              cfg: Dict) -> List[Issue]:
    """检测 adapter/infrastructure 层直接改写领域状态（状态泄漏）。

    状态流转应经 Application 编排、Domain 封装；Adapter/Infra 只传递事件。
    启发式：adapter/infrastructure 层出现 set/change/update/modify...Status/State() 调用。
    adapter 层强制，infrastructure 层推荐（DO 转换等场景可能合理）。
    """
    if source_layer not in ("adapter", "infrastructure"):
        return []
    severity = Severity.MANDATORY if source_layer == "adapter" else Severity.RECOMMENDED
    issues: List[Issue] = []
    for m in _STATUS_WRITE_RE.finditer(content):
        line = content[:m.start()].count("\n") + 1
        call = m.group(0).rstrip("(")
        issues.append(Issue(
            file=file_path, line=line, severity=severity,
            rule="状态泄漏", rule_code=STATE_FIELD_LEAKAGE,
            description=f"{source_layer} 层直接改写状态: {call}()（状态流转应收敛在 Domain 层）",
            suggestion="通过 Application Executor 调用 Domain 服务/聚合方法触发状态流转，Adapter 只传递事件",
        ))
    return issues


def check_state_machine_governance(project_root: str, java_files: List[str],
                                   cfg: Dict) -> List[Issue]:
    """全局：检测状态枚举但未引入状态机框架/统一管理（启发式）。

    形态 A 状态枚举若散落 switch/if 管理，流转规则难以审计。
    有状态枚举 + 无任何状态机框架 import → 推荐级提醒。
    """
    sm_imports = cfg.get("state_machine_imports", [])
    has_framework = False
    status_enums: List[Tuple[str, str]] = []
    for jf in java_files:
        try:
            with open(jf, "r", encoding="utf-8") as fp:
                content = fp.read()
        except Exception:
            continue
        if any(imp in content for imp in sm_imports):
            has_framework = True
        rel = os.path.relpath(jf, project_root)
        for m in _STATUS_ENUM_RE.finditer(content):
            status_enums.append((rel, m.group(0).split()[-1]))

    if has_framework or not status_enums:
        return []

    seen_enum: set = set()
    issues: List[Issue] = []
    for rel, enum_name in status_enums:
        if enum_name in seen_enum:
            continue
        seen_enum.add(enum_name)
        issues.append(Issue(
            file=rel, line=0, severity=Severity.RECOMMENDED,
            rule="状态机治理", rule_code=STATE_MACHINE,
            description=f"识别到状态枚举 {enum_name} 但未引入状态机框架，状态流转可能散落于 switch/if",
            suggestion="引入 Cola Statemachine，或在 Domain 服务集中封装流转规则（参见 steering/gtsp/01-project-structure.md 状态机章节）",
        ))
    return issues


# ── 检查 5+6: Maven 模块依赖（同域层矩阵 + 跨域检查，单次扫描） ──────────

def check_maven_modules(project_root: str, pom_files: List[str],
                        cfg: Dict) -> List[Issue]:
    issues = []
    layer_patterns = _build_layer_patterns(cfg)

    module_info: Dict[str, Tuple[str, str, str]] = {}
    for pom in pom_files:
        aid = _parse_artifact_id(pom)
        if aid is None:
            continue
        rel = os.path.relpath(pom, project_root)
        layer = _identify_module_layer(aid, cfg)
        if layer is None:
            layer = _infer_layer_from_packages(pom, layer_patterns, cfg)
        bd = _identify_business_domain(aid, rel, cfg)
        if layer is not None:
            module_info[aid] = (bd or "", layer, rel)

    all_domains = {bd for bd, _, _ in module_info.values() if bd}
    multi_domain = len(all_domains) >= 2

    # 单模块场景：仅靠包约定软隔离，缺少 Maven 编译期物理屏障
    if len(module_info) <= 1 and pom_files:
        _warn("单模块项目缺少 Maven 编译期隔离——分层依赖仅靠包约定约束。"
              "强烈建议拆分为多模块项目（adapter/client/app/domain/infrastructure）以获得编译期物理屏障。")

    for pom in pom_files:
        source_aid = _parse_artifact_id(pom)
        if source_aid is None or source_aid not in module_info:
            continue
        src_domain, source_layer, rel_pom = module_info[source_aid]
        deps = _parse_module_dependencies(pom)

        for dep_aid, dep_coord in deps:
            if dep_aid not in module_info:
                continue
            tgt_domain, target_layer, _ = module_info[dep_aid]

            if tgt_domain == src_domain:
                if target_layer == source_layer:
                    continue
                allowed = _MAVEN_DEP_MATRIX.get(source_layer, {}).get(target_layer, True)
                if not allowed:
                    issues.append(Issue(
                        file=rel_pom, line=0, severity=Severity.MANDATORY,
                        rule="Maven 模块依赖", rule_code=MAVEN_MODULE_DEP,
                        description=f"{source_aid} ({source_layer} 层) 禁止依赖 {dep_aid} ({target_layer} 层)",
                        suggestion=f"移除 {rel_pom} 中 <dependency><artifactId>{dep_aid}</artifactId>",
                    ))
                continue

            if multi_domain and tgt_domain:
                if target_layer != "client":
                    issues.append(Issue(
                        file=rel_pom, line=0, severity=Severity.MANDATORY,
                        rule="跨域依赖", rule_code=CROSS_DOMAIN_DEP,
                        description=f"跨域依赖仅允许通过 -client: {source_aid} ({src_domain} 域) → {dep_aid} ({tgt_domain} 域的 {target_layer} 层)",
                        suggestion=f"改为引入 {tgt_domain}-client，或通过领域事件/MQ 异步解耦",
                    ))

        if source_layer == "domain":
            for dep_aid, dep_coord in deps:
                for forbidden in cfg["domain_forbidden_pom"]:
                    if dep_coord.startswith(forbidden):
                        issues.append(Issue(
                            file=rel_pom, line=0, severity=Severity.MANDATORY,
                            rule="领域层纯净度(POM)", rule_code=DOMAIN_PURITY_POM,
                            description=f"domain 模块禁止依赖框架: {dep_coord}",
                            suggestion="domain 模块只能依赖 JDK + JPA 注解（jakarta.persistence），移除该依赖",
                        ))
    return issues


# ── Java 文件收集与检查调度 ───────────────────────────────────────────────

def check_file(file_path: str, project_root: str,
               layer_patterns: List, cfg: Dict) -> Tuple[List[Issue], bool, Optional[str]]:
    """返回 (issues, classified, layer)。

    classified=False 表示该文件未被任何层识别（不属于分层模块）。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as fp:
            content = fp.read()
    except Exception as e:
        _debug(f"跳过文件读取 ({file_path}): {e}")
        return [], False, None

    # P0: 统一剥离注释/字符串/字符字面量内容（偏移保持，行号不变），
    # 抑制 CLASS_PATTERN/_STATUS_WRITE_RE/import 提取对注释与字符串的误报
    content = _strip_java_noise(content)
    rel_path = os.path.relpath(file_path, project_root)
    layer = identify_layer(rel_path, layer_patterns, cfg)
    if layer is None:
        return [], False, None

    issues = []
    # layer 识别一次，传递给各检查函数，避免重复调用 identify_layer
    issues.extend(check_domain_purity(rel_path, content, cfg) if layer == "domain" else [])
    issues.extend(check_dependency_direction(rel_path, layer, content, layer_patterns, cfg))
    issues.extend(check_naming(rel_path, layer, content, cfg))
    issues.extend(check_adapter_isolation(rel_path, content, layer_patterns, cfg) if layer == "adapter" else [])
    issues.extend(check_state_field_leakage(rel_path, layer, content, cfg) if layer in ("adapter", "infrastructure") else [])
    return issues, True, layer


def collect_java_files(project_root: str) -> List[str]:
    java_files = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            if f.endswith(".java"):
                java_files.append(os.path.join(dirpath, f))
    return java_files


# ── 基线机制 ────────────────────────────────────────────────────────────────

def _issue_fingerprint(issue: Issue) -> str:
    """生成违规指纹：sha1(file + rule_code + description) 前 12 位。

    不含 line 号（行号随代码格式化位移），不含 severity（同一违规不因级别变化而变）。
    rule_code 保证指纹跨规则版本稳定（中文 rule 可能被优化表述而变）。
    """
    raw = f"{issue.file}:{issue.rule_code}:{issue.description}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def load_baseline(baseline_path: str) -> set[str]:
    """加载基线文件（.json 数组），返回指纹集合。"""
    if not os.path.isfile(baseline_path):
        return set()
    try:
        with open(baseline_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return set(data.get("fingerprints", []))
    except Exception:
        return set()

def baseline_state(baseline_path: str) -> Tuple[str, set]:
    """探测基线文件状态，供 --frozen 区分处置：

    ("missing", set())  文件不存在 —— CI 拒绝（fail-fast，防误建吞违规）
    ("corrupt", set())  文件存在但 JSON 损坏/结构非法 —— CI 拒绝（fail-closed）
    ("empty",  set())   合法基线但零指纹 —— 债务已还清，正常放行
    ("ok",     fps)     常规基线
    """
    if not os.path.isfile(baseline_path):
        return "missing", set()
    try:
        with open(baseline_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, dict) or not isinstance(
                data.get("fingerprints", []), list):
            return "corrupt", set()
        fps = set(data.get("fingerprints", []))
    except Exception:
        return "corrupt", set()
    return ("empty", set()) if not fps else ("ok", fps)


def save_baseline(baseline_path: str, issues: List[Issue]):
    _write_baseline(baseline_path, {_issue_fingerprint(i) for i in issues})


def _write_baseline(baseline_path: str, fingerprints: set[str]):
    """按指纹集合写基线文件（结构 version/created/total_issues/fingerprints）。"""
    ordered = sorted(fingerprints)
    with open(baseline_path, "w", encoding="utf-8") as fp:
        json.dump({
            "version": 1,
            "created": _now_iso(),
            "total_issues": len(ordered),
            "fingerprints": ordered,
        }, fp, ensure_ascii=False, indent=2)


def shrink_baseline(baseline_path: str, baseline_fps: set[str],
                    current_fps: set[str]) -> int:
    """ratchet 收缩：本次未再现的基线指纹视为已偿还，剔除并写回基线文件。

    对齐 ArchUnit FreezingArchRule（allowStoreUpdate=true）：只缩不涨——
    新增违规由调用方照常上报，不进入基线。
    返回收缩掉的指纹数（0 表示基线无变化，不写文件）。
    """
    retained = baseline_fps & current_fps
    if retained == baseline_fps:
        return 0
    _write_baseline(baseline_path, retained)
    return len(baseline_fps) - len(retained)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def filter_by_baseline(issues: List[Issue], baseline_fingerprints: Optional[set] = None) -> Tuple[List[Issue], int]:
    """过滤掉基线中已存在的存量违规，仅返回新增违规。

    ratchet 双向对账的"报新增"半边；"收缩写回"半边由调用方接 shrink_baseline 完成。
    """
    new_issues = []
    suppressed = 0
    for issue in issues:
        fp = _issue_fingerprint(issue)
        if fp in baseline_fingerprints:
            suppressed += 1
            _debug(f"基线抑制: {issue.file}: {issue.description[:60]}")
        else:
            new_issues.append(issue)
    return new_issues, suppressed


# ── 主入口 ──────────────────────────────────────────────────────────────────

def run(project_root: str, strict: bool = False, config_path: Optional[str] = None,
        baseline_path: Optional[str] = None, warn_unclassified: bool = False
        ) -> Tuple[List[Issue], int, int, Dict]:
    """返回 (issues, mandatory_count, recommended_count, stats)。"""
    global _warnings, _debug_enabled
    _warnings = []

    cfg = load_config(project_root, config_path)
    layer_patterns = _build_layer_patterns(cfg)

    if not cfg.get("project_package_prefix", ""):
        _warn("未配置 project_package_prefix，依赖方向检查使用回退启发式过滤第三方包。"
              "建议在 .arch-guard.json 中配置以消除误报风险。")

    java_files = collect_java_files(project_root)
    all_issues: list[Issue] = []
    classified_count = 0
    unclassified_count = 0

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(check_file, f, project_root, layer_patterns, cfg): f
                   for f in java_files}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                file_issues, classified, _ = result
                all_issues.extend(file_issues)
                if classified:
                    classified_count += 1
                else:
                    unclassified_count += 1

    pom_files = _collect_poms(project_root)
    all_issues.extend(check_maven_modules(project_root, pom_files, cfg))
    all_issues.extend(check_state_machine_governance(project_root, java_files, cfg))

    if strict:
        for issue in all_issues:
            if issue.severity == Severity.RECOMMENDED:
                issue.severity = Severity.MANDATORY

    # 基线过滤（ratchet：只缩不涨）
    suppressed_count = 0
    retired_count = 0
    if baseline_path:
        baseline_fps = load_baseline(baseline_path)
        if baseline_fps:
            current_fps = {_issue_fingerprint(i) for i in all_issues}
            all_issues, suppressed_count = filter_by_baseline(all_issues, baseline_fps)
            # 检查成功完成后收缩写回：本次未再现的存量视为已偿还
            retired_count = shrink_baseline(baseline_path, baseline_fps, current_fps)

    # 去重（含 severity：同一位置强制+推荐并存时保留两者）
    seen = set()
    deduped: list[Issue] = []
    for i in all_issues:
        key = (i.file, i.line, i.rule_code, i.description, i.severity)
        if key not in seen:
            seen.add(key)
            deduped.append(i)

    mandatory_count = sum(1 for i in deduped if i.severity == Severity.MANDATORY)
    recommended_count = sum(1 for i in deduped if not strict and i.severity == Severity.RECOMMENDED)
    structural_debt_count = sum(1 for i in deduped if i.severity == Severity.STRUCTURAL_DEBT)

    commit_sha, dirty = _commit_binding(project_root)
    stats = {
        "java_files_total": len(java_files),
        "java_files_classified": classified_count,
        "java_files_unclassified": unclassified_count,
        "pom_files_total": len(pom_files),
        "baseline_suppressed": suppressed_count,
        "baseline_retired": retired_count,
        "structural_debt_count": structural_debt_count,
        "warnings": list(_warnings),
        # §4 内容绑定：收据结论钉在项目 git 提交切面上（stale/dirty 即无权威性）
        "project_root": project_root,
        "commit_sha": commit_sha,
        "dirty": dirty,
    }

    return deduped, mandatory_count, recommended_count, stats


# ── 输出 ──────────────────────────────────────────────────────────────────

def format_text(issues: List[Issue], mandatory_count: int, recommended_count: int,
                stats: Optional[Dict] = None) -> str:
    structural_debt_count = stats.get("structural_debt_count", 0) if stats else 0

    if not issues and not (stats and stats.get("warnings")):
        return "\n".join(["✅ 所有架构分层检查通过"] + _boundary_footer(stats))

    lines = []

    # 统计摘要
    if stats:
        lines.append("## 统计\n")
        lines.append(f"  检查 Java 文件: {stats['java_files_total']}"
                     f"（识别分层: {stats['java_files_classified']}，"
                     f"跳过: {stats['java_files_unclassified']}）")
        lines.append(f"  检查 pom.xml: {stats['pom_files_total']}")
        if stats.get("baseline_suppressed"):
            lines.append(f"  基线抑制存量违规: {stats['baseline_suppressed']}")
        if stats.get("baseline_retired"):
            lines.append(f"  基线自动收缩: 已偿还 {stats['baseline_retired']} 条存量（已写回基线文件）")
        if structural_debt_count:
            lines.append(f"  📋 结构性债务: {structural_debt_count}（已知架构约束，不计入门禁）")
        if stats.get("warnings"):
            for w in stats["warnings"]:
                lines.append(f"  ⚠️  {w}")
        lines.append("")

    if not issues:
        lines.append("✅ 无新增违规")
        lines.extend(_boundary_footer(stats))
        return "\n".join(lines)

    lines.append(f"发现 {mandatory_count} 个强制问题，{recommended_count} 个推荐问题")
    if structural_debt_count:
        lines.append(f"     （另有 {structural_debt_count} 个结构性债务，不计入门禁）")
    lines.append("")

    # 按规则分组统计
    by_rule: Dict[str, List[Issue]] = defaultdict(list)
    for i in issues:
        by_rule[i.rule].append(i)

    lines.append("## 摘要\n")
    for rule, items in sorted(by_rule.items()):
        m = sum(1 for x in items if x.severity == Severity.MANDATORY)
        r = sum(1 for x in items if x.severity == Severity.RECOMMENDED)
        s = sum(1 for x in items if x.severity == Severity.STRUCTURAL_DEBT)
        parts = []
        if m: parts.append(f"{m} 强制")
        if r: parts.append(f"{r} 推荐")
        if s: parts.append(f"{s} 结构债务")
        lines.append(f"  [{rule}] {'，'.join(parts)}")

    lines.append("\n## 明细\n")
    for issue in sorted(issues, key=lambda x: (
        (0 if x.severity == Severity.MANDATORY else 1 if x.severity == Severity.RECOMMENDED else 2),
        x.file, x.line)):
        if issue.severity == Severity.STRUCTURAL_DEBT:
            prefix = "📋"
        elif issue.severity == Severity.MANDATORY:
            prefix = "🔴"
        else:
            prefix = "🟡"
        loc = f":{issue.line}" if issue.line else ""
        lines.append(f"{prefix} [{issue.rule}] {issue.file}{loc}")
        lines.append(f"   {issue.description}")
        if issue.suggestion:
            lines.append(f"   → {issue.suggestion}")
        lines.append("")
    lines.extend(_boundary_footer(stats))
    return "\n".join(lines)


# ── 收据信封（docs/design/guard-receipt-spec.md）────────────────────────────

# Tier 1 结构性无法覆盖 / 需人工判断的范围（对齐 SKILL.md「仍需人工」表）
_TIER1_NOT_ANALYZED = [
    "tier2_method_level_dependency",        # 层间依赖方向需知识图谱（--mode graph）
    "aggregate_design",                     # 聚合设计合理性（大小、边界）
    "value_object_immutability",            # 值对象不可变（setter 检查）
    "application_service_business_logic",   # 应用服务是否包含业务逻辑
    "cross_domain_event_decoupling",        # 跨域通信应偏事件解耦
]


def _commit_binding(project_root: str) -> Tuple[Optional[str], Optional[bool]]:
    """项目 git 提交切面（guard-receipt-spec §4）：

    返回 (commit_sha, dirty)：HEAD 的 40 位原生 sha 与工作区相对 HEAD 是否有差异
    （含未跟踪文件——Tier1 按文件系统扫描，未跟踪文件同样进入分析）。
    非 git 仓库 / git 不可用 → (None, None)，消费方按 fail-closed 视为无权威性。
    """
    try:
        sha = subprocess.run(["git", "-C", project_root, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        if sha.returncode != 0:
            return None, None
        st = subprocess.run(["git", "-C", project_root, "status", "--porcelain"],
                            capture_output=True, text=True, timeout=10)
        return sha.stdout.strip() or None, bool(st.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return None, None


def _build_receipt(issues: List[Issue], mandatory_count: int,
                   stats: Optional[Dict] = None,
                   baseline_path: Optional[str] = None) -> Dict:
    """收据信封：decision / provenance / boundary / verified（§4 内容绑定）。"""
    s = stats or {}
    reason_codes = sorted({i.rule_code for i in issues
                           if i.severity == Severity.MANDATORY and i.rule_code})
    degraded = ["tier1_file_level_heuristic"]
    if s.get("java_files_unclassified", 0):
        degraded.append("unclassified_java_files")
    verified = [{"check_id": "tier1_scan",
                 "subject": s.get("project_root", "."),
                 "commit_sha": s.get("commit_sha"),
                 "dirty": s.get("dirty")}]
    return {
        "tool": "arch-guard",
        "schema_version": 1,
        "decision": {"gate": "block" if mandatory_count else "pass",
                     "reason_codes": reason_codes},
        "verified": verified,
        "provenance": {
            "tier": 1,
            "java_files": s.get("java_files_total", 0),
            "java_files_classified": s.get("java_files_classified", 0),
            "java_files_unclassified": s.get("java_files_unclassified", 0),
            "pom_files": s.get("pom_files_total", 0),
            "baseline": baseline_path,
            "baseline_suppressed": s.get("baseline_suppressed", 0),
            "baseline_retired": s.get("baseline_retired", 0),
        },
        "boundary": {"degraded": degraded,
                     "not_analyzed": list(_TIER1_NOT_ANALYZED)},
    }


def _boundary_footer(stats: Optional[Dict] = None) -> List[str]:
    """收据信封 boundary 的人读投影（format_text 末尾段）。"""
    s = stats or {}
    lines = ["── 证据边界 ──"]
    lines.append("  检查精度: Tier 1 文件级启发式（字符串匹配）；"
                 "层间依赖方向需 Tier 2 知识图谱（--mode graph）")
    lines.append("  未覆盖: 聚合设计、值对象不可变、应用服务业务逻辑、"
                 "跨域事件解耦（人工判断）")
    if s.get("baseline_suppressed"):
        lines.append(f"  基线抑制: {s['baseline_suppressed']} 条存量违规未列出"
                     f"（ratchet 只缩不涨）")
    return lines


def format_json(issues: List[Issue], mandatory_count: int, recommended_count: int,
                strict: bool = False, stats: Optional[Dict] = None,
                baseline_path: Optional[str] = None) -> str:
    # 根因聚类：提取 callee 的包前缀，归类同源违规
    callee_clusters: Dict[str, int] = defaultdict(int)
    _CALLEE_RE = re.compile(r"(:?import|[→]\s*)\s*([\w.]+)")
    for i in issues:
        m = _CALLEE_RE.search(i.description)
        if m:
            callee_full = m.group(2)
            # 去掉项目包前缀和末段类名，保留中间包路径作为 cluster key
            parts = callee_full.split(".")
            if len(parts) >= 4:
                callee_clusters[".".join(parts[1:-1])] += 1
            else:
                callee_clusters[callee_full] += 1

    summary = {
        "by_rule": {},
        "by_callee_root": [{"package": pkg, "count": cnt}
                          for pkg, cnt in
                          sorted(callee_clusters.items(), key=lambda x: -x[1])],
    }
    for i in issues:
        summary["by_rule"].setdefault(i.rule, 0)
        summary["by_rule"][i.rule] += 1

    result = {
        "passed": mandatory_count == 0,
        "mandatory_count": mandatory_count,
        "recommended_count": recommended_count,
        "structural_debt_count": (stats or {}).get("structural_debt_count", 0),
        "strict": strict,
        "receipt": _build_receipt(issues, mandatory_count, stats, baseline_path),
        "summary": summary,
        "stats": stats or {},
        "issues": [
            {
                "file": i.file, "line": i.line,
                "severity": i.severity.value, "rule": i.rule,
                "rule_code": i.rule_code,
                "description": i.description, "suggestion": i.suggestion,
            }
            for i in issues
        ],
    }
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── CLI ────────────────────────────────────────────────────────────────────

def print_graph_mode(config_path: Optional[str] = None):
    """输出 Tier 2 Cypher 查询清单，根据配置文件动态生成。

    先尝试加载配置以获得 layer_aliases/layer_paths，若失败则使用默认值。
    """
    try:
        cfg = load_config(".", config_path)
    except Exception:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))

    # 收集所有层的路径变体（含别名）
    # 例如 layer_paths["adapter"]=["/adapter/"] + layer_aliases["interfaces"]="adapter"
    # → adapter 层的匹配模式为 [".adapter.", ".interfaces."]
    layer_patterns: Dict[str, List[str]] = {}
    for name, paths in cfg["layer_paths"].items():
        layer_patterns[name] = [p.strip("/") for p in paths]
    for alias, target in cfg["layer_aliases"].items():
        if target not in layer_patterns:
            layer_patterns[target] = []
        if alias not in layer_patterns[target]:
            layer_patterns[target].append(alias)

    def _layer_condition(layer_name: str, var: str) -> str:
        """生成 Cypher CONTAINS 条件，覆盖该层的所有路径变体。"""
        variants = layer_patterns.get(layer_name, [layer_name])
        conditions = [f"{var}.qualified_name CONTAINS '.{v}.'" for v in variants]
        return " OR ".join(conditions) if len(conditions) <= 1 else f"({' OR '.join(conditions)})"

    def _layer_case(layer_name: str, var: str) -> str:
        """生成 CASE WHEN 子句中的一个分支。"""
        variants = layer_patterns.get(layer_name, [layer_name])
        # 首个条件用 WHEN，其余用 OR 同层
        conds = " OR ".join([f"{var}.qualified_name CONTAINS '.{v}.'" for v in variants])
        return f"WHEN {conds} THEN '{layer_name}'"

    adapter_cond = _layer_condition("adapter", "f")
    domain_cond = _layer_condition("domain", "f")
    infra_cond = _layer_condition("infrastructure", "f")
    app_cond = _layer_condition("application", "f")
    client_cond = _layer_condition("client", "f")

    domain_d = _layer_condition("domain", "d")
    infra_d = _layer_condition("infrastructure", "d")
    app_d = _layer_condition("application", "d")
    adapter_d = _layer_condition("adapter", "d")
    client_d = _layer_condition("client", "d")

    adapter_case_f = _layer_case("adapter", "f")
    domain_case_f = _layer_case("domain", "f")
    infra_case_f = _layer_case("infrastructure", "f")
    app_case_f = _layer_case("application", "f")
    client_case_f = _layer_case("client", "f")

    adapter_case_d = _layer_case("adapter", "d")
    domain_case_d = _layer_case("domain", "d")
    infra_case_d = _layer_case("infrastructure", "d")
    app_case_d = _layer_case("application", "d")
    client_case_d = _layer_case("client", "d")

    print(f"""## Tier 2: 知识图谱深度审查 — Cypher 查询清单

以下查询通过 codebase-memory-mcp 的 query_graph 工具执行。前提：项目已建立索引。

> ⚠️ IMPORTS 边的端点通常为 File 节点（qualified_name 以 __file__ 结尾），
> 切勿在 MATCH 中限定 :Function 标签——使用无标签变量 (f)。

### 1. Domain → Infrastructure（禁止）

MATCH (f)-[:IMPORTS]->(d)
WHERE {domain_cond}
  AND {infra_d}
RETURN f.qualified_name AS domain_caller, d.qualified_name AS infra_callee
ORDER BY domain_caller

### 2. Domain → Application（禁止）

MATCH (f)-[:IMPORTS]->(d)
WHERE {domain_cond}
  AND {app_d}
RETURN f.qualified_name, d.qualified_name ORDER BY f.qualified_name

### 3. Adapter → Domain Entity（禁止）

MATCH (f)-[:IMPORTS]->(d)
WHERE {adapter_cond}
  AND {domain_d}
RETURN f.qualified_name AS adapter_caller, d.qualified_name AS domain_entity_ref
ORDER BY adapter_caller

### 4. Infrastructure → Application（禁止）

MATCH (f)-[:IMPORTS]->(d)
WHERE {infra_cond}
  AND {app_d}
RETURN f.qualified_name, d.qualified_name ORDER BY f.qualified_name

### 5. Application → Adapter（禁止）

MATCH (f)-[:IMPORTS]->(d)
WHERE {app_cond}
  AND {adapter_d}
RETURN f.qualified_name, d.qualified_name ORDER BY f.qualified_name

### 6. 跨层违规汇总（矩阵过滤）

MATCH (f)-[:IMPORTS]->(d)
WITH f, d,
     CASE {adapter_case_f} {domain_case_f} {app_case_f} {infra_case_f} {client_case_f} ELSE 'other' END AS src_layer,
     CASE {adapter_case_d} {domain_case_d} {app_case_d} {infra_case_d} {client_case_d} ELSE 'other' END AS tgt_layer
WHERE src_layer <> 'other' AND tgt_layer <> 'other'
WITH f, d, src_layer, tgt_layer
WHERE NOT (
  (src_layer = 'adapter' AND tgt_layer IN ['client', 'application']) OR
  (src_layer = 'application' AND tgt_layer IN ['domain', 'infrastructure', 'client']) OR
  (src_layer = 'domain' AND tgt_layer IN ['domain']) OR
  (src_layer = 'infrastructure' AND tgt_layer IN ['domain', 'infrastructure'])
)
RETURN src_layer, tgt_layer, f.qualified_name AS caller, d.qualified_name AS callee
ORDER BY src_layer, tgt_layer, caller

### 7. 状态泄漏（Adapter/Infrastructure → 状态枚举，需人工确认）

> 状态枚举的深度质量分析（死状态/不可达/缺失流转）由 doc-gen 的 StateMachineScanner 负责；
> 此查询聚焦架构层面：adapter/infrastructure 是否直接依赖状态枚举。

MATCH (f)-[:IMPORTS]->(d)
WHERE ({adapter_cond} OR {infra_cond})
  AND d.qualified_name =~ '(?i).*\\.(Status|State)$'
RETURN f.qualified_name AS caller, d.qualified_name AS status_enum
ORDER BY caller

---
> 层路径识别基于配置文件：{json.dumps(cfg.get("layer_aliases", {}), ensure_ascii=False)}（可通过 .arch-guard.json 覆盖）
> 知识图谱天然不索引第三方包，无需额外过滤。
""")


# ── ArchUnit 生成器（--mode archunit，Phase 2b） ────────────────────────────
#
# 规则唯一源：.arch-guard.json 配置 + 本文件内置矩阵（_DEPENDENCY_RULES /
# _SUFFIX_RULES / domain_forbidden_imports / _STATUS_WRITE_NAME_RE）。
# 生成物为 Java 8 兼容源码（gtsp-parent -source 8 约束，禁 var/匿名类钻石）。
# 设计：docs/design/arch-guard-evolution-design.md Phase 2b。

ARCHUNIT_VERSION = "1.2.1"
ARCHUNIT_JUNIT5_VERSION = "5.10.2"

# ArchUnit 层序（生成顺序稳定，verify diff 才有意义）
_ARCH_LAYER_ORDER = ["adapter", "client", "application", "domain", "infrastructure"]


def _archunit_layer_packages(cfg: Dict) -> Dict[str, List[str]]:
    """层名 → 包路径变体（canonical + alias），与 Tier 2 图查询同源。"""
    layer_patterns: Dict[str, List[str]] = {}
    for name, paths in cfg["layer_paths"].items():
        layer_patterns[name] = [p.strip("/") for p in paths]
    for alias, target in cfg["layer_aliases"].items():
        if target not in layer_patterns:
            layer_patterns[target] = []
        if alias not in layer_patterns[target]:
            layer_patterns[target].append(alias)
    return layer_patterns


def _pkg_patterns_for_layers(layer_packages: Dict[str, List[str]],
                             layers: List[str]) -> List[str]:
    """层列表 → ArchUnit 包匹配模式（..variant..），层内变体去重展开。"""
    seen, out = set(), []
    for layer in layers:
        for v in layer_packages.get(layer, [layer]):
            pat = f"..{v}.."
            if pat not in seen:
                seen.add(pat)
                out.append(pat)
    return out


def _archunit_layer_packages(cfg: Dict) -> Dict[str, List[str]]:
    """层名 → 包路径变体（canonical + alias），与 Tier 2 图查询同源。"""
    layer_patterns: Dict[str, List[str]] = {}
    for name, paths in cfg["layer_paths"].items():
        layer_patterns[name] = [p.strip("/") for p in paths]
    for alias, target in sorted(cfg["layer_aliases"].items()):
        if target not in layer_patterns:
            layer_patterns[target] = []
        if alias not in layer_patterns[target]:
            layer_patterns[target].append(alias)
    return layer_patterns


def _suffix_rule_to_name_pattern(pattern: str) -> Optional[str]:
    """Tier 1 后缀正则 → ArchUnit haveNameMatching 的 FQN 正则。
    (?<=[a-z])XXX$（后缀前接小写）→ .*[a-z]XXX$：FQN 以简单名结尾，
    类名首字符前一位置是 '.'（包分隔）或小写字母，语义等价且排除了
    "类名本身即后缀词"（如类名恰为 Inter）的边界。其余负向后行断言原样保留。
    """
    if pattern.startswith("(?<=[a-z])"):
        return ".*[a-z]" + pattern[len("(?<=[a-z])"):]
    return None


def _java_str(s: str) -> str:
    """转义为 Java 字符串字面量内容。"""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _generate_archunit_layering(cfg: Dict, layer_packages: Dict) -> List[str]:
    """_DEPENDENCY_RULES 列视图 → layeredArchitecture 链。"""
    lines = ["    @ArchTest",
             "    static final ArchRule layering = freeze(layeredArchitecture().consideringOnlyDependenciesInLayers()"]
    for layer in _ARCH_LAYER_ORDER:
        if layer not in layer_packages:
            continue
        pats = ", ".join(f'"{p}"' for p in _pkg_patterns_for_layers(layer_packages, [layer]))
        lines.append(f'            .layer("{layer}").definedBy({pats})')
    for target in _ARCH_LAYER_ORDER:
        if target not in layer_packages:
            continue
        accessors = [s for s in _ARCH_LAYER_ORDER
                     if s != target and s in layer_packages
                     and _DEPENDENCY_RULES.get(s, {}).get(target, False)]
        if accessors:
            allowed = ", ".join(f'"{a}"' for a in accessors)
            lines.append(f'            .whereLayer("{target}").mayOnlyBeAccessedByLayers({allowed})'
                         f' // {", ".join(accessors)} → {target}')
        else:
            lines.append(f'            .whereLayer("{target}").mayNotBeAccessedByAnyLayer()')
    lines.append('            .because("分层依赖方向矩阵（steering/gtsp/01 §6-7）；'
                 '模块级 pom 校验由 Tier 1 Python 承担"));')
    return lines


def _generate_archunit_purity(cfg: Dict, layer_packages: Dict) -> List[str]:
    """domain_forbidden_imports −（allowed + annotations 白名单）→ 依赖禁入规则。"""
    forbidden = [p.rstrip(".") + ".." for p in cfg["domain_forbidden_imports"]]
    whitelist_src = list(cfg["domain_allowed_imports"]) + list(cfg.get("domain_annotation_imports", []))
    whitelist = [p.rstrip(".") + ".." for p in whitelist_src]
    forbid_lit = ", ".join(f'"{_java_str(p)}"' for p in forbidden)
    allow_lit = ", ".join(f'"{_java_str(p)}"' for p in whitelist)
    domain_pats = ", ".join(f'"{p}"' for p in _pkg_patterns_for_layers(layer_packages, ["domain"]))
    return [
        "    // ── 领域层纯净度（对齐 Tier 1 check_domain_purity；JPA 注解豁免） ──",
        "    @ArchTest",
        "    static final ArchRule domainPurity = freeze(noClasses()",
        f"            .that().resideInAnyPackage({domain_pats})",
        f"            .should().dependOnClassesThat(resideInAnyPackage({forbid_lit})",
        f"                    .and(DescribedPredicate.not(resideInAnyPackage({allow_lit}))))",
        "            .allowEmptyShould(true)",
        '            .because("领域层禁依赖框架业务类（JPA 注解与 domain_annotation_imports 白名单豁免）")).allowEmptyShould(true);',
    ]


def _generate_archunit_naming(cfg: Dict, layer_packages: Dict) -> List[str]:
    """_SUFFIX_RULES → 每条一个命名规则（allowEmptyShould 防 failOnEmptyShould）。"""
    exclude_prefixes = "|".join(_NAMING_EXCLUDE_STARTSWITH)
    # that() 子句无 doNotHaveNameMatching；用 DescribedPredicate.not(nameMatching(...)) 表达排除前缀
    exclude_lit = f'DescribedPredicate.not(nameMatching(".*\\\\.({exclude_prefixes})\\\\w*"))'
    lines = ["    // ── 命名后缀 × 分层（对齐 _SUFFIX_RULES / 02-naming） ──"]
    for idx, (regex, allowed_layers, severity, message) in enumerate(_SUFFIX_RULES, 1):
        name_pat = _suffix_rule_to_name_pattern(regex.pattern)
        if name_pat is None:
            lines.append(f"    // [跳过] 后缀正则 {regex.pattern} 无 ArchUnit 等价形态：{message}")
            continue
        pats = ", ".join(f'"{p}"' for p in _pkg_patterns_for_layers(layer_packages, list(allowed_layers)))
        sev = severity.value
        lines.append(f"    // {message}")
        lines.append("    @ArchTest")
        lines.append(f"    static final ArchRule naming{idx:02d} = freeze(classes()")
        lines.append(f"            .that().haveNameMatching(\"{_java_str(name_pat)}\")")
        lines.append(f"            .and({exclude_lit})")
        lines.append(f"            .should().resideInAnyPackage({pats})")
        lines.append('            .because("[' + sev + '] ' + _java_str(message) + '"))')
        lines.append("            .allowEmptyShould(true); // 项目无此后缀类时跳过（failOnEmptyShould 默认 true）")
    return lines


def _generate_archunit_state_leakage(cfg: Dict, layer_packages: Dict) -> List[str]:
    """_STATUS_WRITE_NAME_RE → adapter/infrastructure 禁改写状态规则。"""
    pats = ", ".join(f'"{p}"' for p in _pkg_patterns_for_layers(
        layer_packages, ["adapter", "infrastructure"]))
    name_re = _java_str(_STATUS_WRITE_NAME_RE)
    return [
        "    // ── 状态泄漏（对齐 Tier 1 check_state_field_leakage） ──",
        "    @ArchTest",
        "    static final ArchRule noStatusWriteFromAdapterOrInfra = freeze(noClasses()",
        f"            .that().resideInAnyPackage({pats})",
        f"            .should().callCodeUnitWhere(target(nameMatching(\"{name_re}\")))",
        "            .allowEmptyShould(true)",
        '            .because("状态流转属领域知识，adapter/infrastructure 不得直接改写（01 §12/§17）")).allowEmptyShould(true);',
    ]


def _generate_archunit_cycles(prefix: str) -> List[str]:
    """循环依赖（Tier 1 无此能力，ArchUnit 增量价值）。prefix 为空则跳过。"""
    if not prefix:
        return ["    // [跳过] project_package_prefix 未配置，循环依赖规则无法限定分析范围"]
    return [
        "    // ── 循环依赖（Tier 1 无此能力） ──",
        "    @ArchTest",
        "    static final ArchRule noCycles = freeze(slices()",
        f"            .matching(\"{_java_str(prefix)}.(**)\")",
        "            .should().beFreeOfCycles());",
    ]


def _detect_existing_layers(project_root: str, cfg: Dict) -> set:
    """扫描项目目录，返回实际存在的层（空层不生成规则，避免 'Layer X is empty' 假违规）。

    仅匹配目录名与层路径变体（轻量目录扫描，不解析 Java 源码）。
    """
    layer_packages = _archunit_layer_packages(cfg)
    variants = set()
    for paths in layer_packages.values():
        variants.update(paths)
    existing_layers = set()
    for dirpath, dirnames, _ in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for layer, paths in layer_packages.items():
            if layer in existing_layers:
                continue
            if any(v in dirnames or v == os.path.basename(dirpath)
                   for v in paths):
                existing_layers.add(layer)
                break
    return existing_layers


def _generate_archunit_test(cfg: Dict, project_root: str = ".") -> str:
    prefix = cfg.get("project_package_prefix", "")
    layer_packages = _archunit_layer_packages(cfg)
    existing = _detect_existing_layers(project_root, cfg) or set(layer_packages)
    # 只为实际存在的层生成规则（探测失败时回退全层，保底不静默）
    layer_packages = {k: v for k, v in layer_packages.items() if k in existing}
    body: List[str] = []
    body.extend(_generate_archunit_layering(cfg, layer_packages))
    body.append("")
    body.extend(_generate_archunit_purity(cfg, layer_packages))
    body.append("")
    body.extend(_generate_archunit_naming(cfg, layer_packages))
    body.append("")
    body.extend(_generate_archunit_state_leakage(cfg, layer_packages))
    body.append("")
    body.extend(_generate_archunit_cycles(prefix))
    header = f"""// DO NOT EDIT — 由 skills/arch-guard --mode archunit 生成，手改会被 --verify 拦截
// 重新生成: python3 skills/arch-guard/scripts/arch_check.py <root> --mode archunit --output <dir>
// 规则源: .arch-guard.json + arch_check.py 内置矩阵（_DEPENDENCY_RULES/_SUFFIX_RULES 等，单一源）
// 兼容: gtsp-parent -source 8（Java 8 语法）
package {_java_str(prefix)}.archguard;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.core.domain.JavaCall.Predicates.target;
import static com.tngtech.archunit.core.domain.JavaClass.Predicates.resideInAnyPackage;
import static com.tngtech.archunit.core.domain.properties.HasName.Predicates.nameMatching;
import static com.tngtech.archunit.library.Architectures.layeredArchitecture;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;
import static com.tngtech.archunit.library.freeze.FreezingArchRule.freeze;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

// 排除测试类：测试代码不参与架构分层判定（测试位于 ..domain.. 包下调用 infrastructure
// 属正常测试行为，非架构违规——gtsp-wop-gateway 试点实测教训）
@AnalyzeClasses(packages = "{_java_str(prefix)}", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureGuardTest {{

"""
    return header + "\n".join(body) + "\n}\n"


def _generate_archunit_properties() -> str:
    return (
        "# DO NOT EDIT — 由 skills/arch-guard --mode archunit 生成\n"
        "# 本地首跑建基线（allowStoreCreation=true）；CI 应覆盖为 false 防误建\n"
        "freeze.store.default.path=src/test/resources/archguard-store\n"
        "freeze.store.default.allowStoreCreation=true\n"
        "freeze.store.default.allowStoreUpdate=true\n"
    )


def _generate_archunit_guide(cfg: Dict) -> str:
    prefix = cfg.get("project_package_prefix", "")
    return f"""# ArchUnit 接入指引（由 --mode archunit 生成）

## 1. 放置产物

- `ArchitectureGuardTest.java` → `src/test/java/{prefix.replace('.', '/')}/archguard/`
- `archunit.properties` → `src/test/resources/`
- 完整档（6 模块）：放在 `-start` 模块（传递依赖全模块，单 classpath 覆盖）
- 轻量档（api+service）：放在 `-service` 模块

## 2. pom 依赖（test scope）

```xml
<dependency>
    <groupId>com.tngtech.archunit</groupId>
    <artifactId>archunit-junit5</artifactId>
    <version>{ARCHUNIT_VERSION}</version>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter-engine</artifactId>
    <version>{ARCHUNIT_JUNIT5_VERSION}</version>
    <scope>test</scope>
</dependency>
```

> ⚠️ Spike 实测：部分项目 fss-common 的 lombok 为 provided 不传递，纯 `mvn test`
> 会编译失败——若遇到 `package lombok does not exist`，补：
>
> ```xml
> <dependency>
>     <groupId>org.projectlombok</groupId>
>     <artifactId>lombok</artifactId>
>     <version>1.18.30</version>
>     <scope>provided</scope>
> </dependency>
> ```

## 3. 基线（ratchet，与 Tier 1 语义一致）

1. 本地首跑 `mvn test -Dtest=ArchitectureGuardTest`：freeze store 落盘
   `src/test/resources/archguard-store/`，全部存量违规被冻结，测试绿。
2. 提交 store 目录（与 `.arch-guard-baseline.json` 同等地位，随仓走）。
3. CI 运行时覆盖 `-Darchunit.freeze.store.default.allowStoreCreation=false`
   防误建基线；偿还存量 → store 自动收缩（allowStoreUpdate=true）。

## 4. 防漂移（DO NOT EDIT）

CI 中运行 `--mode archunit --verify`：配置/矩阵变更后未重新生成 → exit 1。

## 5. 层别名

本项目生效的 layer_aliases：`{json.dumps(cfg.get("layer_aliases", {}), ensure_ascii=False)}`
（ArchUnit 层定义已展开为多包模式；调整别名请改 `.arch-guard.json` 后重新生成）。
"""


def _find_generated_files(root: str) -> Tuple[Optional[str], Optional[str]]:
    """在项目内定位已提交的生成物。

    跳过 SKIP_DIRS 但豁免 "test"/"tests"：生成物按 Maven 惯例位于 src/test/，
    若照抄 SKIP_DIRS（Tier 1 巡检语义：排除测试目录）会剪掉 src/test 整棵
    子树，--verify 在标准布局项目上恒报"不存在"（三试点实测教训）。
    """
    verify_skip = SKIP_DIRS - {"test", "tests"}
    test_path = props_path = None
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in verify_skip]
        if "ArchitectureGuardTest.java" in filenames and test_path is None:
            test_path = os.path.join(dirpath, "ArchitectureGuardTest.java")
        if "archunit.properties" in filenames and props_path is None:
            props_path = os.path.join(dirpath, "archunit.properties")
    return test_path, props_path


def print_archunit_mode(project_root: str, config_path: Optional[str] = None,
                        output_dir: Optional[str] = None, verify: bool = False):
    """--mode archunit：生成 ArchUnit 测试/properties/指引，或校验生成物漂移。"""
    cfg = load_config(project_root, config_path)
    prefix = cfg.get("project_package_prefix", "")
    if not prefix:
        print("错误: project_package_prefix 未配置，无法限定 @AnalyzeClasses 范围"
              "（不限定会扫描整个 classpath 含第三方类，产生大量误报）。\n"
              "  请先运行 --init 或在 .arch-guard.json 中配置 project_package_prefix。",
              file=sys.stderr)
        sys.exit(2)

    test_src = _generate_archunit_test(cfg, project_root)
    props = _generate_archunit_properties()
    guide = _generate_archunit_guide(cfg)

    if verify:
        base = output_dir if output_dir else project_root
        existing_test, existing_props = _find_generated_files(base)
        problems = []
        if existing_test is None:
            problems.append("ArchitectureGuardTest.java 不存在（未生成或被删除）")
        elif open(existing_test, encoding="utf-8").read() != test_src:
            problems.append(f"ArchitectureGuardTest.java 与当前配置生成结果不一致: {existing_test}")
        if existing_props is None:
            problems.append("archunit.properties 不存在（未生成或被删除）")
        elif open(existing_props, encoding="utf-8").read() != props:
            problems.append(f"archunit.properties 与生成结果不一致: {existing_props}")
        if problems:
            print("❌ 生成物漂移（配置/规则矩阵变更后未重新生成，或被手改）:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            print("  修复: python3 arch_check.py <root> --mode archunit --output <dir> 重新生成并提交",
                  file=sys.stderr)
            sys.exit(1)
        print("✅ ArchUnit 生成物与当前配置一致（无漂移）")
        sys.exit(0)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for name, content in (("ArchitectureGuardTest.java", test_src),
                              ("archunit.properties", props),
                              ("INTEGRATION.md", guide)):
            path = os.path.join(output_dir, name)
            with open(path, "w", encoding="utf-8") as fp:
                fp.write(content)
            print(f"已生成: {path}")
        print(f"\n下一步: 按 {os.path.join(output_dir, 'INTEGRATION.md')} 接入（放置产物 + pom 依赖 + 基线）")
    else:
        print(test_src)
        print("// 提示: 完整三产物（测试/properties/接入指引）用 --output <dir> 生成",
              file=sys.stderr)
    sys.exit(0)

# ── init ────────────────────────────────────────────────────────────────────

def _infer_prefix_from_pom(project_root: str) -> Optional[str]:
    """从根目录 pom.xml 的 <groupId> 自动推断 project_package_prefix。"""
    pom = os.path.join(project_root, "pom.xml")
    if not os.path.isfile(pom):
        # 尝试子目录第一层
        for entry in os.listdir(project_root):
            sub = os.path.join(project_root, entry, "pom.xml")
            if os.path.isfile(sub):
                pom = sub
                break
    if not os.path.isfile(pom):
        return None
    try:
        tree = ET.parse(pom)
        root = tree.getroot()
        gid = root.find(_pom_tag("groupId"))
        if gid is None or not gid.text:
            parent = root.find(_pom_tag("parent"))
            if parent is not None:
                gid = parent.find(_pom_tag("groupId"))
        if gid is not None and gid.text:
            return gid.text.strip()
    except Exception:
        pass
    return None


def _do_init(project_root: str, output_path: str):
    """自动推断配置并生成 .arch-guard.json。"""
    prefix = _infer_prefix_from_pom(project_root)
    if prefix:
        inferred_msg = f"从 pom.xml <groupId> 推断: {prefix}"
    else:
        inferred_msg = "未找到 pom.xml，project_package_prefix 留空（使用启发式回退）"

    config = {
        "project_package_prefix": prefix or "",
        "_comment": f"自动生成 by arch_check --init。{inferred_msg}",
    }

    out = os.path.join(project_root, output_path)
    if os.path.exists(out):
        print(f"错误: {out} 已存在。若需覆盖请手动删除后重试。", file=sys.stderr)
        sys.exit(1)

    with open(out, "w", encoding="utf-8") as fp:
        json.dump(config, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    print(f"已生成: {out}")
    print(f"  {inferred_msg}")
    print(f"  layer_aliases 默认内置 interfaces→adapter，无需额外配置")
    if not prefix:
        print(f"  ⚠️  建议手动设置 project_package_prefix 以消除第三方 import 误报风险")


def main():
    parser = argparse.ArgumentParser(description="DDD 架构分层守护检查")
    parser.add_argument("project_root", nargs="?", default=".",
                       help="Java 项目根目录（--mode graph 时不需要）")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--strict", action="store_true",
                       help="推荐问题升级为强制（影响退出码和 passed）")
    parser.add_argument("--config", default=None,
                       help="配置文件路径（默认查找 .arch-guard.json）")
    parser.add_argument("--mode", choices=["check", "graph", "archunit"], default="check",
                       help="check: 脚本巡检（默认）; graph: Tier 2 Cypher 清单; "
                            "archunit: 生成 ArchUnit 测试（配合 --output/--verify）")
    parser.add_argument("--output", default=None, metavar="DIR",
                       help="--mode archunit 产物输出目录（缺省打印测试源码到 stdout）")
    parser.add_argument("--verify", action="store_true",
                       help="--mode archunit 漂移校验：生成物与配置不一致 → exit 1")
    parser.add_argument("--baseline", default=None,
                       help="基线文件路径（仅报新增违规；偿还存量后基线自动收缩）")
    parser.add_argument("--refreeze", default=None, metavar="PATH",
                       help="用当前全部违规重置基线（唯一允许基线变大的路径，有意重置债务线时使用）")
    parser.add_argument("--update-baseline", default=None, metavar="PATH",
                       help="[已弃用] --refreeze 的别名：用当前所有违规重写基线文件")
    parser.add_argument("--frozen", action="store_true",
                       help="CI 模式：基线缺失/损坏时拒绝执行（exit 2）；合法空基线=零债务，放行")
    parser.add_argument("--warn-unclassified", action="store_true",
                       help="将未识别层的文件数输出为警告")
    parser.add_argument("--debug", action="store_true",
                       help="输出调试信息到 stderr（文件跳过原因等）")
    parser.add_argument("--init", nargs="?", const=".arch-guard.json", default=None,
                       metavar="PATH",
                       help="自动生成最小配置文件，从 pom.xml 推断 project_package_prefix")
    args = parser.parse_args()

    global _debug_enabled
    _debug_enabled = args.debug

    if args.init:
        _do_init(args.project_root, args.init)
        sys.exit(0)

    if args.mode == "graph":
        print_graph_mode(config_path=args.config)
        sys.exit(0)

    if args.mode == "archunit":
        print_archunit_mode(args.project_root, config_path=args.config,
                            output_dir=args.output, verify=args.verify)
        sys.exit(0)

    if not os.path.isdir(args.project_root):
        print(f"错误: 路径不存在或不是目录: {args.project_root}", file=sys.stderr)
        sys.exit(2)

    # --refreeze 模式：执行完整检查，将当前全部违规重置进基线（唯一允许基线变大的路径）
    # --update-baseline 为弃用别名（行为等价，仅打印迁移提示）
    refreeze_path = args.refreeze or args.update_baseline
    if refreeze_path:
        if args.update_baseline:
            print("⚠️  --update-baseline 已弃用，请改用 --refreeze（语义相同：用当前全部违规重置基线）",
                  file=sys.stderr)
        issues, m, r, stats = run(args.project_root, strict=True,
                                  config_path=args.config)
        # 使用原始违规（不含基线过滤）保存
        save_baseline(refreeze_path, issues)
        sd = stats.get("structural_debt_count", 0)
        print(f"重置基线: {refreeze_path} ({len(issues)} 个违规)")
        print(f"  其中 {m} 强制, {r} 推荐"
              + (f", {sd} 结构债务" if sd else ""))
        sys.exit(0)

    # --frozen（CI 模式）：扫描前校验基线文件状态（三态区分）：
    #   missing/corrupt → 拒绝执行（exit 2，防误建吞违规/坏文件静默放过）
    #   empty（合法零指纹）→ 放行 —— 债务已全部还清，零债务即全绿（对齐
    #     ArchUnit FreezingArchRule：store 收缩为空时测试通过而非失败）
    if args.frozen:
        if not args.baseline:
            print("错误: --frozen 需要同时指定 --baseline", file=sys.stderr)
            sys.exit(2)
        state, _ = baseline_state(args.baseline)
        if state == "missing":
            print(f"错误: 基线文件不存在: {args.baseline}\n"
                  "  CI 模式拒绝自动创建基线（防止吞掉违规）。请先在本地执行:\n"
                  f"    python3 arch_check.py {args.project_root} --refreeze {args.baseline}",
                  file=sys.stderr)
            sys.exit(2)
        if state == "corrupt":
            print(f"错误: 基线文件损坏或结构非法: {args.baseline}\n"
                  "  CI 模式 fail-closed 拒绝运行（无法确认基线可信）。"
                  "请在本地检查该文件，或重新执行 --refreeze 生成。",
                  file=sys.stderr)
            sys.exit(2)

    issues, m, r, stats = run(args.project_root, strict=args.strict,
                              config_path=args.config,
                              baseline_path=args.baseline,
                              warn_unclassified=args.warn_unclassified)

    if args.format == "json":
        print(format_json(issues, m, r, strict=args.strict, stats=stats,
                          baseline_path=args.baseline))
    else:
        print(format_text(issues, m, r, stats=stats))
    # 输出未分类文件的警告（如果很多文件未被识别层，可能是配置问题）
    if args.warn_unclassified and stats.get("java_files_unclassified", 0) > stats.get("java_files_total", 1) * 0.5:
        print(f"\n⚠️  超过半数 Java 文件 ({stats['java_files_unclassified']}/{stats['java_files_total']}) "
              f"未被识别到架构分层。请检查 layer_paths 和 layer_aliases 配置。",
              file=sys.stderr)

    if m > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
