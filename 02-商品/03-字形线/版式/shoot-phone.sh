#!/bin/bash
# 字形线 A 线①「字体演变」· 手机竖版出图（2026-10-09 起**双画幅**）
#   ios      1179×2556  iPhone 15/16/17 Pro 原生 19.5:9
#   android  1080×2400  当代安卓主流 20:9
#   std      1080×1920  旧版 16:9（2026-10-09 起停发，仅供对照）
# ⚠️ 客户交付 = iOS 16 + Android 16 = 32 张；旧的那 16 张 1080×1920 不进客户包。
#
# 用法：
#   bash shoot-phone.sh                    # iOS + Android 各 16 张（默认）
#   bash shoot-phone.sh ios                # 只出 iOS
#   bash shoot-phone.sh android shang zhou # 指定画幅 + 指定朝
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/05-承接站/样张"
V="$ROOT/02-商品/03-字形线/版式"
OUT="$ROOT/02-商品/03-字形线/成品-演变/01-正式成品/手机竖版"
CP="/tmp/dsh-cp-phone"

wh_of()  { case "$1" in ios) echo "1179 2556";; android) echo "1080 2400";; std) echo "1080 1920";; esac; }
dir_of() { case "$1" in ios) echo "iOS";; android) echo "Android";; std) echo "_旧版-1080x1920";; esac; }

VARIANTS=""; SLUGS=""
for a in "$@"; do
  case "$a" in
    ios|android|std) VARIANTS="$VARIANTS $a";;
    *) SLUGS="$SLUGS $a";;
  esac
done
[ -n "$VARIANTS" ] || VARIANTS="ios android"

# ① 先按最新数据重生成竖版 HTML（HTML 与成品永远同源，画幅缩放只在生成器里）
cd "$V" || exit 1
for v in $VARIANTS; do
  if [ -n "$SLUGS" ]; then
    "$PY" gen-evolution-phone.py --variant "$v" $SLUGS >/dev/null || exit 1
  else
    "$PY" gen-evolution-phone.py --variant "$v" >/dev/null || exit 1
  fi
done

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

# ② 逐画幅 × 逐朝截图
for v in $VARIANTS; do
  set -- $(wh_of "$v")                      # ⚠️ 会覆盖 "$@"，所以上面已把参数存进 VARIANTS/SLUGS
  W=$1; H=$2
  D="$OUT/$(dir_of "$v")"; mkdir -p "$D"
  echo "[$v · ${W}×${H}] → 手机竖版/$(dir_of "$v")/"
  for f in "$B"/evolution-*-phone-$v.html; do
    [ -e "$f" ] || continue
    s="$(basename "$f" "-phone-$v.html")"; s="${s#evolution-}"
    [ -n "$SLUGS" ] && ! echo " $SLUGS " | grep -q " $s " && continue
    shot "evolution-$s-phone-$v" "$W" "$H" "$D/$s-${W}x${H}.png"
  done
done
echo "── 完成 ──"
for v in $VARIANTS; do
  echo "$(dir_of "$v")：$(ls -1 "$OUT/$(dir_of "$v")"/*.png 2>/dev/null | wc -l | tr -d ' ') 张"
done
