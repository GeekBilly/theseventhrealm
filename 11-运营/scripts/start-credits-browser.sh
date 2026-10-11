#!/bin/zsh
# ============================================================
# 启动「取数专用」的常驻无头 Chrome（后台运行，不弹窗）
# ------------------------------------------------------------
# 为什么必须常驻：站点登录走 Keycloak，登录态里的 AUTH_SESSION_ID 是 session cookie，
# 浏览器进程一关就失效 —— 所以「复用 profile 起新浏览器」这条路走不通（实测必跳登录页）。
# 只有让一个 Chrome 一直活着，登录态才能保持，取数才能免登录。
#
# 流程（只在首次 / 电脑重启后需要）：
#   1) 跑本脚本 → 后台起无头 Chrome，打开登录页，并自动截一张二维码图
#   2) 用手机微信扫图里的码完成登录
#   3) 之后 fetch-credits.sh 直连这个常驻 Chrome 取数，日常零操作
#
# 用法：11-运营/scripts/start-credits-browser.sh
# ============================================================

set -u

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="${HOME}/.workbuddy/browser-profile"
PORT="${1:-9222}"
DIR="$(cd "$(dirname "$0")" && pwd)"
NODE="$(ls -d /Users/billyhou/.workbuddy/binaries/node/versions/*/bin/node 2>/dev/null | tail -1)"
PY="/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
LOGIN_URL='https://www.workbuddy.cn/login/?platform=usercenter&state=0&redirect_uri=https%3A%2F%2Fwww.workbuddy.cn%2Fprofile%2Fplans-usage'
SHOT="/tmp/wb-login-qr.png"

[ -x "$CHROME" ] || { echo '{"error":"NO_CHROME"}'; exit 4; }
[ -n "$NODE" ]   || { echo '{"error":"NO_NODE"}'; exit 4; }
mkdir -p "$PROFILE"

port_up() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/version" 2>/dev/null | grep -q "webSocketDebuggerUrl"
}
taburl() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/list" 2>/dev/null \
    | grep -oE '"url": "https://www\.workbuddy\.cn/[^"]*"' | head -1
}

# 已经有一个登录好的常驻 Chrome —— 不用重复起
if port_up; then
  case "$(taburl)" in
    *"profile/plans-usage"*)
      echo "✓ 常驻 Chrome 已在运行且已登录，直接跑 11-运营/scripts/fetch-credits.sh 即可"
      exit 0 ;;
  esac
fi

# 起常驻无头 Chrome：用 start_new_session 脱离进程组，避免被父进程/终端关闭连带杀掉
"$PY" - "$CHROME" "$PROFILE" "$PORT" "$LOGIN_URL" <<'PYEOF'
import subprocess, sys
chrome, profile, port, url = sys.argv[1:5]
subprocess.Popen([
    chrome, "--headless=new",
    "--remote-debugging-port=" + port,
    "--user-data-dir=" + profile,
    "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
    "--no-first-run", "--no-default-browser-check",
    "--window-size=1280,1000",
    url,
], stdout=open("/tmp/chrome-credits-daemon.log", "wb"),
   stderr=subprocess.STDOUT,
   start_new_session=True)
print("Chrome 已在后台启动（脱离进程组，端口 %s）" % port)
PYEOF

for i in $(seq 1 30); do
  sleep 1
  port_up && break
done
port_up || { echo '{"error":"CHROME_NOT_UP","hint":"看 /tmp/chrome-credits-daemon.log"}'; exit 5; }

sleep 8
"$NODE" "$DIR/fetch-credits-shot.mjs" "${PORT}" "${SHOT}"

if [ -f "$SHOT" ]; then
  echo
  echo "📱 二维码已截图：${SHOT}"
  echo "   请用手机微信扫描登录。登录成功后跑：11-运营/scripts/fetch-credits.sh"
else
  echo "（截图失败，可手动在浏览器打开 ${LOGIN_URL} 登录）"
fi
