#!/bin/bash
# 第七境 · 站点健康体检（本地零 AI 成本，输出 Markdown）
#
# 用法：
#   bash 11-运营/scripts/site-health-lite.sh                       # 打印到屏幕
#   bash 11-运营/scripts/site-health-lite.sh -o 11-运营/reports/x.md    # 同时写文件  # deadlinks-ignore
#
# 覆盖：① 凭据是否还在（钥匙串）② WP REST 是否被 401（应用密码是否被撤销）
#      ③ 全站 URL 状态码（含 404 死链）④ WordPress 版本 ⑤ 最近一次备份新鲜度
#      ⑥ HTTPS/证书剩余天数 ⑦ Cloudflare 是否还在代理（橙云被关检测）
#
# 设计：全部走 curl + 本地命令，不联网搜索、不调用模型，跑一次约 3–10 秒。

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
SITE="${SITE:-https://theseventhrealm.com}"
# 🔴 Cloudflare 会拦 curl 默认 UA 返回 403（2026-10-06 起实测），所有取数必须带浏览器 UA，
#    否则全站 43 条 URL 会「全部异常」——那是拦截不是故障。
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
OUTFILE="${2:-}"
[ "${1:-}" = "-o" ] && OUTFILE="${2:-}"

say() { echo "$1"; [ -n "$OUTFILE" ] && echo "$1" >> "$OUTFILE"; }
[ -n "$OUTFILE" ] && : > "$OUTFILE"

say "## 站点健康体检（本地脚本）"
say ""
say "- 时间：$(date '+%F %T')"
say "- 目标：$SITE"
say ""

# ① 凭据在位检查
say "### 1. 凭据在位"
for svc in theseventhrealm-wp deepseek-api; do
  if security find-generic-password -s "$svc" >/dev/null 2>&1; then
    say "- ✅ 钥匙串 $svc 存在"
  else
    say "- ⚠️ 钥匙串 $svc **缺失**（相关自动化会静默失败）"
  fi
done

