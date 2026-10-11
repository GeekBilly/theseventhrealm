#!/bin/bash
# 2026-10-02 重出图：英文落款 THE SEVENTH REALM → TANTSE（中文「第七境」与印章不变）
# 用法：bash reshoot-20261002.sh          （全部 43 张）
#       bash reshoot-20261002.sh classic  （只出字形线 8 张，先试）
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
B="$ROOT/02-商品/05-承接站/样张"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CP="/tmp/dsh-cp-shot"

shot() { # $1=stem(无扩展) $2=宽 $3=高 $4=倍率 $5=输出后缀
  local out="$B/$1$5.png"
  rm -f "$out"
  "$CH" --headless=new --no-sandbox --disable-setuid-sandbox --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --user-data-dir="$CP" --force-device-scale-factor="$4" \
    --window-size="$2","$3" --virtual-time-budget=6000 \
    --screenshot="$out" "file://$B/$1.html" >/dev/null 2>&1 &
  local pid=$!
  local i
  for i in $(seq 1 100); do [ -s "$out" ] && break; sleep 0.4; done
  sleep 0.6; kill $pid 2>/dev/null; wait $pid 2>/dev/null
  if [ -s "$out" ]; then
    printf "  ✓ %-34s %s\n" "$1$5.png" "$(du -h "$out" | cut -f1)"
  else
    printf "  ✗ %-34s 失败\n" "$1$5.png"
  fi
}

MODE="${1:-all}"

if [ "$MODE" = "classic" ] || [ "$MODE" = "all" ]; then
  echo "── 字形线（4 HTML × 1x/2x = 8 张）──"
  for s in shang-v9-std shang-v9-mac zhou-v9-std zhou-v9-mac; do
    case "$s" in *-mac) H=1248 ;; *) H=1080 ;; esac
    shot "$s" 1920 "$H" 1 ""
    shot "$s" 1920 "$H" 2 "-4k"
  done
  [ "$MODE" = "classic" ] && { echo "完成（仅字形线）"; exit 0; }
fi

echo "── 金句线 · 手机竖版（32 张）──"
for f in "$B"/*-phone-iphone.html; do
  [ -e "$f" ] || continue
  shot "$(basename "$f" .html)" 1179 2556 1 ""
done
for f in "$B"/*-phone-android.html; do
  [ -e "$f" ] || continue
  shot "$(basename "$f" .html)" 1080 2400 1 ""
done

echo "── 锁屏预览 + 桌面/移动金句版（3 张）──"
[ -e "$B/shang-phone-lockpreview.html" ] && shot shang-phone-lockpreview 1179 2556 1 ""
[ -e "$B/shang-desktop.html" ] && shot shang-desktop 1920 1080 1 ""
[ -e "$B/shang-mobile.html" ] && shot shang-mobile 1170 2532 1 ""

echo "── 完成 ──"
echo "样张 PNG 总数：$(ls -1 "$B"/*.png | wc -l | tr -d ' ')"
echo "残留旧英文名的 HTML：$(grep -l 'THE SEVENTH REALM' "$B"/*.html 2>/dev/null | wc -l | tr -d ' ')"
