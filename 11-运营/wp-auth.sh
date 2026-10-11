#!/bin/bash
# 第七境 · WordPress 凭据自动装载
# 用法：source 11-运营/wp-auth.sh   （之后可直接使用 $WP_USER / $WP_APP_PASS / $SITE）
#
# 优先级：环境变量 > macOS 钥匙串
#   - 环境变量：WP_USER / WP_APP_PASS / SITE（临时覆盖用，用完即丢）
#   - 钥匙串：服务名 theseventhrealm-wp，账号 MollyBot_No.2
#     security add-generic-password -a "MollyBot_No.2" -s "theseventhrealm-wp" -w "<应用密码>"
#
# 安全口径：凭据**不写入任何项目文件、不进 git、不进记忆文件**；
# 只存在 macOS 钥匙串（受登录密码保护），脚本运行时读入内存。

SITE="${SITE:-https://theseventhrealm.com}"
WP_USER="${WP_USER:-MollyBot_No.2}"
KC_SERVICE="${KC_SERVICE:-theseventhrealm-wp}"

if [ -z "${WP_APP_PASS:-}" ]; then
  if command -v security >/dev/null 2>&1; then
    WP_APP_PASS="$(security find-generic-password -s "$KC_SERVICE" -w 2>/dev/null | tr -d '\n')"
  fi
fi

if [ -z "${WP_APP_PASS:-}" ]; then
  echo "✗ 拿不到应用密码。二选一："
  echo "  1) 存钥匙串：security add-generic-password -a \"$WP_USER\" -s \"$KC_SERVICE\" -U -w \"<应用密码>\""
  echo "  2) 临时给：WP_APP_PASS='xxxx xxxx xxxx xxxx' bash 11-运营/xxx.sh"  # deadlinks-ignore
  return 1 2>/dev/null || exit 1
fi

export SITE WP_USER WP_APP_PASS
