#!/bin/bash
# 第七境 · 五页一键发布（关于 / 联络 / 隐私政策 / 使用条款 / 免责声明）
#
# 用法（凭据自动从 macOS 钥匙串取，不用手工传）：
#   bash 11-运营/publish-pages.sh
#
# 临时覆盖（一次性，不落盘）：
#   WP_APP_PASS='xxxx xxxx …' bash 11-运营/publish-pages.sh
#
# 可选：先加 DRY_RUN=1 只做本地体检，不碰线上：
#   DRY_RUN=1 bash 11-运营/publish-pages.sh
#
# 幂等：同 slug 已存在时改走更新（不会建重复页）。

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
# 凭据自动装载：环境变量 > 钥匙串（见 11-运营/wp-auth.sh）
# shellcheck disable=SC1091
. "$(dirname "$0")/wp-auth.sh" || exit 1
# 注意：站点规范域名是 apex（www 会 301 到 apex，POST 被 301 吞掉会导致发布失败）
SITE="${SITE:-https://theseventhrealm.com}"
USER_NAME="${WP_USER}"
PASS="${WP_APP_PASS}"
DRY="${DRY_RUN:-}"

# slug|标题|正文文件（目录已于 2026-09-30 由 shop/ 归入 03-页面/，路径随之更新）
PAGES=(
  "about|关于|03-页面/draft-about.html"
  "contact|联络|03-页面/draft-contact.html"
  "privacy|隐私政策|03-页面/draft-privacy.html"
  "terms|使用条款|03-页面/draft-terms.html"
  "disclaimer|免责声明|03-页面/draft-disclaimer.html"
)

echo "== 本地体检 =="
for row in "${PAGES[@]}"; do
  IFS='|' read -r slug title file <<<"$row"
  if [ ! -f "$file" ]; then echo "  ✗ 缺文件 $file"; exit 1; fi
  # 正文里不该出现真实姓名/手机号/私人邮箱
  if grep -nE '1[3-9][0-9]{9}|@sina\.com|@qq\.com|@163\.com|@gmail\.com' "$file" >/dev/null; then
    echo "  ✗ $file 含疑似私密信息，已中止"; grep -nE '1[3-9][0-9]{9}|@sina\.com|@qq\.com|@163\.com|@gmail\.com' "$file"; exit 1
  fi
  echo "  ✓ $slug  ($(wc -c <"$file" | tr -d ' ') 字节, 标题 [${title}])"
done

if [ -n "$DRY" ]; then echo "DRY_RUN=1：仅体检，未访问线上。"; exit 0; fi
if [ -z "$PASS" ]; then echo "缺少 WP_APP_PASS（WordPress 后台 → 用户 → 个人资料 → 应用程序密码）"; exit 1; fi

API="$SITE/wp-json/wp/v2/pages"
AUTH=(-u "$USER_NAME:$PASS")
echo
echo "== 发布到 $SITE =="
for row in "${PAGES[@]}"; do
  IFS='|' read -r slug title file <<<"$row"
  exist=$(curl -s "${AUTH[@]}" "$API?slug=$slug&status=any&per_page=1" \
          | tr -d '\n' | sed -n 's/.*"id":\([0-9]\{1,\}\).*/\1/p')
  payload=$(/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 - "$title" "$slug" "$file" <<'PY'
import json,sys
title,slug,path=sys.argv[1],sys.argv[2],sys.argv[3]
body=open(path,encoding='utf-8').read()
print(json.dumps({"title":title,"slug":slug,"status":"publish","content":body,"comment_status":"closed","ping_status":"closed"},ensure_ascii=False))
PY
)
  if [ -n "$exist" ]; then
    res=$(curl -s -X POST "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary "$payload" "$API/$exist")
    act="更新 #$exist"
  else
    res=$(curl -s -X POST "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary "$payload" "$API")
    act="新建"
  fi
  link=$(printf '%s' "$res" | /Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("link") or d.get("code","?"))' 2>/dev/null)
  echo "  $act  /$slug  →  $link"
done
echo
echo "== 线上复核 =="
for row in "${PAGES[@]}"; do
  IFS='|' read -r slug title file <<<"$row"
  code=$(curl -s -o /dev/null -w '%{http_code}' -L "$SITE/$slug/")
  echo "  /$slug  HTTP $code"
done
echo
echo "完成后请到 WordPress 后台「用户 → 个人资料」撤销本次应用程序密码。"
