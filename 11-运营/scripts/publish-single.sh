#!/bin/bash
# 第七境 · 通用单页发布（幂等，按 slug 新建或更新）
#
# 背景：publish-pages.sh 是「五页固定清单」专用。发新页面（FAQ、公告、活动页等）
#       不该去改那个清单，抽一个通用入口，将来任何单页都走这里。
#
# 用法（凭据自动从 macOS 钥匙串取，不用手工传）：
#   bash 11-运营/scripts/publish-single.sh <slug> <标题> <正文文件> [摘要]
#
# 例：
#   bash 11-运营/scripts/publish-single.sh faq 常见问题 03-页面/faq.html "第七境常见问题…"
#
# ⚠️ 第 4 个参数「摘要」很重要，别省：
#    子主题 functions.php 有钩子，写了 excerpt 就自动同步三处 description（meta/Yoast/摘要），
#    等于零成本拿到 SEO 描述。不写则搜索结果里显示 WordPress 自动截断的第一段。
#
# 先体检不碰线上：
#   DRY_RUN=1 bash 11-运营/scripts/publish-single.sh faq 常见问题 03-页面/faq.html
#
# 幂等：slug 已存在则走「更新」，不会建重复页。评论与 trackback 一律关闭。

set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1

# 凭据自动装载：环境变量 > 钥匙串（见 11-运营/wp-auth.sh）
. "11-运营/wp-auth.sh" || exit 1

# 站点规范域名是 apex（www 会 301 到 apex，POST 被 301 吞掉会导致发布失败）
SITE="${SITE:-https://theseventhrealm.com}"
DRY="${DRY_RUN:-}"

SLUG="${1:-}"
TITLE="${2:-}"
FILE="${3:-}"
EXCERPT="${4:-}"

if [ -z "$SLUG" ] || [ -z "$TITLE" ] || [ -z "$FILE" ]; then
  echo "用法：bash 11-运营/scripts/publish-single.sh <slug> <标题> <正文文件> [摘要]"
  exit 1
fi

echo "== 本地体检 =="
if [ ! -f "$FILE" ]; then
  echo "  ✗ 缺文件：$FILE"
  exit 1
fi

# 私密信息体检：正文里不该出现真实姓名载体——手机号、私人邮箱
if grep -nE '1[3-9][0-9]{9}|@sina\.com|@qq\.com|@163\.com|@gmail\.com' "$FILE" >/dev/null; then
  echo "  ✗ 正文含疑似私密信息，已中止："
  grep -nE '1[3-9][0-9]{9}|@sina\.com|@qq\.com|@163\.com|@gmail\.com' "$FILE"
  exit 1
fi

# 异常字符体检：只接受有意书写的 HTML 实体，防止生成过程混入转义残渣
if grep -nE '&(amp|lt|gt|quot|nbsp|#39);' "$FILE" >/dev/null; then
  echo "  ⚠ 正文含 HTML 实体，确认是有意为之："
  grep -nE '&(amp|lt|gt|quot|nbsp|#39);' "$FILE"
fi

SIZE=$(wc -c <"$FILE" | tr -d ' ')
LINES=$(wc -l <"$FILE" | tr -d ' ')
echo "  ✓ slug=$SLUG  标题=[${TITLE}]  ${SIZE} 字节 / ${LINES} 行"
echo "  ✓ 私密信息体检通过"

# 摘要既影响 SEO（钩子同步三处 description），也参与私密信息体检
if [ -z "$EXCERPT" ]; then
  echo "  ⚠ 未提供摘要：搜索结果页会显示正文前若干字的自动截断，SEO 描述失控。"
  echo "     建议补第 4 个参数（120 字内，含主关键词）。"
else
  echo "  ✓ 摘要 ${#EXCERPT} 字：$EXCERPT"
  if printf '%s' "$EXCERPT" | grep -nE '1[3-9][0-9]{9}|@(sina|qq|163|gmail)\.com' >/dev/null; then
    echo "  ✗ 摘要含疑似私密信息，已中止"
    exit 1
  fi
fi

if [ -n "$DRY" ]; then
  echo "DRY_RUN=1：仅体检，未访问线上。"
  exit 0
fi

if [ -z "${WP_APP_PASS:-}" ]; then
  echo "缺少 WP_APP_PASS（WordPress 后台 → 用户 → 个人资料 → 应用程序密码）"
  exit 1
fi

API="$SITE/wp-json/wp/v2/pages"
AUTH=(-u "$WP_USER:$WP_APP_PASS")

echo
echo "== 查重 =="
EXIST=$(curl -s "${AUTH[@]}" "$API?slug=$SLUG&status=any&per_page=1" \
        | tr -d '\n' | sed -n 's/.*"id":\([0-9]\{1,\}\).*/\1/p')
if [ -n "$EXIST" ]; then
  echo "  已存在 #${EXIST} → 走更新"
else
  echo "  未存在 → 新建"
fi

PAYLOAD=$(/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 - "$TITLE" "$SLUG" "$FILE" "$EXCERPT" <<'PY'
import json, sys
title, slug, path, excerpt = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
body = open(path, encoding='utf-8').read()
data = {
    "title": title, "slug": slug, "status": "publish", "content": body,
    "comment_status": "closed", "ping_status": "closed",
}
# 写了 excerpt 才会被子主题钩子同步成三处 description；不写则缺失，不传空串占位
if excerpt.strip():
    data["excerpt"] = excerpt.strip()
print(json.dumps(data, ensure_ascii=False))
PY
)

echo
echo "== 发布到 $SITE =="
if [ -n "$EXIST" ]; then
  RES=$(curl -s -X POST "${AUTH[@]}" -H 'Content-Type: application/json' \
        --data-binary "$PAYLOAD" "$API/$EXIST")
  ACT="更新 #${EXIST}"
else
  RES=$(curl -s -X POST "${AUTH[@]}" -H 'Content-Type: application/json' \
        --data-binary "$PAYLOAD" "$API")
  ACT="新建"
fi

LINK=$(printf '%s' "$RES" \
  | /Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -c \
    'import json,sys
try:
    d=json.load(sys.stdin); print(d.get("link") or d.get("message") or d.get("code","?"))
except Exception:
    print("响应不是 JSON，见上")' 2>/dev/null)
echo "  $ACT  →  $LINK"

echo
echo "== 线上复核 =="
CODE=$(curl -s -o /dev/null -w '%{http_code}' -L "$SITE/$SLUG/")
echo "  /$SLUG/  HTTP $CODE"

echo
echo "小提示：发布后可：① 跑 11-运营/scripts/site-health-lite.sh 复核 sitemap 是否纳入新页"
echo "       ② 若该页要进百度，记得重跑 build-baidu-sitemap.py 并重传扁平版 sitemap"
