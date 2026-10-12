#!/bin/zsh
# 第七境 · 一键装载「MacBook 每日自动同步」任务
# 双击本文件即可运行；运行完窗口会停住让你看结果，按回车关闭。

echo "=============================================="
echo " 装载 MacBook 每日 02:30 自动同步（gitsync）"
echo "=============================================="
echo

PLIST="$HOME/Library/LaunchAgents/com.theseventhrealm.gitsync.plist"

if [ ! -f "$PLIST" ]; then
  echo "❌ 找不到任务文件："
  echo "   $PLIST"
  echo "   （请确认先把它复制到 ~/Library/LaunchAgents/）"
  echo
  read "?按回车关闭…"
  exit 1
fi

echo "→ 先卸掉可能存在的旧装载（忽略报错）"
launchctl unload -w "$PLIST" 2>/dev/null

echo "→ 装载中…"
if launchctl load -w "$PLIST"; then
  echo "✅ 装载命令执行成功"
else
  echo "⚠️ 装载返回非零，继续检查状态："
fi
echo

echo "--- 检查 1：任务是否在册 ---"
if launchctl list | grep -q "com.theseventhrealm.gitsync"; then
  launchctl list | grep "com.theseventhrealm.gitsync"
  echo "✅ 已装载（第一列是 PID，'-' 表示当前没在跑，正常）"
else
  echo "❌ 没有出现在 launchctl list 里"
fi
echo

echo "--- 检查 2：立即试跑一次（会真的 pull + 提交 + push）---"
launchctl kickstart "gui/$(id -u)/com.theseventhrealm.gitsync" 2>/dev/null \
  && echo "已触发，等 10 秒后看日志…" \
  || echo "⚠️ 触发失败（不影响定时，02:30 仍会自己跑）"
sleep 10
echo

LOG="$HOME/WorkBuddy/2026-09-25-15-56-17/11-运营/logs/gitsync.log"
ERR="$HOME/WorkBuddy/2026-09-25-15-56-17/11-运营/logs/gitsync.err"
echo "--- 检查 3：日志 ---"
[ -f "$LOG" ] && { echo "【$LOG】"; tail -12 "$LOG"; } || echo "（还没有 log，正常，第一次跑完才有）"
[ -s "$ERR" ] && { echo "【$ERR】"; tail -12 "$ERR"; }
echo
echo "=============================================="
echo " 完成。之后每天 02:30 会自动同步一次。"
echo " 想手动跑：sh 11-运营/scripts/qj-sync.sh auto"
echo "=============================================="
read "?按回车关闭窗口…"
