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
PORT="${1:-9226}"
SRC="$HOME/.workbuddy/browser-profile"
PROFILE="$HOME/.workbuddy/xhs-creator"
TARGET='https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image'

port_up() {
  curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/json/version" 2>/dev/null \
    | grep -q "webSocketDebuggerUrl"
}

# ---- 1. 同步登录态到独立 profile -------------------------------------------
mkdir -p "$PROFILE/Default"
if [ -f "$SRC/Local State" ]; then
  cp "$SRC/Local State" "$PROFILE/Local State"
fi
if [ -f "$SRC/Default/Cookies" ]; then
  cp "$SRC/Default/Cookies" "$PROFILE/Default/Cookies"
fi
[ -d "$SRC/Default/Local Storage" ] && cp -R "$SRC/Default/Local Storage" "$PROFILE/Default/" 2>/dev/null

HAS_XHS=$(/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 - <<'PY' 2>/dev/null
import sqlite3, os
p = os.path.expanduser("~/.workbuddy/xhs-creator/Default/Cookies")
if not os.path.exists(p):
    print(0); raise SystemExit
c = sqlite3.connect(p)
try:
    print(c.execute("select count(*) from cookies where host_key like '%xiaohongshu%'").fetchone()[0])
except Exception:
    print(0)
finally:
    c.close()
PY
)
echo "已同步 profile：$PROFILE（小红书 cookie ${HAS_XHS} 条）"
[ "${HAS_XHS:-0}" -eq 0 ] && echo "WARN 源 profile 里没有小红书 cookie，起窗后多半要扫码"

# ---- 2. 已就绪就复用 -------------------------------------------------------
if port_up; then
  echo "OK 端口 ${PORT} 已就绪，无需重开"
  exit 0
fi

# ---- 3. 启动（非沙箱 + 常驻）----------------------------------------------
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
    break
  fi
done

wait
