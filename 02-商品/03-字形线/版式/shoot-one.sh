#!/bin/zsh
# 单张截图（带独立 user-data-dir，避免 Chrome 静默失败）
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/05-承接站/样张"
NAME="${1:-zhou-v9-std}"
SCALE="${2:-1}"
case "$NAME" in *mac) H=1248 ;; *) H=1080 ;; esac

"$CH" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
      --user-data-dir=/tmp/chrome-shot --force-device-scale-factor="$SCALE" \
      --window-size=1920,"$H" --virtual-time-budget=9000 \
      --screenshot="$B/$NAME.png" "file://$B/$NAME.html"
echo "chrome exit=$?"
ls -la "$B/$NAME.png"
