#!/bin/bash
# 字形线 A 线①「字体演变」出图
# 用法：bash shoot-evolution.sh [slug...]     不带参数=全部
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/05-承接站/样张"
# 默认＝正式成品；设 OUT_OVERRIDE=… 可改投别处（如无底纹校样，避免与可上架成品混放）
OUT="${OUT_OVERRIDE:-$ROOT/02-商品/03-字形线/成品-演变/01-正式成品}"
CP="/tmp/dsh-cp-evo"
mkdir -p "$OUT"

shot() { # $1=stem $2=w $3=h $4=scale $5=out
  rm -f "$5"
  "$CH" --headless=new --no-sandbox --disable-setuid-sandbox --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --user-data-dir="$CP" --force-device-scale-factor="$4" \
    --window-size="$2","$3" --virtual-time-budget=8000 \
    --screenshot="$5" "file://$B/$1.html" >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 120); do [ -s "$5" ] && break; sleep 0.4; done
  sleep 0.6; kill $pid 2>/dev/null; wait $pid 2>/dev/null
  [ -s "$5" ] && printf "  ✓ %-34s %s\n" "$(basename "$5")" "$(du -h "$5" | cut -f1)" \
              || printf "  ✗ %-34s 失败\n" "$(basename "$5")"
}

WANT="${*:-shang zhou}"
for s in $WANT; do
  echo "[$s]"
  [ -f "$B/evolution-$s-std.html" ] && {
    shot "evolution-$s-std" 1920 1080 1 "$OUT/$s-1920x1080.png"
    shot "evolution-$s-std" 1920 1080 2 "$OUT/$s-3840x2160.png"
  }
  [ -f "$B/evolution-$s-mac.html" ] && \
    shot "evolution-$s-mac" 1920 1248 2 "$OUT/$s-3840x2496.png"
done
echo "── 完成 ──"
echo "产出：$(ls -1 "$OUT"/*.png 2>/dev/null | wc -l | tr -d ' ') 张 → $OUT"
