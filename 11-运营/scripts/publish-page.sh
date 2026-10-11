#!/bin/bash
# 第七境 · 单页通用发布（新建或按 slug 更新，幂等）
#
# 用法：
#   bash 11-运营/scripts/publish-page.sh <slug> <标题> <正文文件> [父页面ID]
#   DRY_RUN=1 bash 11-运营/scripts/publish-page.sh collection 藏品 03-页面/collection.html
#
# 例：挂到 /5000years 下（父页 id=32）
#   bash 11-运营/scripts/publish-page.sh shang 商朝 03-页面/朝代页/shang.html 32

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
. "$(dirname "$0")/../wp-auth.sh" || exit 1

SLUG="${1:?缺 slug}"
TITLE="${2:?缺标题}"
FILE="${3:?缺正文文件}"
PARENT="${4:-}"

SITE="${SITE:-https://theseventhrealm.com}"   # 必须 apex，www 会 301 吞掉请求
PY=/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3

echo "== 本地体检 =="
[ -f "$FILE" ] || { echo "  ✗ 缺文件 $FILE"; exit 1; }
if grep -nE '1[3-9][0-9]{9}|@qq\.com|@163\.com|@sina\.com|@gmail\.com' "$FILE" >/dev/null; then
  echo "  ✗ $FILE 含疑似私密信息，已中止"; exit 1
fi
echo "  ✓ $SLUG  ($(wc -c <"$FILE" | tr -d ' ') 字节, 标题 [${TITLE}])"

if [ -n "${DRY_RUN:-}" ]; then echo "DRY_RUN=1：仅体检，未访问线上。"; exit 0; fi
[ -n "${WP_APP_PASS:-}" ] || { echo "缺少 WP_APP_PASS"; exit 1; }

API="$SITE/wp-json/wp/v2/pages"
AUTH=(-u "$WP_USER:$WP_APP_PASS")
EXTRA=""
[ -n "$PARENT" ] && EXTRA=",\"parent\":$PARENT"

# ⚠️ 同 publish.sh：不要用 sed 抠 id（贪婪匹配会取错）。用 json 解析。
# ⚠️ 查询必须带 cache-buster：曾发生 ?slug=en 被（CDN/对象缓存）返回空响应 →
#    JSONDecodeError → EXIST 误判为空 → 重复新建出 /en-2/（2026-10-01 事故，已手删）。
EXIST=$(curl -s -L --max-time 30 "${AUTH[@]}" "$API?slug=$SLUG&status=any&per_page=1&_cb=${RANDOM}${RANDOM}" \
        | /Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')

PAYLOAD=$($PY - "$TITLE" "$SLUG" "$FILE" "$EXTRA" <<'PY'
import json, sys
title, slug, path, extra = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
body = open(path, encoding='utf-8').read()
d = {"title": title, "slug": slug, "status": "publish", "content": body,
     "comment_status": "closed", "ping_status": "closed"}
if extra:
    d["parent"] = int(extra.strip(',').split(':')[1])
print(json.dumps(d, ensure_ascii=False))
PY
)

if [ -n "$EXIST" ]; then
  RES=$(curl -s -L --post301 --post302 --max-time 60 "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary "$PAYLOAD" "$API/$EXIST")
  ACT="更新 #$EXIST"
else
  RES=$(curl -s -L --post301 --post302 --max-time 60 "${AUTH[@]}" -H 'Content-Type: application/json' --data-binary "$PAYLOAD" "$API")
  ACT="新建"
fi

LINK=$(printf '%s' "$RES" | $PY -c 'import json,sys
try:
    d=json.load(sys.stdin); print(d.get("link") or d.get("message") or d.get("code","?"))
except Exception: print("解析失败")')
echo "  $ACT  /$SLUG  →  $LINK"

CODE=$(curl -s -o /dev/null -w '%{http_code}' -L "$SITE/$SLUG/")
echo "  线上复核：/$SLUG  HTTP $CODE"
