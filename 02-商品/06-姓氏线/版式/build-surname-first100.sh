#!/bin/bash
# 姓氏线 · 首批 100 姓出图（1x + 4K）
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/05-承接站/样张"
OUT="$ROOT/02-商品/06-姓氏线/成品-桌面"
CP="/tmp/dsh-cp-surname"
N="${1:-100}"

mkdir -p "$OUT"
echo "── 1. 生成 HTML（前 $N 姓）──"
"$PY" "$ROOT/02-商品/06-姓氏线/版式/gen-surname-wallpaper.py" --first "$N" 2>&1 | tail -1

shot() { # $1=html stem $2=倍率 $3=后缀
  local o="$OUT/$1$3.png"; rm -f "$o"
  "$CH" --headless=new --no-sandbox --disable-setuid-sandbox --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --user-data-dir="$CP" --force-device-scale-factor="$2" \
    --window-size=1920,1080 --virtual-time-budget=7000 \
    --screenshot="$o" "file://$B/$1.html" >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 100); do [ -s "$o" ] && break; sleep 0.4; done
  sleep 0.5; kill $pid 2>/dev/null; wait $pid 2>/dev/null
  [ -s "$o" ] && echo "  ✓ $1$3.png" || echo "  ✗ $1$3.png 失败"
}

echo "── 2. 1x 渲染 ──"
n=0
for f in "$B"/surname-*.html; do
  [ -e "$f" ] || continue
  s="$(basename "$f" .html)"
  shot "$s" 1 ""; n=$((n+1))
  [ "$n" -ge "$N" ] && break
done

echo "── 3. 4K 渲染 ──"
n=0
for f in "$B"/surname-*.html; do
  [ -e "$f" ] || continue
  s="$(basename "$f" .html)"
  shot "$s" 2 "-4k"; n=$((n+1))
  [ "$n" -ge "$N" ] && break
done

echo "── 完成 ──"
echo "产出：$(ls -1 "$OUT"/*.png 2>/dev/null | wc -l | tr -d ' ') 张 → $OUT"
