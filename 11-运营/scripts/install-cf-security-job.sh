#!/bin/bash
# 安装「CF 安全事件每日采集」launchd 任务
#
# 为什么需要它：Cloudflare 的防火墙事件只能回溯 3–4 天，
#   漏一天＝永久缺一天（和站点分析采集同一个坑）。
#
# 为什么不用 WorkBuddy 的晨检任务：
#   这是纯脚本、零 AI 积分。和「DeepSeek 余额记账」同类，
#   走 launchd 更合适，也不占定时任务条数。
#
# 用法：  bash 11-运营/scripts/install-cf-security-job.sh
set -u

BASE="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3"
LABEL="com.theseventhrealm.cf-security"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="/tmp/cf-security.log"

echo "── 安装 $LABEL ──"

if [ ! -x "$PY" ]; then
  echo "  🔴 找不到 Python：$PY"
  exit 1
fi
if [ ! -f "$BASE/11-运营/scripts/cf-security-collect.py" ]; then
  echo "  🔴 找不到采集脚本"
  exit 1
fi
if ! security find-generic-password -a theseventhrealm -s cf-audit -w >/dev/null 2>&1; then
  echo "  🔴 钥匙串里读不到 cf-audit token，先执行："
  echo "     security add-generic-password -a theseventhrealm -s cf-audit -U -w \"<Token>\""
  exit 1
fi

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>$PY $BASE/11-运营/scripts/cf-security-collect.py --days 3 >> $LOG 2>&1</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>21</integer>
    <key>Minute</key><integer>10</integer>
  </dict>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLISTEOF

echo "  ✅ 已写 ${PLIST}（$(wc -c < "$PLIST" | tr -d ' ') 字节）"

launchctl unload "$PLIST" 2>/dev/null
if launchctl load "$PLIST" 2>&1; then
  echo "  ✅ 已加载"
else
  echo "  ⚠️ load 报错，试试：launchctl bootstrap gui/$(id -u) $PLIST"
fi
sleep 1
launchctl list 2>/dev/null | grep -i "theseventhrealm" | sed 's/^/  /'

echo
echo "── 立即试跑一次 ──"
launchctl start "$LABEL" 2>/dev/null
sleep 12
tail -14 "$LOG" 2>/dev/null | sed 's/^/  /' || echo "  （无日志）"

echo
echo "── 验证 ──"
echo "  任务：每日 21:10 自动采最近 3 天（幂等，重复跑不重复记）"
echo "  数据：11-运营/data/cf-security.csv"
echo "  看趋势：$PY 11-运营/scripts/cf-security-collect.py --report"