# ② WP REST 探活
say ""
say "### 2. WordPress REST 凭据"
if [ -f "$ROOT/11-运营/wp-auth.sh" ] && WP_PASS="$(security find-generic-password -s theseventhrealm-wp -w 2>/dev/null | tr -d '\n')" && [ -n "$WP_PASS" ]; then
  code=$(curl -A "$UA" -s -L -o /tmp/sr_me.json -w "%{http_code}" --max-time 30 -u "MollyBot_No.2:$WP_PASS" "$SITE/wp-json/wp/v2/users/me")
  if [ "$code" = "200" ]; then
    ME_ROLE=$(/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c 'import json
try:
    r = json.load(open("/tmp/sr_me.json")).get("roles") or []
    print("/".join(r) if r else "编辑器（REST 未公开 roles）")
except Exception:
    print("未知")' 2>/dev/null)
    say "- ✅ 应用密码有效（users/me 返回 200，角色：${ME_ROLE}）"
  else
    say "- ⚠️ users/me 返回 **HTTP $code** —— 应用密码可能已被后台撤销，请重生成并写回钥匙串"
  fi
else
  say "- ⚠️ 取不到 WP 凭据，跳过"
fi

# ③ 全站 URL 状态码（从 sitemap 取）
say ""
say "### 3. 全站 URL 状态码"
map=$(curl -A "$UA" -s -LL --max-time 25 "$SITE/wp-sitemap.xml" | grep -oE '<loc>[^<]+</loc>' | sed -E 's#</?loc>##g' | head -5)
urls=$(printf '%s\n' "$map" | grep -v '^$' | while IFS= read -r sm; do curl -A "$UA" -s -LL --max-time 25 "$sm" | grep -oE '<loc>[^<]+</loc>'; done | sed -E 's#</?loc>##g' | sort -u)
total=0; bad=0
if [ -n "$urls" ]; then
  while IFS= read -r u; do
    [ -z "$u" ] && continue
    total=$((total+1))
    code=$(curl -A "$UA" -s -L -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 "$u")
    if [ "$code" = "000" ]; then
      # 000 多为瞬时抖动/限速，不是真死链——重试一次再判（2026-09-30 起：曾误报 2 条）
      sleep 2
      code=$(curl -A "$UA" -s -L -o /dev/null -w "%{http_code}" --connect-timeout 15 --max-time 40 "$u")
    fi
    if [ "$code" != "200" ]; then bad=$((bad+1)); say "- ❌ $code $u"; fi
  done <<EOF
$urls
EOF
  say "- 共检查 ${total} 条 URL，异常 ${bad} 条$( [ "$bad" -eq 0 ] && echo ' ✅' )"
else
  say "- ⚠️ 取不到 sitemap（可能是 Cloudflare 拦截或路径变更），本次未做死链扫描"
fi

# ④ WordPress 版本
say ""
say "### 4. 版本暴露"
gen=$(curl -A "$UA" -s -L --max-time 25 "$SITE/" | grep -oE 'name="generator" content="WordPress [0-9.]+"' | head -1 | grep -oE '[0-9]+\.[0-9.]+')
[ -n "$gen" ] && say "- WordPress ${gen} —— 留意该版本的安全公告；插件更新需管理员权限，编辑角色无法代劳" \
               || say "- 未探测到 generator 标记（可能已被隐藏，属好事）"

# ⑤ 备份新鲜度
say ""
say "### 5. 备份"
last=$(ls -1d "$ROOT"/11-运营/backup/20* 2>/dev/null | tail -1)
if [ -n "$last" ]; then
  days=$(( ( $(date +%s) - $(stat -f "%B" "$last") ) / 86400 ))
  if [ "$days" -gt 40 ]; then say "- ⚠️ 最近备份 $(basename "$last") 已 **${days} 天**，超过 40 天阈值"
  else say "- ✅ 最近备份 $(basename "$last")（${days} 天前）"; fi
  if [ -f "$last/manifest.json" ]; then
    BK_INFO=$(/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c 'import json,sys
try:
    m = json.load(open(sys.argv[1]))
    c = m.get("counts", {})
    b = m.get("total_bytes")
    b = format(b, ",") if isinstance(b, int) else "未知"
    print("条目 %s / 体积 %s 字节" % (c, b))
except Exception:
    print("manifest 解析失败")' "$last/manifest.json" 2>/dev/null)
    say "- ${BK_INFO}"
  fi
else
  say "- ⚠️ 尚未生成过结构化备份，跑 \`bash 11-运营/scripts/backup-site.sh\`"
fi

# ⑥ 证书剩余天数
say ""
say "### 6. HTTPS 证书"
exp=$(echo | openssl s_client -servername "${SITE#https://}" -connect "${SITE#https://}:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | sed 's/notAfter=//')
if [ -n "$exp" ]; then
  left=$(( ( $(date -j -f "%b %e %H:%M:%S %Y %Z" "$exp" "+%s" 2>/dev/null || echo 0) - $(date +%s) ) / 86400 ))
  [ "$left" -lt 30 ] && say "- ⚠️ 证书剩余 **${left} 天**：${exp}" || say "- ✅ 证书剩余 ${left} 天（${exp}）"
else
  say "- ⚠️ 取不到证书信息，检查 SSL/TLS 配置"
fi

# ⑦ Cloudflare 代理检测
say ""
say "### 7. Cloudflare 代理"
ips=$(dig +short "${SITE#https://}" A | tr '\n' ' ')
cf=$(curl -A "$UA" -s -LI --max-time 25 "$SITE/" | grep -ciE '^server: cloudflare|^cf-ray' || true)
if [ "$cf" -gt 0 ]; then say "- ✅ 橙云生效（server/cf-ray 存在），解析：$ips"
else say "- ⚠️ 未检测到 Cloudflare 响应头，可能被关代理或证书直出，解析：$ips"; fi

say ""
say "> 本脚本只读，不做任何修改、移动、删除操作。"
