"""rejected_reconcile 对账测试——reject→人工闭环缺口（2026-08-23 审计）。

场景锚定真实事故形态：4 个 rejected issue 修复已进 main 但 issue 未关。
机器不可判定"是否已修复"，只暴露处置信号（回执后人工评论数）。
"""

import json
import subprocess
import sys
from pathlib import Path

from factory_lib import RECEIPT_CLOSURE_NOTE, reject_receipt, rejected_reconcile

FACTORY = Path(__file__).resolve().parents[1]

RECEIPT_BODY = "## 工厂 triage 裁决：reject —— 判据 b 不通过"


def _issue(n, comments):
    return {"number": n, "title": f"issue-{n}", "comments": comments}


def test_human_comment_after_receipt_counted():
    """回执后的人工评论 = 处置信号（审计实证的「已修未关」形态）。"""
    it = rejected_reconcile([_issue(23, [
        {"author": "sourcery-ai[bot]", "body": "review"},
        {"author": "im47cn", "body": RECEIPT_BODY},      # 链回执（bot 语义）
        {"author": "im47cn", "body": "已人工修复，PR #27"},  # 回执后人工评论
    ])])[0]
    assert it["human_comments_after_reject"] == 1


def test_bot_and_receipt_comments_excluded():
    """回执本体与 bot 评论不计——回执前的人工评论也不计（裁决前语境）。"""
    it = rejected_reconcile([_issue(24, [
        {"author": "im47cn", "body": "裁决前的讨论"},       # 回执前：不算
        {"author": "im47cn", "body": RECEIPT_BODY},
        {"author": "github-actions[bot]", "body": "CI done"},  # bot：不算
    ])])[0]
    assert it["human_comments_after_reject"] == 0


def test_latest_receipt_wins_when_multiple():
    """多轮回执取最后一轮为界——重投后再拒，只看最新裁决之后。"""
    it = rejected_reconcile([_issue(5, [
        {"author": "im47cn", "body": RECEIPT_BODY},       # round0 回执
        {"author": "im47cn", "body": "按指引重投"},         # round0 后（应忽略）
        {"author": "im47cn", "body": RECEIPT_BODY},       # round1 回执
    ])])[0]
    assert it["human_comments_after_reject"] == 0


def test_no_receipt_counts_all_human():
    """无回执（历史形态/批次落标无评论）→ 全部人工评论计为处置信号。"""
    it = rejected_reconcile([_issue(3, [
        {"author": "im47cn", "body": "人工处置说明"},
    ])])[0]
    assert it["human_comments_after_reject"] == 1


def test_malformed_entries_fail_open():
    """comments 缺失/标量/元素非 dict → 0 计数不抛——对账报告不得崩链尾。"""
    out = rejected_reconcile([
        {"number": 1, "title": "t"},
        {"number": 2, "title": "t", "comments": None},
        {"number": 3, "title": "t", "comments": [42, {"body": "x"}]},
    ])
    assert [r["human_comments_after_reject"] for r in out] == [0, 0, 0]


def test_title_truncated():
    """超长标题截 60 字符——dispatch 单行报告防刷屏。"""
    it = rejected_reconcile([{"number": 9, "title": "长" * 100,
                              "comments": []}])[0]
    assert len(it["title"]) == 60


def test_cli_tsv_smoke():
    """CLI: stdin JSON → TSV（number\tcount\ttitle）——dispatch 消费契约。"""
    payload = json.dumps([_issue(23, [
        {"author": "im47cn", "body": RECEIPT_BODY},
        {"author": "im47cn", "body": "已修"},
    ])])
    proc = subprocess.run(
        [sys.executable, str(FACTORY / "factory_lib.py"), "rejected-reconcile"],
        input=payload, capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout == "23\t1\tissue-23\n"


def test_receipt_carries_closure_note():
    """回执带处置协议教育句——人工 PR 带 Closes #N 即自动闭环。"""
    md = reject_receipt({"verdict": "reject", "reasons": ["判据b: 不通过"]})
    assert RECEIPT_CLOSURE_NOTE in md
    assert "Closes #" in md
