#!/bin/bash
# 金句线 · 手机竖版批量出图（16 朝 × iPhone/Android）
# 依赖：系统 Chrome 无头截图（agent-browser 对 file:// + 本地字体页易超时，不用）
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="${ROOT}/02-商品/05-承接站/样张"

"${PY}" "${ROOT}/02-商品/04-金句线/版式/gen-wallpaper-phone.py" --all || exit 1

shot() { # $1=html 名 $2=宽 $3=高
  "${CH}" --headless=new --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --force-device-scale-factor=1 \
    --window-size="$2","$3" --virtual-time-budget=6000 \
    --screenshot="${B}/${1%.html}.png" "file://${B}/$1" 2>/dev/null
}

n=0
for f in "${B}"/*-phone-iphone.html; do
  [ -e "$f" ] || continue
  shot "$(basename "$f")" 1179 2556; n=$((n + 1))
done
for f in "${B}"/*-phone-android.html; do
  [ -e "$f" ] || continue
  shot "$(basename "$f")" 1080 2400; n=$((n + 1))
done
echo "截图完成：${n} 张 -> ${B}"
