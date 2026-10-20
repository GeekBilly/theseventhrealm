#!/bin/zsh
# 复验 CF 挑战页修复（2026-10-20 / REQ-2026-10-20-01）
# 用途：在 CF 面板改完 browser_check / security_level 后，跑一次确认线上状态。
# 只读，不改任何东西。
#
# 用法：zsh 11-运营/scripts/check-cf-challenge.sh

set -u
ZONE_NAME="theseventhrealm.com"
KEYCHAIN_ACCT="theseventhrealm"
# 按顺序找第一个可读的 token（cf-settings 通常带写权限，cf-audit 只读）
KEYCHAIN_SVCS=("cf-settings" "cf-audit" "cf-cache-edit")
API="https://api.cloudflare.com/client/v4"
PY="/Users/billyhou/.workbuddy/binaries/python/envs/default/bin/python"

TOK=""; KeyUsed=""
for svc in "${KEYCHAIN_SVCS[@]}"; do
  t=$(security find-generic-password -a "$KEYCHAIN_ACCT" -s "$svc" -w 2>/dev/null)
  [[ -z "$t" ]] && continue
  TOK="$t"; KeyUsed="$svc"; break
done
if [[ -z "${TOK}" ]]; then
  echo "🔴 钥匙串读不到任何 CF token（试过：${KEYCHAIN_SVCS[*]}）"
  exit 1
fi
echo "使用 token：${KeyUsed}"

ZID=$(curl -s --noproxy '*' -H "Authorization: Bearer ${TOK}" \
  "${API}/zones?name=${ZONE_NAME}" \
  | ${PY} -c "import sys,json;d=json.load(sys.stdin);print(d['result'][0]['id'] if d.get('success') else '')")
if [[ -z "${ZID}" ]]; then
  echo "🔴 取不到 zone id"
  exit 1
fi

echo "=== CF 安全设置（期望：browser_check=off / security_level=low）==="
for s in browser_check security_level challenge_ttl; do
  printf "  %-16s " "$s"
  curl -s --noproxy '*' -H "Authorization: Bearer ${TOK}" "${API}/zones/${ZID}/settings/${s}" \
    | ${PY} -c "import sys,json;d=json.load(sys.stdin);print(d['result']['value'] if d.get('success') else 'ERR')"
done

echo
echo "=== 线上实访（带安卓 UA，看是否还吐挑战页）==="
UA_AND="Mozilla/5.0 (Linux; Android 9; SM-G9500) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Mobile Safari/537.36"
BODY=$(mktemp)
CODE=$(curl -s --noproxy '*' -m 25 -A "${UA_AND}" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  -H "Accept-Language: zh-CN,zh;q=0.9" \
  -o "${BODY}" -w "%{http_code}" "https://${ZONE_NAME}/")
echo "  HTTP ${CODE}"

if grep -q "正在验证您的请求\|Just a moment\|Attention Required" "${BODY}" 2>/dev/null; then
  echo "  🔴 仍是挑战/拦截页 —— 未修好，或需清手机 cf_clearance 再试"
elif grep -q "第七境" "${BODY}" 2>/dev/null; then
  echo "  ✅ 正常返回站点内容（含「第七境」）"
else
  echo "  🟡 返回了内容但不是站点页，人工看一眼"
fi

if grep -qi "cf-mitigated" "${BODY}" 2>/dev/null; then
  echo "  ⚠️ 响应体带 cf-mitigated 标记"
fi

rm -f "${BODY}"
