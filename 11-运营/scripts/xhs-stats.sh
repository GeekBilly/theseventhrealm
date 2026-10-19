#!/bin/zsh
# 小红书创作服务平台 · 每日数据采集
# 前提：先跑 start-xhs-browser.sh 起 Chrome（9226）并登录一次。
# 输出：单行 JSON；同时写 11-运营/data/xhs-stats.json + 两份 CSV。
# 失败一次即降级调用方不要再试（多半是掉登录或 Chrome 没开）。

NODE="${NODE_BIN:-/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-6/bin/node}"
DIR="$(cd "$(dirname "$0")" && pwd)"

if ! curl -s --max-time 3 "http://127.0.0.1:${1:-9226}/json/version" >/dev/null 2>&1; then
  echo '{"error":"NO_DEBUG_PORT","hint":"Chrome 未以 --remote-debugging-port=9226 启动，先跑 start-xhs-browser.sh"}'
  exit 1
fi

exec "$NODE" "$DIR/xhs-stats.mjs" "${1:-9226}"
