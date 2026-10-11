#!/usr/bin/env bash
# DeepSeek API 用量抓取
# 用法：fetch-deepseek-usage.sh
# 输出：单行 JSON（余额/累计消费/近30天请求数/tokens/API key 数），并把原始文本落到 /tmp/
# 失败：{"error":"NEED_LOGIN"} —— 说明 Chrome 配置档快照没带登录态，退出 Chrome 后重跑
set -uo pipefail

AB_HOME="/Users/billyhou/.workbuddy/binaries/node/workspace"
export PATH="$AB_HOME/bin:$PATH"
REPORT_DIR="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/reports"
RAW_USAGE="/tmp/ds-usage-raw.txt"
RAW_KEYS="/tmp/ds-keys-raw.txt"

# ── 主通道：官方余额 API（秒级，无需浏览器）────────────────────
# 前置：把 API key 存进钥匙串（只需一次）。
# ⚠️ 不要用 -w "sk-明文" 的形式——那会把 key 留在 shell 历史里。
#    改用交互式输入（回车后提示 Password:，输入不回显）：
#      security add-generic-password -a deepseek -s deepseek-api -U -w
DS_KEY="$(security find-generic-password -s deepseek-api -w 2>/dev/null || true)"
if [ -n "$DS_KEY" ]; then
  BAL_JSON="$(curl -s --noproxy '*' --max-time 20 \
    -H "Authorization: Bearer ${DS_KEY}" \
    "https://api.deepseek.com/user/balance" 2>/dev/null)"
  if echo "$BAL_JSON" | grep -q "balance_infos"; then
    echo "$BAL_JSON" | /usr/bin/python3 -c '
import json,sys
d=json.load(sys.stdin)
infos=d.get("balance_infos",[])
out={"ok":True,"source":"api","isAvailable":d.get("is_available")}
for b in infos:
    c=b.get("currency")
    out.setdefault("balances",{})[c]={
        "total":b.get("total_balance"),
        "granted":b.get("granted_balance"),
        "toppedUp":b.get("topped_up_balance"),
    }
print(json.dumps(out,ensure_ascii=False))
'
    exit 0
  fi
fi

# ── 备用通道：浏览器复用本机 Chrome 登录态（慢且不稳定）────────
command -v agent-browser >/dev/null 2>&1 || { echo '{"error":"NO_AGENT_BROWSER"}'; exit 3; }

# profile 参数需重启守护进程才生效
agent-browser close --all >/dev/null 2>&1
sleep 3

# 关键：--profile Default 首次 open 要复制配置档，必须前台跑完（哪怕超时），
# 否则守护进程未就绪，后续 eval 全部返回空。
open_and_wait() {
  local target="$1"
  agent-browser --profile Default open "$target" >/dev/null 2>&1
  local u=""
  for i in $(seq 1 45); do
    sleep 4
    u="$(agent-browser eval 'location.href' 2>/dev/null | tail -1 | tr -d '"')"
    case "$u" in
      *"$target"*) return 0 ;;
      *"/login"*|*"signin"*) return 1 ;;
    esac
  done
  return 2
}

if ! open_and_wait "https://platform.deepseek.com/usage"; then
  echo '{"error":"NEED_LOGIN"}'
  agent-browser close --all >/dev/null 2>&1
  exit 1
fi
sleep 3

agent-browser eval 'document.body.innerText.replace(/\n+/g," | ")' 2>/dev/null | tail -1 > "$RAW_USAGE"
open_and_wait "https://platform.deepseek.com/api_keys" || true
sleep 3
agent-browser eval 'document.body.innerText.replace(/\n+/g," | ")' 2>/dev/null | tail -1 > "$RAW_KEYS"

agent-browser close --all >/dev/null 2>&1

/usr/bin/python3 - "$RAW_USAGE" "$RAW_KEYS" <<'PY'
import json, re, sys, os
u = open(sys.argv[1], encoding="utf-8", errors="ignore").read() if os.path.exists(sys.argv[1]) else ""
k = open(sys.argv[2], encoding="utf-8", errors="ignore").read() if os.path.exists(sys.argv[2]) else ""

if "充值余额" not in u:
    print(json.dumps({"error": "NEED_LOGIN"}, ensure_ascii=False))
    raise SystemExit

def grab(pat, src, group=1):
    m = re.search(pat, src)
    return m.group(group).strip() if m else None

bal   = grab(r"充值余额\s*\|?\s*(?:余额预警[^|]*\|)?\s*¥?([\d.,<]+)", u)
total = grab(r"累计消费金额\s*\|?\s*¥?([\d.,<]+)", u)
reqs  = grab(r"API 请求次数\s*\|\s*(\d+)", u)
toks  = grab(r"Tokens\s*\|\s*(\d+)", u)
spend = grab(r"消费金额（CNY）\s*\|?\s*¥?([\d.,<]+)", u)
model = grab(r"([a-z0-9\-]*(?:v4|v3|chat|coder|reasoner)[a-z0-9\-]*)\s*\|\s*API Key", u)

keys = re.findall(r"名称\s*\\tTracking ID[^|]*\|([^|]*)\|", k)
key_rows = []
for seg in re.split(r"\|\s*", k):
    m = re.match(r"^(.+?)\\t([0-9a-f\-]{8,})\\t(sk-\S+?)\\t([\d\-]+)\\t([\d\-]+)\\t?\s*$", seg.strip())
    if m:
        key_rows.append({"name": m.group(1), "key": m.group(3), "created": m.group(4), "lastUsed": m.group(5)})

out = {
    "ok": True,
    "balance": bal,
    "totalSpend": total,
    "req30d": reqs,
    "tokens30d": toks,
    "spend30d": spend,
    "model": model,
    "keyCount": len(key_rows),
    "keys": key_rows,
    "rawUsage": u[:1200],
}
print(json.dumps(out, ensure_ascii=False))
PY
