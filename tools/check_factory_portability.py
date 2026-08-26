#!/usr/bin/env python3
"""check_factory_portability —— .factory 拆分就绪门（ADR-009）。

三条规则（负控制 NC13，test_gauntlet_checks.sh）：
  P1 宿主专名零容忍：DISTRIBUTION.json full 面的 .sh/.py（排除 tests/——
     测试夹具以真实 slug/作者名当样例数据是合法用法）与 prompts/*.md 中
     禁出现宿主仓特定标识（awesome-rules / im47cn / gtsp- / fss- /
     etf-radar / steering/ / scripts/run_tests）。历史考证引用一律中性化
     （「源仓#NN」保留编号可溯），本地化值一律走 factory-local.json。
  P2 引擎单点：full 面 .sh 中 omp CLI 直调（`omp -p`）只允许出现在
     factory-lib.sh 的 omp_node——换引擎只改一个函数（设计 §4）。
  P3 无平铺 path hack：full 面 .py（排除 tests/）禁 sys.path.insert——
     布局注入只属于 tests/conftest.py；测试对兄弟源目录的注入在被测
     布局语义内，不在此门管辖。

语义契约见 docs/design/factory-harness-design.md §11 与 ADR-009。
退出码：0 = 干净；1 = 有命中；2 = 门自身错误（fail-closed）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# P1 禁词：宿主仓名 / 组织名 / 宿主仓特定路径。run_tests 用裸词（review
# R2-M6）："scripts/run_tests" 会漏 bare run_tests.sh 文案/注释残留。
# 刻意不含 "skills/"：monorepo|skills 双布局识别是通用机制词（factory_lib
# evidence_suites），非宿主绑定。误报的修复属于模式，不属于豁免清单。
P1_PATTERN = re.compile(
    r"awesome-rules|im47cn|gtsp-|fss-|etf-radar|steering/|run_tests")

ENGINE_MARK = "omp -p"
ENGINE_ALLOWED = "factory-lib.sh"
PATH_HACK = "sys.path.insert"


def _fail_closed(cond: bool, msg: str) -> None:
    if not cond:
        print(f"check_factory_portability: {msg}", file=sys.stderr)
        sys.exit(2)


def scan(repo_root: Path) -> int:
    factory = repo_root / ".factory"
    dist = factory / "DISTRIBUTION.json"
    _fail_closed(dist.is_file(), f"缺 {dist}（DISTRIBUTION 漂移）")
    try:
        d = json.loads(dist.read_text(encoding="utf-8"))
        full = d["full"]
    except Exception as exc:
        _fail_closed(False, f"DISTRIBUTION.json 不可解析: {exc}")

    files: list[Path] = []
    for entry in full:
        p = factory / entry
        _fail_closed(p.exists(), f"full 面条目不存在: {entry}（清单漂移）")
        if p.is_dir():
            continue  # tests/ 整目录：P1/P3 豁免（见模块 docstring）
        if p.suffix in (".sh", ".py"):
            files.append(p)
    prompts = sorted((factory / "prompts").glob("*.md"))
    _fail_closed(bool(prompts), "prompts/ 为空（清单漂移）")

    hits = 0
    for f in files + prompts:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception as exc:
            _fail_closed(False, f"{f} 不可读: {exc}")
        for i, line in enumerate(text.splitlines(), 1):
            if P1_PATTERN.search(line):
                print(f"P1 宿主专名: {f.relative_to(repo_root)}:{i}: {line.strip()[:90]}")
                hits += 1
            if ENGINE_MARK in line and f.name != ENGINE_ALLOWED:
                print(f"P2 引擎旁路: {f.relative_to(repo_root)}:{i}: {line.strip()[:90]}")
                hits += 1
            if PATH_HACK in line and f.suffix == ".py":
                print(f"P3 path hack: {f.relative_to(repo_root)}:{i}: {line.strip()[:90]}")
                hits += 1
    if hits:
        print(f"factory-portability: {hits} 命中（P1 专名 / P2 引擎旁路 / P3 平铺 hack）")
        return 1
    print(f"factory-portability: P1/P2/P3 干净（{len(files)} full 面 + {len(prompts)} prompts）")
    return 0


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    _fail_closed((root / ".factory").is_dir(), f"{root} 不是含 .factory 的仓库根")
    return scan(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
