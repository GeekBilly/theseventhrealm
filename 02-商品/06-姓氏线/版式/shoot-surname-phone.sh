#!/bin/bash
# 姓氏线（B 线）· 手机出图（2026-10-21 建立，对应 A 线 shoot-phone.sh）
#   ios      1179×2556  iPhone 15/16/17 Pro 原生 19.5:9   ← 模板 v11-竖版（缩放）
#   android  1080×2400  当代安卓主流 20:9                  ← 模板 v11-竖版（缩放）
#   xhs      1179×1572  小红书 3:4                         ← 模板 v11-方版（不缩放，版式写死）
#   std      1080×1920  基准，仅供回归
#
# 用法：
#   bash shoot-surname-phone.sh                      # iOS + Android，全部 100 姓
#   bash shoot-surname-phone.sh xhs                  # 小红书 3:4，全部 100 姓
#   bash shoot-surname-phone.sh xhs 赵 钱 孙          # 指定画幅 + 指定姓
#
# ⚠️ 缺字（某体字体里没有这个字）的姓会被生成器标注 ⚠，仍出图 —— 出完务必看输出里的 ⚠ 行。
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.workbuddy/binaries/python/envs/default/bin/python"   # ⚠️ 必须是带 PIL 的环境
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/06-姓氏线/版式/_build-v2a"
V="$ROOT/02-商品/06-姓氏线/版式"
OUT="$ROOT/02-商品/06-姓氏线/成品-手机竖版"
CP="/tmp/dsh-cp-surname-phone"

wh_of()  { case "$1" in ios) echo "1179 2556";; android) echo "1080 2400";; std) echo "1080 1920";; xhs) echo "1179 1572";; esac; }
dir_of() { case "$1" in ios) echo "iOS";; android) echo "Android";; std) echo "基准-1080x1920";; xhs) echo "小红书-3x4";; esac; }
# 画幅 → 模板：3:4 走写死版式的方版，其余走缩放竖版
tpl_of() { case "$1" in xhs) echo square;; *) echo phone;; esac; }

VARIANTS=""; CHARS=""
for a in "$@"; do
  case "$a" in
    ios|android|std|xhs) VARIANTS="$VARIANTS $a";;
    *) CHARS="$CHARS $a";;
  esac
done
[ -n "$VARIANTS" ] || VARIANTS="ios android"
CHARS="$(echo $CHARS)"

shot() { # $1=stem $2=w $3=h $4=out
  rm -f "$4"
  "$CH" --headless=new --no-sandbox --disable-setuid-sandbox --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --user-data-dir="$CP" --force-device-scale-factor=1 \
    --window-size="$2","$3" --virtual-time-budget=8000 \
    --screenshot="$4" "file://$B/$1.html" >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 120); do [ -s "$4" ] && break; sleep 0.4; done
  sleep 0.6; kill $pid 2>/dev/null; wait $pid 2>/dev/null
  [ -s "$4" ] && printf "  ✓ %-40s %s\n" "$(basename "$4")" "$(du -h "$4" | cut -f1)" \
              || printf "  ✗ %-40s 失败\n" "$(basename "$4")"
}

cd "$V" || exit 1
for v in $VARIANTS; do
  T="$(tpl_of "$v")"
  # ① 先重生成 HTML（HTML 与成品永远同源）
  if [ -n "$CHARS" ]; then
    "$PY" gen-surname-v2a.py --tpl "$T" --variant "$v" $CHARS >/dev/null || exit 1
  else
    "$PY" gen-surname-v2a.py --tpl "$T" --variant "$v" --first 100 >/dev/null || exit 1
  fi

  # ② 逐张截图
  set -- $(wh_of "$v"); W=$1; H=$2
  D="$OUT/$(dir_of "$v")"; mkdir -p "$D"
  echo "[$v · ${W}×${H}] → 成品-手机竖版/$(dir_of "$v")/"
  # 方版的 stem 没有 variant 后缀（有且只有一种画幅）
  if [ "$T" = square ]; then SUF="-square"; else SUF="-phone-$v"; fi
  for f in "$B"/surname-*"$SUF".html; do
    [ -e "$f" ] || continue
    s="$(basename "$f" "$SUF.html")"
    ch="$(echo "$s" | sed 's/^surname-[0-9]*-//')"
    if [ -n "$CHARS" ] && ! echo " $CHARS " | grep -q " $ch "; then continue; fi
    shot "${s}${SUF}" "$W" "$H" "$D/${ch}-${W}x${H}.png"   # ⚠️ 必须带 $SUF，否则截到别的版式
  done
done
echo "── 完成 ──"
for v in $VARIANTS; do
  echo "$(dir_of "$v")：$(ls -1 "$OUT/$(dir_of "$v")"/*.png 2>/dev/null | wc -l | tr -d ' ') 张"
done
