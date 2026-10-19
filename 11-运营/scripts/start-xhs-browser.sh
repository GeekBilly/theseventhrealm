#!/bin/zsh
# ============================================================
# 启动「小红书创作者中心」专用有头调试 Chrome（端口 9226，profile ~/.workbuddy/xhs-creator）
# ------------------------------------------------------------
# 端口分配（不要混用）：
#   9222 = WorkBuddy 积分取数专用（**无头**，永远不可见，不能被占用做发布类任务）
#   9223 = 淘宝卖家后台
#   9226 = 小红书创作者中心（本脚本）
#
# 登录态从哪来：~/.workbuddy/browser-profile（9222 那个 profile，里面已有 creator 会话）
#   → 本脚本把它的 Local State + Default/Cookies + Default/Local Storage 复制到
#     ~/.workbuddy/xhs-creator，由 Chrome 自己解密。
#   ⚠️ **不要试图自己解密 cookie**：2026-10-18 实测，拿 Keychain 的
#      「Chrome Safe Storage」密钥（-a "Chrome"）+ PBKDF2 salt='saltysalt' 1003 16 字节
#      解出来只有**第 2 块之后正确，第 1 块（前 16 字节）永远是乱码**（IV 不是常见那几种）。
#      所以每条 cookie 都缺头，不可用。让 Chrome 自己解是唯一可行路径。
#
# 🔴 启动方式（两个条件缺一不可，2026-10-18 实测）：
#   ① 必须 **非沙箱** 执行（dangerouslyDisableSandbox），否则
#      "Failed to initialize sandbox" → GPU 进程退出 → 浏览器直接死。
#   ② 用 **二进制 + 后台常驻任务**（命令尾部 `wait`），不能前台 `&`（随会话结束被回收），
#      也不能 `open -a`/`open -n`（参数会被已运行的 Chrome 实例吞掉，端口不生效）。
#   ③ 必须带 `--no-sandbox --disable-gpu-sandbox`。
#
# 用法（在 Agent 的 Bash 工具里）：
#   dangerouslyDisableSandbox=true, run_in_background=true 执行本脚本
#   然后：CDP_PORT=9226 python3 /tmp/xhs-cdp.py eval "..." （工具脚本：/tmp/xhs-cdp.py）
# ============================================================

set -u

CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SRC="$HOME/.workbuddy/browser-profile"
PROFILE="$HOME/.workbuddy/xhs-creator"
TARGET='https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image'

# 参数：start-xhs-browser.sh [端口] [--force-sync]
PORT=""
FORCE_SYNC=0
for _a in "$@"; do
  case "$_a" in
    --force-sync) FORCE_SYNC=1 ;;
    *) PORT="$_a" ;;
  esac
done
PORT="${PORT:-9226}"

port_up() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/version" 2>/dev/null \
    | grep -q "webSocketDebuggerUrl"
}

# ---- 1. 同步登录态到独立 profile -------------------------------------------
# 🔴 2026-10-20 加固：默认**不再无条件覆盖**（此前每次启动都 cp，实测会丢登录态）
#    根因：源 profile（9222 积分取数专用）里**只有小红书 cookie、没有抖音 cookie**，
#          无条件 cp 会把 9226 里已登录的抖音 cookie（41+11 条）整个抹掉；
#          即便只登了小红书，也会被 9222 那份**旧快照**覆盖成掉登录状态。
#    现在：目标 profile 里只要还有这两个站的 cookie 就**跳过同步**；
#          只有确实要从 9222 重新拉登录态时才显式加 --force-sync。
#    另：任何一次真正覆盖前，都先把现有 Cookies 备份到 ~/.workbuddy/backups/。
mkdir -p "$PROFILE/Default"

COUNT_CK() {
  [ -f "$PROFILE/Default/Cookies" ] || { echo 0; return; }
  /Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 - "$PROFILE" <<'PY' 2>/dev/null
import sqlite3, sys, os
p = os.path.join(sys.argv[1], "Default/Cookies")
try:
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    print(c.execute(
        "select count(*) from cookies "
        "where host_key like '%xiaohongshu%' or host_key like '%douyin%'").fetchone()[0])
except Exception:
    print(0)
PY
}

