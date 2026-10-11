#!/bin/bash
# 2026-10-02 方案① 重出：中文产品去掉 TANTSE；手机竖版只留单字朝代
#   · 手机竖版：11 单字朝代 × iPhone/Android = 22 张（免费引流品）
#   · 桌面横版：16 朝 × 1x/2x = 32 张（付费品）
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/05-承接站/样张"
DESK="$ROOT/02-商品/04-金句线/成品-桌面"
CP="/tmp/dsh-cp-v2"

# 多字朝代（手机版不发）
MULTI="sanhuang sanguo jin wudai juexing"

shot() { # $1=html stem $2=宽 $3=高 $4=倍率 $5=输出文件
  rm -f "$5"
  "$CH" --headless=new --no-sandbox --disable-setuid-sandbox --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --user-data-dir="$CP" --force-device-scale-factor="$4" \
    --window-size="$2","$3" --virtual-time-budget=7000 \
    --screenshot="$5" "file://$B/$1.html" >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 100); do [ -s "$5" ] && break; sleep 0.4; done
  sleep 0.6; kill $pid 2>/dev/null; wait $pid 2>/dev/null
  [ -s "$5" ] && printf "  ✓ %-30s %s\n" "$(basename "$5")" "$(du -h "$5" | cut -f1)" \
              || printf "  ✗ %-30s 失败\n" "$(basename "$5")"
}

echo "── 1. 清理多字朝代的手机产物 ──"
for e in $MULTI; do
  rm -f "$B/$e-phone-iphone.png" "$B/$e-phone-android.png" "$B/$e-phone-iphone.html" "$B/$e-phone-android.html"
  echo "  已拿下 $e"
done

echo "── 2. 重新生成 HTML（手机会自动跳过 5 个多字朝代）──"
"$PY" "$ROOT/02-商品/04-金句线/版式/gen-wallpaper-phone.py" --all 2>&1 | head -3
"$PY" "$ROOT/02-商品/04-金句线/版式/gen-wallpaper.py" --all 2>&1 | tail -1

echo "── 3. 手机竖版重出（11 单字朝代 × 2 = 22 张）──"
for f in "$B"/*-phone-iphone.html; do
  [ -e "$f" ] || continue
  s="$(basename "$f" .html)"
  shot "$s" 1179 2556 1 "$B/$s.png"
done
for f in "$B"/*-phone-android.html; do
  [ -e "$f" ] || continue
  s="$(basename "$f" .html)"
  shot "$s" 1080 2400 1 "$B/$s.png"
done

echo "── 4. 桌面横版重出（16 朝 × 1x/2x = 32 张）──"
mkdir -p "$DESK"
for f in "$B"/*-desktop.html; do
  [ -e "$f" ] || continue
  s="$(basename "$f" .html)"
  shot "$s" 1920 1080 1 "$DESK/$(echo "$s" | sed 's/-desktop$//')-desktop.png"
  shot "$s" 1920 1080 2 "$DESK/$(echo "$s" | sed 's/-desktop$//')-desktop-4k.png"
done

echo "── 完成 ──"
echo "手机竖版：$(ls -1 "$B"/*-phone-iphone.png 2>/dev/null | wc -l | tr -d ' ') 朝 iPhone + $(ls -1 "$B"/*-phone-android.png 2>/dev/null | wc -l | tr -d ' ') 朝 Android"
echo "桌面横版：$(ls -1 "$DESK"/*.png 2>/dev/null | grep -v _ | wc -l | tr -d ' ') 张"
