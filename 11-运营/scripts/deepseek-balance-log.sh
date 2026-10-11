#!/bin/bash
# DeepSeek 余额记账 · launchd 每日调用
# 纯 API，不启动浏览器、不唤醒 AI，零 WorkBuddy 积分成本。
# 钥匙串服务名：deepseek-api
set -u

CSV="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/data/deepseek-balance.csv"
PY="/usr/bin/python3"

KEY="$(/usr/bin/security find-generic-password -s deepseek-api -w 2>/dev/null || true)"
if [ -z "$KEY" ]; then
  echo "$(/bin/date '+%F %T') ERR no-keychain-item(deepseek-api)"
  exit 1
fi

JSON="$(/usr/bin/curl -s --noproxy '*' --max-time 20 \
  -H "Authorization: Bearer ${KEY}" \
  "https://api.deepseek.com/user/balance" 2>/dev/null)"

if ! echo "$JSON" | grep -q "balance_infos"; then
  echo "$(/bin/date '+%F %T') ERR api: ${JSON:0:200}"
  exit 1
fi

export DS_CSV="$CSV"
printf '%s' "$JSON" | "$PY" -c '
import json, sys, datetime, csv, os
CSV = os.environ.get("DS_CSV")
d = json.load(sys.stdin)
b = (d.get("balance_infos") or [{}])[0]
now = datetime.datetime.now()
os.makedirs(os.path.dirname(CSV), exist_ok=True)
new = not os.path.exists(CSV)
with open(CSV, "a", newline="") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["date","time","source","total","granted","toppedUp","isAvailable"])
    w.writerow([now.strftime("%Y-%m-%d"), now.strftime("%H:%M"), "api",
                b.get("total_balance"), b.get("granted_balance"),
                b.get("topped_up_balance"), d.get("is_available")])
print("total=%s granted=%s" % (b.get("total_balance"), b.get("granted_balance")))
'
# 刷新图形化看板（纯本地，零成本）
"$PY" "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/scripts/build-balance-chart.py" 2>&1 | tail -1

echo "$(/bin/date '+%F %T') OK"
