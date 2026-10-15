#!/bin/zsh
# qj-sync.sh —— 第七境 · MacBook 端（唯一写入端）同步助手
#
# 架构：MacBook 是链路上**唯一**会 push 的一端。Mac mini 只 pull、从不 push，
#       所以 pull 永远可以走 --ff-only，不存在 merge 冲突。
#
# 用法
#   sh qj-sync.sh pull                 改文件之前：拉远端最新
#   sh qj-sync.sh push "改了什么"       改完之后：提交并推送
#   sh qj-sync.sh auto "改了什么"       pull → commit → push 一条龙
#   sh qj-sync.sh status               看工作区状态（不 push）
#   sh qj-sync.sh setup <仓库地址>     首次初始化 git 并关联远端
#
# 纪律
#   - 零积分：只用 git/curl，不调模型
#   - 不擅自推：push 必须显式命令 + 写明提交信息
#   - 失败即报：任何一步失败都打印原因并以非零码退出，不静默继续

set -uo pipefail

# 🔴 两个坑，别改回去：
#   ① zsh 函数内部的 $0 是函数名 ⇒ 必须在顶层先存成全局量
#   ② launchd 用 `sh` 调用本脚本时，zsh 进入 sh 兼容模式，
#      ${0:A} 会被解析成未定义变量 A ⇒ "A: unbound variable"（2026-10-13 实测踩到）
#      ⇒ 下面这套是 POSIX 写法，sh / zsh 两种调用方式都能跑
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
SCRIPT="$SCRIPT_DIR/$(basename "$0")"
ROOT="${ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$ROOT" || { echo "❌ 找不到项目根目录: $ROOT"; exit 1; }

REPO_NAME="第七境"

# ---------- 基础自检 ----------
need_git_identity() {
  if [ -z "$(git config user.name 2>/dev/null)" ] || [ -z "$(git config user.email 2>/dev/null)" ]; then
    echo "❌ git 全局身份未配置。先执行（邮箱别用工作邮箱）："
    echo "   git config --global user.name  \"你的名字\""
    echo "   git config --global user.email \"你的邮箱\""
    return 1
  fi
  return 0
}

ensure_repo() {
  if [ ! -d .git ]; then
    echo "❌ 当前目录还不是 git 仓库。先执行：sh $SCRIPT setup <你的私有仓库地址>"
    return 1
  fi
  return 0
}

guard_gitignore() {
  # 🔴 .gitignore 是分层的核心：没有它，第一次 commit 就会把 3.6GB 缓存写进历史
  if [ ! -f .gitignore ]; then
    echo "❌ 缺少 .gitignore！先补回来再 add，否则垃圾会进历史且不可逆。"
    return 1
  fi
  # 兜底：拦截任何 >20MB 的文件进入暂存区
  local big
  big=$(git diff --cached --name-only 2>/dev/null | head -200 | while read -r f; do
    [ -f "$f" ] || continue
    s=$(stat -f%z "$f" 2>/dev/null || echo 0)
    [ "$s" -gt 20971520 ] && echo "$f ($((s/1048576))MB)"
  done)
  if [ -n "$big" ]; then
    echo "❌ 检测到超大文件，已中止（二进制应走移动硬盘，不进 Git）："
    echo "$big"
    git reset -q 2>/dev/null
    return 1
  fi
  return 0
}

# ---------- setup ----------
cmd_setup() {
  local url="${1:-}"
  [ -z "$url" ] && { echo "用法：sh $SCRIPT setup <私有仓库地址>"; exit 1; }
  need_git_identity || exit 1

  if [ ! -d .git ]; then
    echo "→ 初始化仓库…"
    git init -q -b main || exit 1
    git config core.quotePath false
    git config core.autocrlf false
  fi

  if git remote get-url origin >/dev/null 2>&1; then
    echo "→ 已有远端：$(git remote get-url origin)"
    echo "  要改成 $url 请手动：git remote set-url origin <url>"
  else
    git remote add origin "$url"
    echo "→ 已关联远端：$url"
  fi

  echo "→ 检查将要入库的规模…"
  local n size
  n=$(git status --porcelain -uall | wc -l | tr -d ' ')
  echo "   待入库约 $n 个文件"
  echo ""
  echo "✅ 就绪。接下来执行："
  echo "   sh $SCRIPT push \"首次提交：文本层入库\""
  echo ""
  echo "⚠️  首次推送后请到 GitHub 网页确认仓库是 **Private**（私有）。"
}

