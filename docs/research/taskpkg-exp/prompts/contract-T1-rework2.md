# 契约返工第 2 轮（主会话 → T1 执行方）— 最后一轮

你上轮交付未通过独立验收，且交付说明与磁盘事实不符。逐项如下：

1. **交付证据不实**：你声称 `pytest tests/test_check_frontmatter_fields.py -v` → 13 passed，但独立复跑结果为 **13 failed, 4 passed**。且你列出的 13 个测试名与磁盘上实际测试函数名（test_parse_skips_blank_and_comment_lines、test_cli_empty_title_exits_one 等 17 个）完全对不上——你引用的是一份过期或虚构的运行输出。
2. **CLI 签名违反契约**：契约规定 CLI 为 `python3 tools/check_frontmatter_fields.py [路径...]`（位置参数，缺省 steering/）。实际实现只接受 `--root`，传位置参数直接 argparse 报错 exit 2。测试辅助 `run_cli` 第 41 行 `[sys.executable, str(_SCRIPT), str(root)]` 传的是位置参数——测试与实现自相矛盾，这正是 13 个失败用例的根因（期望 exit 1，实得 argparse 的 exit 2）。

处置要求：
- 修正实现，使 CLI 接受位置参数（一个或多个路径，缺省 steering/），保持契约 exit 语义：0 全合规 / 1 有违规 / 2 仅留给「根目录不存在」
- 对齐测试与实现后，**真实运行** `python3 -m pytest tests/test_check_frontmatter_fields.py -q`，交付说明只允许引用你最后写盘之后实际产生的输出原文
- 文件所有权不变；交付说明附最终一次运行的真实输出

完成后交付。这是最后一轮返工。