HAS_XHS=$(COUNT_CK)
if [ "${HAS_XHS:-0}" -gt 0 ] && [ "$FORCE_SYNC" -ne 1 ]; then
  echo "OK profile 里已有 ${HAS_XHS} 条小红书/抖音 cookie → **跳过同步**，保留现有登录态"
  echo "   如需从 9222 重新拉登录态：zsh $0 ${PORT} --force-sync"
else
  if [ -f "$PROFILE/Default/Cookies" ]; then
    BK="$HOME/.workbuddy/backups/xhs-creator-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BK"
    cp "$PROFILE/Default/Cookies" "$BK/Cookies" 2>/dev/null
    cp "$PROFILE/Local State" "$BK/Local-State" 2>/dev/null
    echo "已备份现有登录态 → $BK"
  fi
  [ -f "$SRC/Local State" ] && cp "$SRC/Local State" "$PROFILE/Local State"
  [ -f "$SRC/Default/Cookies" ] && cp "$SRC/Default/Cookies" "$PROFILE/Default/Cookies"
  [ -d "$SRC/Default/Local Storage" ] && cp -R "$SRC/Default/Local Storage" "$PROFILE/Default/" 2>/dev/null
  echo "已从 9222 profile 同步登录态到 $PROFILE"
fi
echo "profile：$PROFILE（小红书+抖音 cookie $(COUNT_CK) 条）"

# ---- 2. 兜底：保证抖音标签存在 --------------------------------------------
# 🔴 2026-10-20 冷启动实测抓到的真问题（不修明天就会丢数据）：
#    TARGET 只指向小红书发布页 ⇒ Chrome 冷启动后**只有小红书一个标签**，
#    dy-stats.sh 报 NO_DY_TAB ⇒ 当天抖音数据**永久缺失**（7 天滚动窗口不可回溯）。
#    实测：关掉 Chrome 用 launchctl 拉起后，小红书采集正常、抖音 NO_DY_TAB。
#    所以「已就绪」和「刚启动」两条路径都要确认抖音标签在。
DY_HOME='https://creator.douyin.com/creator-micro/home'
ensure_dy_tab() {
  local has
  has=$(curl -s --noproxy '*' --max-time 5 "http://127.0.0.1:${PORT}/json/list" 2>/dev/null \
        | grep -c "creator\.douyin\.com")
  if [ "${has:-0}" -eq 0 ]; then
    curl -s --noproxy '*' --max-time 10 -X PUT \
      "http://127.0.0.1:${PORT}/json/new?${DY_HOME}" >/dev/null 2>&1
    echo "已补开抖音标签（冷启动不会自动恢复，必须手动补）"
  else
    echo "抖音标签已存在，无需补开（匹配 ${has} 行）"
  fi
}

# ---- 3. 已就绪就复用 -------------------------------------------------------
if port_up; then
  echo "OK 端口 ${PORT} 已就绪，无需重开"
  ensure_dy_tab
  exit 0
fi

# ---- 4. 启动（非沙箱 + 常驻）----------------------------------------------
echo "正在启动小红书专用 Chrome（端口 ${PORT}）…"
"$CHROME_BIN" \
  --user-data-dir="$PROFILE" \
  --profile-directory="Default" \
  --remote-debugging-port="$PORT" \
  --remote-allow-origins='*' \
  --no-first-run --no-default-browser-check \
  --no-sandbox --disable-gpu-sandbox \
  --window-size=1440,960 \
  "$TARGET" > "/tmp/xhs-chrome-port${PORT}.log" 2>&1 &

for i in $(seq 1 15); do
  sleep 2
  if port_up; then
    echo "OK 已就绪：http://127.0.0.1:${PORT}"
    ensure_dy_tab
    break
  fi
done

wait