# ---------- pull ----------
cmd_pull() {
  ensure_repo || exit 1
  if ! git remote get-url origin >/dev/null 2>&1; then
    echo "⚠️  尚未关联远端，跳过 pull。关联方式：sh $SCRIPT setup <仓库地址>"
    return 0
  fi
  echo "→ 拉取远端最新…"
  if git pull --rebase --autostash origin main 2>&1 | sed 's/^/   /'; then
    echo "✅ pull 完成"
  else
    echo "❌ pull 失败（见上方输出）。不要在这个状态下继续改文件。"
    return 1
  fi
}

# ---------- push ----------
cmd_push() {
  local msg="${1:-}"
  ensure_repo || exit 1
  need_git_identity || exit 1
  [ -z "$msg" ] && { echo "用法：sh $SCRIPT push \"提交说明\""; exit 1; }

  # 先导出 MEMORY 快照：.workbuddy/ 被 .gitignore 排除，快照是它唯一的异地备份。
  # 脚本内部已做幂等（内容未变不写盘）与失败降级（不阻塞同步）。
  local pyb="${PYBIN:-/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3}"
  [ -x "$pyb" ] || pyb="$(command -v python3 2>/dev/null || echo python3)"
  "$pyb" "$ROOT/11-运营/scripts/export-memory-snapshot.py" 2>&1 | sed 's/^/  /'

  git add -A
  guard_gitignore || exit 1

  if git diff --cached --quiet 2>/dev/null; then
    echo "→ 没有需要提交的改动，跳过 commit。"; return 0
  fi

  echo "→ 提交：$msg"
  git commit -q -m "$msg" || { echo "❌ commit 失败"; return 1; }

  if ! git remote get-url origin >/dev/null 2>&1; then
    echo "⚠️  未关联远端，已提交到本地但未推送。关联：sh $SCRIPT setup <仓库地址>"
    return 0
  fi

  echo "→ 推送到远端…"
  local br; br=$(git rev-parse --abbrev-ref HEAD)
  if git push -u origin "$br" 2>&1 | sed 's/^/   /'; then
    echo "✅ push 完成（$br）"
  else
    echo "❌ push 失败。常见原因：未登录（gh auth login）／SSH key 未加到 GitHub／仓库不存在"
    echo "   本地提交已保留，修好认证后重跑本命令即可。"
    return 1
  fi
}

# ---------- status ----------
cmd_status() {
  ensure_repo || exit 1
  echo "=== 分支 / 远端 ==="
  echo "  分支：$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  echo "  远端：$(git remote get-url origin 2>/dev/null || echo '（未关联）')"
  echo "=== 工作区 ==="
  local n; n=$(git status --porcelain -uall | wc -l | tr -d ' ')
  if [ "$n" = "0" ]; then
    echo "  ✅ 干净，无未提交改动"
  else
    echo "  未提交 $n 项："
    git status --porcelain -uall | head -20 | sed 's/^/    /'
    [ "$n" -gt 20 ] && echo "    …还有 $((n-20)) 项"
  fi
  echo "=== 最近 5 次提交 ==="
  git log --oneline -5 2>/dev/null | sed 's/^/  /'
}

# ---------- 入口 ----------
case "${1:-status}" in
  setup)  shift; cmd_setup "$@" ;;
  pull)   cmd_pull ;;
  push)   shift; cmd_push "$*" ;;
  auto)   shift; cmd_pull && cmd_push "$*" ;;
  status) cmd_status ;;
  -h|--help)  sed -n '2,16p' "$SCRIPT" | sed 's/^#\{1,2\} \{0,1\}//' ;;
  *)      echo "未知子命令：$1（可选 setup/pull/push/auto/status）"; exit 1 ;;
esac
