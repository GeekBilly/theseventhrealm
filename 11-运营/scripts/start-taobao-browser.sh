#!/bin/zsh
# ============================================================
# 启动「淘宝卖家后台专用」的常驻有头 Chrome（端口 9223，独立 profile）
# ------------------------------------------------------------
# 为什么不复用 9222：9222 是 WorkBuddy 积分取数专用的无头浏览器，
#   淘宝登录会往 profile 里灌大量 cookie，且无头窗口用户没法扫码/收短信 → 必须独立。
# 为什么必须有头：本机无头 Chrome 截图会卡死（见长期约定 #39），且登录交互需要真人。
#
# 用法：11-运营/scripts/start-taobao-browser.sh
# 之后：用户在弹出的窗口里登录淘宝 → 告诉 Agent → Agent 用 tb-read.mjs 读页面
# ============================================================

set -u

CHROME="/Applications/Google Chrome.app"
PORT="${1:-9223}"
PROFILE="${HOME}/.workbuddy/taobao-browser-profile"
TARGET='https://myseller.taobao.com/home.htm/SellManage/in_stock?current=1&pageSize=20'

port_up() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/version" 2>/dev/null \
    | grep -q "webSocketDebuggerUrl"
}

mkdir -p "$PROFILE"

if port_up; then
  echo "OK 端口 ${PORT} 已就绪，无需重开"
  exit 0
fi

echo "正在启动独立 Chrome（端口 ${PORT}）…"
open -a "$CHROME" --args \
  --remote-debugging-port="$PORT" \
  --remote-allow-origins='*' \
  --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check \
  "$TARGET"

for i in $(seq 1 15); do
  sleep 2
  if port_up; then
    echo "OK 已就绪：http://127.0.0.1:${PORT}"
    exit 0
  fi
done

echo "ERR 端口未就绪"
exit 2
