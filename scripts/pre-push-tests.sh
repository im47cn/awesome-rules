#!/usr/bin/env bash
# awesome-rules 本仓库的全量测试门禁（pre-push 入口，被 .lefthook/run-tests.sh 调用）
set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$REPO_ROOT/scripts/run_tests.sh"
