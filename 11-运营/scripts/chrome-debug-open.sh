#!/bin/zsh
# 以「远程调试端口」启动 Chrome（常开方案：只做一次，之后 Chrome 一直开着不用再管）
# 若 Chrome 已在运行且没带端口，脚本会提示你先 Cmd+Q 退出再执行本脚本。
#
# 用法：11-运营/scripts/chrome-debug-open.sh [端口，默认 9222]

set -u
PORT="${1:-9222}"
CHROME="/Applications/Google Chrome.app"

port_open() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/version" 2>/dev/null \
    | grep -q "webSocketDebuggerUrl"
}

if port_open; then
  echo "✅ 调试端口 ${PORT} 已就绪，无需任何操作（每天定时任务会自动复用）"
  exit 0
fi

if pgrep -f "MacOS/Google Chrome" >/dev/null 2>&1; then
  echo "⚠️  Chrome 正在运行但没开调试端口。"
  echo "    请先 Cmd+Q 完全退出 Chrome，然后重新执行本脚本："
  echo "      $(cd "$(dirname "$0")" && pwd)/chrome-debug-open.sh"
  exit 1
fi

echo "正在以调试端口启动 Chrome…"
open -a "$CHROME" --args --remote-debugging-port="$PORT" --remote-allow-origins="*"

for i in $(seq 1 12); do
  sleep 2
  if port_open; then
    echo "✅ 已启动，端口 ${PORT} 就绪。以后只要电脑不重启，就不用再管了。"
    exit 0
  fi
done

echo "❌ 端口未就绪，请手动确认 Chrome 是否启动成功"
exit 2
