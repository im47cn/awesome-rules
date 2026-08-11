#!/usr/bin/env bash
#
# awesome-rules —— Git 自动化工具一键安装
# 模式：工具全局（commitlint/commit-and-tag-version）+ 配置仓库（commitlint.config.js/.versionrc.js）+ hook 仓库（commit-msg）
#
# 用法:
#   bash install.sh [目标项目根目录]   # 默认当前目录
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$(cd "${1:-$PWD}" && pwd)"

echo "▸ 目标项目: $TARGET"

# ── 1. 检测 node / npm ──────────────────────────────────────────
command -v node >/dev/null 2>&1 || { echo "✘ 未检测到 node，请先安装 node ≥ 16"; exit 1; }
command -v npm  >/dev/null 2>&1 || { echo "✘ 未检测到 npm"; exit 1; }
echo "✔ node $(node -v)"

# ── 2. 拷贝配置（已存在则确认覆盖）──────────────────────────────
for f in commitlint.config.js .versionrc.js; do
  if [ -f "$TARGET/$f" ]; then
    read -rp "⚠ $f 已存在，覆盖？[y/N] " ans || true
    [ "${ans:-N}" = "y" ] || { echo "  跳过 $f"; continue; }
  fi
  cp "$SCRIPT_DIR/$f" "$TARGET/$f"
done

# commit 模板 → 用户主目录 ~/.gitmessage（全局，所有仓库/IDEA 一次识别）
skip_tmpl=0
if [ -f "$HOME/.gitmessage" ]; then
  read -rp "⚠ ~/.gitmessage 已存在，覆盖？[y/N] " ans || true
  [ "${ans:-N}" = "y" ] || { echo "  跳过 ~/.gitmessage"; skip_tmpl=1; }
fi
if [ "$skip_tmpl" != "1" ]; then
  cp "$SCRIPT_DIR/commit-template.txt" "$HOME/.gitmessage"
  git config --global commit.template "$HOME/.gitmessage"
  echo "✔ 全局 commit 模板已配置（~/.gitmessage，所有仓库生效）"
fi
echo "✔ 配置已就位"

# ── 3. 全局安装工具（一次，所有项目共享；检测已装则跳过）─────────
# commitlint / commit-and-tag-version 装全局，避免每项目重复 npm install
GLOBAL_PKGS=("@commitlint/cli" "@commitlint/config-conventional" "commit-and-tag-version")
INSTALLED=$(npm ls -g --depth=0 2>/dev/null || true)
NEED=()
for pkg in "${GLOBAL_PKGS[@]}"; do
  echo "$INSTALLED" | grep -q "$pkg@" || NEED+=("$pkg")
done
if [ ${#NEED[@]} -gt 0 ]; then
  npm install -g "${NEED[@]}"
  echo "✔ 全局工具已安装: ${NEED[*]}"
else
  echo "✔ 全局工具已就位（跳过安装）"
fi
cd "$TARGET"

# ── 4. 写 git commit-msg hook（原生 hook，无需 husky）────────────
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || true)"
if [ -n "$GIT_DIR" ]; then
  HOOK="$GIT_DIR/hooks/commit-msg"
  mkdir -p "$(dirname "$HOOK")"
  cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# 由 awesome-rules tools/git/install.sh 生成 —— 调全局 commitlint 校验
commitlint --edit "$1"
EOF
  chmod +x "$HOOK"
  echo "✔ git commit-msg hook 已写入"
else
  echo "⚠ 非 git 仓库，跳过 commit-msg hook"
fi

# ── 5. 注入 package.json scripts ────────────────────────────────
if [ -f "$TARGET/package.json" ]; then
  node -e '
    const fs = require("fs");
    const f = "package.json";
    const j = JSON.parse(fs.readFileSync(f, "utf8"));
    j.scripts = j.scripts || {};
    j.scripts.release = "commit-and-tag-version";
    j.scripts["release:dry"] = "commit-and-tag-version --dry-run";
    fs.writeFileSync(f, JSON.stringify(j, null, 2) + "\n");
  '
  echo "✔ package.json scripts 已注入（release / release:dry）"
fi

echo ""
echo "✅ 安装完成"
echo "   提交校验  → git commit 时自动触发"
echo "   发版预览  → npm run release:dry"
echo "   正式发版  → npm run release"
