#!/bin/zsh
# 常开 Chrome 方案：通过远程调试端口接管用户正在用的 Chrome 取数
# 前提：Chrome 以调试端口启动，且停在 workbuddy.cn/profile/plans-usage 并已登录
#
# 用法：11-运营/scripts/fetch-credits-cdp.sh [端口，默认 9222]
#
# 2026-10-05 重写：原实现用 agent-browser connect + tab new，会绑死在自己新建的
# about:blank 目标上；而 workbuddy.cn 的登录态按标签页存（sessionStorage），
# 新标签没有登录态 → fetch 必然 Failed to fetch。
# 现改为 fetch-credits-cdp.mjs：自己从 /json/list 挑中「已登录的那个标签」直连 CDP。

set -u
PORT="${1:-9222}"
DIR="$(cd "$(dirname "$0")" && pwd)"
NODE="/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin/node"

exec "$NODE" "$DIR/fetch-credits-cdp.mjs" "$PORT"
