#!/usr/bin/env bash
# 第七境 · WordPress 权限接入验证脚本（只读）
# 用法： bash wp-api-check.sh <用户名> "<应用密码>"
# 说明： 只做 GET 请求，不创建/修改/删除任何内容
set -uo pipefail

SITE="https://theseventhrealm.com"
USER_NAME="${1:-}"
APP_PASS="${2:-}"

if [ -z "$USER_NAME" ] || [ -z "$APP_PASS" ]; then
  echo "用法: bash wp-api-check.sh <用户名> \"<应用密码>\""
  exit 1
fi

auth=(-u "${USER_NAME}:${APP_PASS}")

echo "===== 第七境 · WordPress REST API 只读验证 ====="
echo "站点: ${SITE}"
echo

echo "---- ① 鉴权与身份（GET /users/me）----"
curl -sS "${auth[@]}" -m 20 "${SITE}/wp-json/wp/v2/users/me?_fields=id,name,slug,roles" \
  -w "\n[HTTP %{http_code}]\n" 2>&1
echo

echo "---- ② 页面列表（GET /pages）----"
curl -sS "${auth[@]}" -m 20 "${SITE}/wp-json/wp/v2/pages?per_page=20&_fields=id,slug,status,title" \
  -w "\n[HTTP %{http_code}]\n" 2>&1
echo

echo "---- ③ 媒体库（GET /media，取最近 3 条）----"
curl -sS "${auth[@]}" -m 20 "${SITE}/wp-json/wp/v2/media?per_page=3&_fields=id,slug,mime_type,source_url" \
  -w "\n[HTTP %{http_code}]\n" 2>&1
echo

echo "---- ④ 权限探测：读取页面的编辑态（context=edit，只读）----"
curl -sS "${auth[@]}" -m 20 "${SITE}/wp-json/wp/v2/pages/13?context=edit&_fields=id,slug,status,title,content" \
  -w "\n[HTTP %{http_code}]\n" 2>&1 | head -c 500
echo
echo "（返回 200 且能看到 edit 态内容 = 具备编辑权限；返回 403 = 权限不足）"
echo
echo "===== 验证结束：以上全部为只读 GET 操作，未创建/修改/删除任何内容 ====="
