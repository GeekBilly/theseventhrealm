#!/bin/zsh
# ============================================================
# 每日积分取数 · 免登录版（2026-10-09 · 定稿）
# ------------------------------------------------------------
# 取什么：WorkBuddy 官方「个人中心 · 用量」的真实余额 + 近 7 日逐日消耗。
# 怎么取：CDP 直连「常驻无头 Chrome」里已登录的那个标签。日常零操作、零人工。
#
# 三代方案的演进（完整排障记录见 11-运营/自动化与取数手册.md）：
#   v1 agent-browser            → daemon 的标签恒为 about:blank，eval 打在空白页上；
#                                 登录失效后把登录页 HTML 当 JSON —— 晨检连错 9 天的真凶
#   v2 无头 Chrome 复用 profile → 登录态含 session cookie，关浏览器即失效，必跳登录页
#   v3 curl + cookie / header   → 实测网关(APISIX)返回 401：真实凭据是浏览器自动附加的
#                                 httpOnly cookie，进程外拿不到有效值，此路不通
#   v4 常驻 Chrome + CDP（当前）→ 登录态活在浏览器进程里，就让它一直活着
#
# 首次 / 电脑重启后：11-运营/scripts/start-credits-browser.sh（扫码一次）
# 日常取数（免登录）：11-运营/scripts/fetch-credits.sh
#
# 退出码：0=成功 / 1=需要登录 / 5=取数失败
# ============================================================

set -u

PORT="${1:-9222}"
DIR="$(cd "$(dirname "$0")" && pwd)"
NODE="$(ls -d /Users/billyhou/.workbuddy/binaries/node/versions/*/bin/node 2>/dev/null | tail -1)"
URL="https://www.workbuddy.cn/profile/plans-usage"

[ -n "$NODE" ] || { echo '{"error":"NO_NODE"}'; exit 4; }

port_up() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/version" 2>/dev/null | grep -q "webSocketDebuggerUrl"
}
taburl() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/list" 2>/dev/null \
    | grep -oE '"url": "https://www\.workbuddy\.cn/[^"]*"' | head -1
}

port_up || {
  echo '{"error":"NEED_LOGIN","hint":"取数用的常驻 Chrome 没在跑。在【你自己的终端】跑一次：11-运营/scripts/start-credits-browser.sh —— 它会后台起一个无头 Chrome 并截二维码，扫一次码后长期免登录"}'
  exit 1
}

# 常驻 Chrome 在，但标签没停在积分页（比如还在登录页）→ 先导航过去
case "$(taburl)" in
  *"profile/plans-usage"*) ;;
  *)
    "$NODE" - "$PORT" "$URL" <<'NODEEOF'
const [port, url] = process.argv.slice(2);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
(async () => {
  const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = list.find(t => t.type === 'page' && /workbuddy\.cn/.test(t.url || ''))
             || list.find(t => t.type === 'page' && !/^chrome|extension/.test(t.url || ''));
  if (!page) process.exit(1);
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws')); });
  let id = 0;
  const send = (m, p) => new Promise((r) => {
    const my = ++id;
    const h = (ev) => { const x = JSON.parse(ev.data); if (x.id === my) { ws.removeEventListener('message', h); r(x); } };
    ws.addEventListener('message', h); ws.send(JSON.stringify({ id: my, method: m, params: p }));
  });
  await send('Page.enable', {});
  await send('Page.navigate', { url });
  await sleep(6000);
  ws.close();
})().catch(() => process.exit(1));
NODEEOF
    ;;
esac

case "$(taburl)" in
  *"/login"*)
    echo '{"error":"NEED_LOGIN","hint":"登录态已失效。在【你自己的终端】跑：11-运营/scripts/start-credits-browser.sh 重新扫码一次"}'
    exit 1 ;;
esac

OUT="$("$NODE" "$DIR/fetch-credits-cdp.mjs" "${PORT}" 2>&1 | tail -1)"
echo "$OUT"

# 成功则落盘，供 build-dashboard.py 直接消费（默认 /tmp/credits-real.json，可用第二参数覆盖）
SAVE="${2:-/tmp/credits-real.json}"
case "$OUT" in
  *'"ok":true'*) printf '%s\n' "$OUT" > "$SAVE"; exit 0 ;;
  *) exit 5 ;;
esac
