#!/bin/bash
# 金句线 · 桌面横版出图（16 朝 × 1x/2x）—— 为 A1 首卖 SKU 备货
# 用法：bash build-desktop-quotes.sh [1x|2x|all]
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/05-承接站/样张"
OUT="$ROOT/02-商品/04-金句线/成品-桌面"
CP="/tmp/dsh-cp-desk"
MODE="${1:-all}"

mkdir -p "$OUT"

echo "── 1. 生成 HTML（16 朝 × desktop/mobile）──"
"$PY" "$ROOT/02-商品/04-金句线/版式/gen-wallpaper.py" --all 2>&1 | tail -2

shot() { # $1=stem $2=倍率 $3=后缀
  local out="$OUT/$1$3.png"
  rm -f "$out"
  "$CH" --headless=new --no-sandbox --disable-setuid-sandbox --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --user-data-dir="$CP" --force-device-scale-factor="$2" \
    --window-size=1920,1080 --virtual-time-budget=7000 \
    --screenshot="$out" "file://$B/$1.html" >/dev/null 2>&1 &
  local pid=$!
  local i
  for i in $(seq 1 100); do [ -s "$out" ] && break; sleep 0.4; done
  sleep 0.6; kill $pid 2>/dev/null; wait $pid 2>/dev/null
  if [ -s "$out" ]; then printf "  ✓ %-26s %s\n" "$1$3.png" "$(du -h "$out" | cut -f1)"
  else printf "  ✗ %-26s 失败\n" "$1$3.png"; fi
}

if [ "$MODE" = "1x" ] || [ "$MODE" = "all" ]; then
  echo "── 2. 1x 渲染（1920×1080）──"
  for f in "$B"/*-desktop.html; do
    [ -e "$f" ] || continue
    shot "$(basename "$f" .html)" 1 ""
  done
fi

if [ "$MODE" = "2x" ] || [ "$MODE" = "all" ]; then
  echo "── 3. 2x 渲染（3840×2160，这才是"值钱"的那份）──"
  for f in "$B"/*-desktop.html; do
    [ -e "$f" ] || continue
    shot "$(basename "$f" .html)" 2 "-4k"
  done
fi

echo "── 完成 ──"
echo "产出目录：$OUT"
echo "文件数：$(ls -1 "$OUT"/*.png 2>/dev/null | wc -l | tr -d ' ')"
