#!/bin/bash
# 第七境 · 百度搜索资源平台「API 提交（主动推送）」凭据装载
# 用法：source 11-运营/baidu-push-auth.sh   （之后可直接使用 $BD_SITE / $BD_TOKEN）
#
# 优先级：环境变量 > macOS 钥匙串
#   - 环境变量：BD_TOKEN（临时覆盖用，用完即丢）
#   - 钥匙串：服务名 baidu-ziyuan-push，账号 theseventhrealm
#     security add-generic-password -a "theseventhrealm" -s "baidu-ziyuan-push" -U -w "<token>"
#
# 安全口径（与 wp-auth.sh 一致）：凭据**不写入任何项目文件、不进 git、不进记忆文件**；
# 只存 macOS 钥匙串，脚本运行时读入内存。
#
# 背景：百度「sitemap 提交」入口对本站处于 disabled 状态（无 ICP 备案 + 全新站），
# 故主路径改走 API 提交 —— 额度与 sitemap 独立，且官方排序「主动推送 > sitemap > 手动提交」。

BD_SITE="${BD_SITE:-https://theseventhrealm.com}"
KC_SERVICE="${KC_SERVICE:-baidu-ziyuan-push}"
KC_ACCOUNT="${KC_ACCOUNT:-theseventhrealm}"

if [ -z "${BD_TOKEN:-}" ]; then
  if command -v security >/dev/null 2>&1; then
    BD_TOKEN="$(security find-generic-password -a "$KC_ACCOUNT" -s "$KC_SERVICE" -w 2>/dev/null | tr -d '\n')"
  fi
fi

if [ -z "${BD_TOKEN:-}" ]; then
  echo "✗ 拿不到推送 token。二选一："
  echo "  1) 存钥匙串：security add-generic-password -a \"$KC_ACCOUNT\" -s \"$KC_SERVICE\" -U -w \"<token>\""
  echo "  2) 临时给：BD_TOKEN='xxxx' /Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 11-运营/scripts/baidu-push.py --limit 10"
  return 1 2>/dev/null || exit 1
fi

export BD_SITE BD_TOKEN
