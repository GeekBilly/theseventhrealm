#!/bin/bash
# 第七境 · 十六朝代独立页一键发布（父页面：/5000years，WP 页面 ID 32）
#
# 用法（凭据自动从 macOS 钥匙串取，不用手工传）：
#   bash 11-运营/朝代页流水线/publish.sh
# 临时覆盖（一次性，不落盘）：
#   WP_APP_PASS='xxxx xxxx …' bash 11-运营/朝代页流水线/publish.sh
# 先体检不发布：
#   DRY_RUN=1 bash 11-运营/朝代页流水线/publish.sh
# 只发一页（调试用）：
#   ONLY=shang bash 11-运营/朝代页流水线/publish.sh
#
# 幂等：同 slug 已存在则更新，不建重复页。

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
# 凭据自动装载：环境变量 > 钥匙串（见 11-运营/wp-auth.sh）
# shellcheck disable=SC1091
. "$(dirname "$0")/../wp-auth.sh" || exit 1
# 必须打 apex：站点规范域名是 theseventhrealm.com，www 会 301 到 apex。
# POST 跟随 301/302 时 curl 默认会把请求降级成 GET（body 丢失且静默），
# 因此除了 -L 还要 --post301 --post302 强制保持 POST。
SITE="${SITE:-https://theseventhrealm.com}"
USER_NAME="${WP_USER}"
PASS="${WP_APP_PASS}"
DRY="${DRY_RUN:-}"
ONLY="${ONLY:-}"
# 父页面 /5000years 的 WP 页面 ID
PARENT_ID="${PARENT_ID:-32}"
PARENT="$PARENT_ID"
PY=/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3

SLUGS=(sanhuang xia shang zhou qin han sanguo jin sui tang wudai song yuan ming qing juexing)
[ -n "$ONLY" ] && SLUGS=("$ONLY")

echo "== 本地体检 =="
for slug in "${SLUGS[@]}"; do
  file="${DYNASTY_DIR:-03-页面/朝代页}/$slug.html"
  [ -f "$file" ] || { echo "  ✗ 缺文件 ${file}（先跑 sync-from-drafts.py 再跑 11-运营/朝代页流水线/build.py）"; exit 1; }
  if grep -nE '1[3-9][0-9]{9}|@qq\.com|@163\.com|@sina\.com|@gmail\.com' "$file" >/dev/null; then
    echo "  ✗ $file 含疑似私密信息，已中止"; exit 1
  fi
  echo "  ✓ $slug  ($(wc -c <"$file" | tr -d ' ') 字节)"
done

if [ -n "$DRY" ]; then echo "DRY_RUN=1：仅体检，未访问线上。"; exit 0; fi
if [ -z "$PASS" ]; then echo "缺少 WP_APP_PASS（WordPress 后台 → 用户 → 个人资料 → 应用程序密码）"; exit 1; fi

API="$SITE/wp-json/wp/v2/pages"
AUTH=(-u "$USER_NAME:$PASS")
echo
echo "== 发布到 ${SITE} （父页面 ID ${PARENT}）=="
for slug in "${SLUGS[@]}"; do
  file="${DYNASTY_DIR:-03-页面/朝代页}/$slug.html"
  # ⚠️ 原用 sed 贪婪匹配抠 id，会取到响应里**最后一个** "id"（实测拿到 131/132/133，
  #    真实是 94-109）→ rest_post_invalid_id 且**静默失败**。改用 json 解析取 d[0]["id"]。
  exist=$(curl -s -L --max-time 30 "${AUTH[@]}" "$API?slug=$slug&status=any&per_page=1" \
          | /Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')
  payload=$($PY - "$slug" "$file" "$PARENT" <<'PY'
import json,sys
slug,path,parent=sys.argv[1],sys.argv[2],sys.argv[3]
html=open(path,encoding='utf-8').read()
# 页面标题（SEO）：取 <style> 之后首行的 seo 标题——这里直接由 slug 映射
import re,os
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(path)),'..','..','11-运营','朝代页流水线'))
from eras import ERAS
title=next(e['seo'] for e in ERAS if e['slug']==slug)
print(json.dumps({"title":title,"slug":slug,"status":"publish","parent":int(parent),
                  "content":html,"comment_status":"closed","ping_status":"closed"},ensure_ascii=False))
PY
)
  if [ -n "$exist" ]; then
    res=$(curl -s -L --post301 --post302 --max-time 60 "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary "$payload" "$API/$exist")
    act="更新 #$exist"
  else
    res=$(curl -s -L --post301 --post302 --max-time 60 "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary "$payload" "$API")
    act="新建"
  fi
  link=$(printf '%s' "$res" | $PY -c 'import json,sys;d=json.load(sys.stdin);print(d.get("link") or d.get("code","?"))' 2>/dev/null)
  echo "  $act  /5000years/$slug/  →  $link"
done

echo
echo "== 清 CF 缓存 =="
if [ -n "$DRY" ]; then
  echo "  DRY_RUN 模式，跳过"
else
  # 🔴 2026-10-17 起 HTML 已进 CDN（Edge TTL 2h）：不清缓存线上要 2 小时才更新。
  #    必须放在「线上复核」之前，否则复核读到的是缓存里的旧页面。
  /usr/bin/python3 11-运营/scripts/cf-cache-rules.py --purge \
    || echo "  ⚠️ 清缓存失败（按规则不重试），稍后可手动再跑一次上面的命令"
fi

echo
echo "== 线上复核 =="
for slug in "${SLUGS[@]}"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -L "$SITE/5000years/$slug/")
  echo "  /5000years/$slug/  HTTP $code"
done
echo
echo "注意：本脚本用的是常驻钥匙串的应用密码（服务名 theseventhrealm-wp，由 11-运营/wp-auth.sh 装载），
发布后**不要撤销**——撤销会让每日晨检、MollyBot 取数全部 401。仅在怀疑泄露时才重生成，
届时按 11-运营/记忆与归档规范.md 用 security add-generic-password 写回钥匙串即可。"
