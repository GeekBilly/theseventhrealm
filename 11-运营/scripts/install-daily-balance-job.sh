#!/bin/bash
# 安装 DeepSeek 余额每日记账（系统级定时，零 AI 成本）
# 用法：在你自己的终端里跑一次（不要在 AI 会话里跑，AI 环境无权注册定时任务）
#   bash /Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/scripts/install-daily-balance-job.sh
set -u

LABEL="com.theseventhrealm.deepseek-balance"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
SCRIPT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/scripts/deepseek-balance-log.sh"

echo "1) 先用 launchd（macOS 原生）"
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null
if launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null; then
  echo "   ✓ launchd 已注册"
  MODE="launchd"
else
  echo "   ✗ launchd 注册失败，改用 cron"
  if ( crontab -l 2>/dev/null; echo "0 21 * * * ${SCRIPT} >> /tmp/deepseek-balance.log 2>&1" ) | grep -v '^$' | crontab - 2>/dev/null; then
    echo "   ✓ cron 已注册"
    MODE="cron"
  else
    echo "   ✗ cron 也失败。请检查系统设置 → 隐私与安全性 → 完全磁盘访问权限"
    exit 1
  fi
fi

echo ""
echo "2) 立即触发一次，验证 launchd/cron 环境下能否读到钥匙串"
if [ "$MODE" = "launchd" ]; then
  launchctl kickstart -k "gui/$(id -u)/${LABEL}" 2>/dev/null
fi
[ "$MODE" = "cron" ] && "$SCRIPT" >> /tmp/deepseek-balance.log 2>&1
sleep 4

echo ""
echo "3) 结果"
echo "--- 日志 ---"
tail -3 /tmp/deepseek-balance.log 2>/dev/null || echo "(无日志)"
echo "--- 错误 ---"
tail -3 /tmp/deepseek-balance.err 2>/dev/null || true
echo "--- CSV 末尾 ---"
tail -2 /Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/data/deepseek-balance.csv

if grep -q "no-keychain-item" /tmp/deepseek-balance.log 2>/dev/null; then
  echo ""
  echo "⚠️ 钥匙串读取被拒（launchd 进程无权访问该项）。修一下（会读取并重写该项，加 -A 允许所有进程访问）："
  echo "   security add-generic-password -a deepseek -s deepseek-api -U -A -w \"\$(security find-generic-password -s deepseek-api -w)\""
  echo "   然后重新跑本脚本。"
fi
