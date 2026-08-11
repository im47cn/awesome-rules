"""架构风险扫描器。

运行 arch_check.py，将架构违规转换为结构化风险清单。
"""

import json
import os
import subprocess
import sys
from pathlib import Path


class RiskScanner:
    """运行 arch_check.py，将架构违规转换为风险清单"""

    RISK_LEVEL_MAP = {"强制": "critical", "推荐": "warning", "结构性债务": "info"}

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        # arch_check 路径解析所需属性(scan 按优先级 1-5 查找)在此初始化空值,
        # 使 scan() 安全走到基于 __file__ 的 _default_location() 兜底,
        # 避免访问未定义属性抛 AttributeError 中断整个生成流程。
        self._arch_check_path = ""
        self._arch_check_env = os.environ.get("ARCH_CHECK_PATH", "")
        self._config_path = ""

    def _default_location(self) -> Path:
        """arch_check.py 默认查找位置(基于 __file__ 向上推导 skills/arch-guard)。

        risks.py 位于 skills/doc-gen/scripts/generator/, arch_check.py 位于
        skills/arch-guard/scripts/。未找到时返回占位路径, 由 scan() 转 error 提示,
        避免方法缺失导致整个生成流程崩溃。
        """
        here = Path(__file__).resolve()
        candidates = [
            here.parent.parent.parent.parent / "arch-guard" / "scripts" / "arch_check.py",
            here.parent.parent / "arch-guard" / "scripts" / "arch_check.py",
        ]
        for c in candidates:
            if c.exists():
                return c
        return Path("arch_check.py")  # 占位: scan() 检测不存在后返回 error

    def _resolve_arch_check(self) -> Optional[Path]:
        """解析 arch_check.py 路径，优先级（从高到低）：

        1. 构造函数传入的 arch_check_path
        2. ARCH_CHECK_PATH 环境变量（显式指定但不存在时返回 None，早停不回退，
           以便 scan() 给出精确的"路径不存在"提示）
        3. .doc-gen.json 中的 arch_check_path 配置项
        4/5. 基于 __file__ 的默认位置（skills/doc-gen → skills/arch-guard）
        """
        # 优先级 1: 构造函数传入
        if self._arch_check_path and Path(self._arch_check_path).exists():
            return Path(self._arch_check_path).resolve()
        # 优先级 2: 环境变量
        if self._arch_check_env:
            candidate = Path(self._arch_check_env).expanduser()
            if candidate.exists():
                return candidate.resolve()
            return None                    # 显式指定但不存在 → 不回退
        # 优先级 3: 配置文件
        if self._config_path and Path(self._config_path).exists():
            try:
                config = json.loads(Path(self._config_path).read_text(encoding="utf-8"))
                config_path = config.get("arch_check_path", "")
                if config_path and Path(config_path).exists():
                    return Path(config_path).resolve()
            except (json.JSONDecodeError, OSError):
                pass
        # 优先级 4/5: 默认位置
        return self._default_location()

    def _not_found_hint(self) -> str:
        """路径未找到时，按触发来源给出对应提示。"""
        if self._arch_check_env:
            return f" ARCH_CHECK_PATH 指向的路径不存在: {self._arch_check_env}"
        if self._config_path and Path(self._config_path).exists():
            return " 请在 .doc-gen.json 中配置 arch_check_path 字段，或设置 ARCH_CHECK_PATH 环境变量。"
        return " 请通过 --arch-check-path 参数或 ARCH_CHECK_PATH 环境变量指定 arch_check.py 路径。"

    def scan(self) -> dict:
        """运行 arch_check.py 返回结构化风险数据。

        路径解析委托 _resolve_arch_check（可独立单测，不依赖 subprocess）。
        """
        arch_check = self._resolve_arch_check()
        if not arch_check or not arch_check.exists():
            detail = str(arch_check) if arch_check else "(未解析)"
            return {"error": f"arch_check.py 未找到: {detail}{self._not_found_hint()}",
                    "issues": [], "summary": {}}

        try:
            result = subprocess.run(
                [sys.executable, str(arch_check), str(self.root_path), "--format", "json"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode not in (0, 1):  # 0=通过, 1=有违反
                return {"error": f"arch_check.py 执行失败: {result.stderr[:500]}", "issues": [], "summary": {}}

            data = json.loads(result.stdout)
            issues = data.get("issues", [])

            # 丰富风险信息
            enriched = []
            for iss in issues:
                rule_code = iss.get("rule_code", "")
                enriched.append({
                    "file": iss.get("file", ""),
                    "line": iss.get("line", 0),
                    "severity": iss.get("severity", "？"),
                    "level": self.RISK_LEVEL_MAP.get(iss.get("severity", ""), "info"),
                    "rule": iss.get("rule", rule_code),
                    "ruleCode": rule_code,
                    "description": iss.get("description", ""),
                    "suggestion": iss.get("suggestion", ""),
                })

            # 按严重性排序
            severity_order = {"critical": 0, "warning": 1, "info": 2}
            enriched.sort(key=lambda x: severity_order.get(x["level"], 99))

            return {
                "passed": data.get("passed", False),
                "totalIssues": len(enriched),
                "criticalCount": sum(1 for i in enriched if i["level"] == "critical"),
                "warningCount": sum(1 for i in enriched if i["level"] == "warning"),
                "infoCount": sum(1 for i in enriched if i["level"] == "info"),
                "summary": data.get("summary", {}),
                "issues": enriched,
            }
        except subprocess.TimeoutExpired:
            return {"error": "arch_check.py 执行超时", "issues": [], "summary": {}}
        except json.JSONDecodeError:
            return {"error": "arch_check.py 输出解析失败", "issues": [], "summary": {}}
        except Exception as e:
            return {"error": str(e)[:500], "issues": [], "summary": {}}
