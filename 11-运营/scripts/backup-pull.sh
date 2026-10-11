#!/bin/zsh
# backup-pull.sh —— 第七境 · Mac mini 端（纯备份机）每日自动备份
#
# 链路：MacBook（唯一写入端）--push--> GitHub 私有仓库 --每日 pull--> Mac mini 外接移动硬盘
#
# 用法
#   sh backup-pull.sh                 正常跑一次（launchd 每天调用）
#   sh backup-pull.sh --once          同上，但输出更详细，便于手动验证
#   BACKUP_ROOT=/Volumes/XXX/备份 sh backup-pull.sh --once
#
# 首次安装（在 Mac mini 的「终端」里手动跑一遍）
#   1) 改下面的 REPO_URL 和 BACKUP_ROOT
#   2) sh backup-pull.sh --once           → 应看到「clone 完成」
#   3) cp com.theseventhrealm.backup.plist ~/Library/LaunchAgents/
#      launchctl load -w ~/Library/LaunchAgents/com.theseventhrealm.backup.plist
#
# 设计要点
#   - Mac mini **从不 push**，所以一律 --ff-only，不会产生 merge 冲突
#   - 移动硬盘没挂载时写日志并以非零码退出（launchd 会重试），绝不静默「假成功」
#   - 若检测到有人在 mini 上改了工作区，停止备份并告警（会破坏「单一写入端」前提）
#   - 零积分：只用 git，不调模型

set -uo pipefail

# ============ 配置区（在 Mac mini 上部署前必须改这两行）============
REPO_URL="${REPO_URL:-git@github.com:YOUR_NAME/YOUR_REPO.git}"
BACKUP_ROOT="${BACKUP_ROOT:-/Volumes/YOUR_DISK/第七境备份}"
REPO_DIR="$BACKUP_ROOT/repo"
LOG="$BACKUP_ROOT/backup.log"
# ================================================================

VERBOSE=0
[ "${1:-}" = "--once" ] && VERBOSE=1

log() {
  local line="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$line"
  [ -d "$BACKUP_ROOT" ] && echo "$line" >> "$LOG" 2>/dev/null
}

fail() {
  log "❌ $*"
  exit 1
}

# ---------- 1. 移动硬盘挂载检查 ----------
if [ ! -d "$BACKUP_ROOT" ]; then
  # 硬盘往往挂在 /Volumes 下的一层 BACKUP_ROOT 父目录里，先看看父目录在不在
  parent="$(dirname "$BACKUP_ROOT")"
  if [ ! -d "$parent" ]; then
    echo "❌ 移动硬盘未挂载：$parent 不存在"
    echo "   （这次是由 launchd 调用的，为避免刷日志，此处仅输出到 stderr）"
    exit 1
  fi
  mkdir -p "$BACKUP_ROOT" 2>/dev/null || {
    echo "❌ 无法创建备份目录 $BACKUP_ROOT（硬盘只读或未挂载）"
    exit 1
  }
  log "→ 已创建备份目录 $BACKUP_ROOT"
fi

# ---------- 2. git 可用性 ----------
command -v git >/dev/null 2>&1 || fail "本机没有 git"

# ---------- 3. 首次 clone / 后续 pull ----------
if [ ! -d "$REPO_DIR/.git" ]; then
  log "→ 首次备份：clone 到 $REPO_DIR"
  if git clone --quiet "$REPO_URL" "$REPO_DIR" 2>&1 | sed 's/^/   /'; then
    log "✅ 首次备份完成"
  else
    fail "clone 失败。检查：①REPO_URL 是否正确 ②SSH key 是否加了本机的公钥到 GitHub ③仓库是否存在"
  fi
else
  cd "$REPO_DIR" || fail "无法进入 $REPO_DIR"

  # 🔴 单一写入端前提：mini 上绝不能有人改文件
  dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [ "$dirty" != "0" ]; then
    fail "检测到 $REPO_DIR 有 $dirty 项本地改动。Mac mini 是**只读备份机**，不该有人改它。\
请先查明改动来源（git status），确认后手动 git checkout . 恢复，否则每日备份会被阻塞。"
  fi

  log "→ 拉取远端（$(git remote get-url origin 2>/dev/null || echo '?')）"
  if out=$(git pull --ff-only --quiet 2>&1); then
    head=$(git log -1 --format='%h %s' 2>/dev/null)
    n=$(git ls-files | wc -l | tr -d ' ')
    size=$(du -sh "$REPO_DIR" 2>/dev/null | cut -f1)
    log "✅ 备份完成 · 最新 $head · 共 $n 个文件 · $size"
    [ "$VERBOSE" = "1" ] && echo "$out"
  else
    fail "pull 失败：$out
   常见原因：①认证过期（重配 SSH / gh auth login）②检测到非快进（有人在 mini 上提交过）"
  fi
fi

# ---------- 4. 顺带记录本机身份，便于排障 ----------
log "   主机 $(scutil --get ComputerName 2>/dev/null || hostname) · git $(git --version | awk '{print $3}')"
exit 0
