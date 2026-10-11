#!/bin/bash
# 字形线 · v9 桌面横版批量出图（商/周 × std/mac × 1x/2x）
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY="/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="${ROOT}/02-商品/05-承接站/样张"

"${PY}" "${ROOT}/02-商品/03-字形线/版式/gen-wallpaper-classic.py" "$@" || exit 1

shot() { # $1=html名 $2=宽 $3=高 $4=倍率
  "${CH}" --headless=new --disable-gpu --hide-scrollbars \
    --allow-file-access-from-files --force-device-scale-factor="$4" \
    --window-size="$2","$3" --virtual-time-budget=9000 \
    --screenshot="${B}/${1%.html}${5}.png" "file://${B}/$1" 2>/dev/null
}

n=0
for f in "${B}"/*-v9-std.html "${B}"/*-v9-mac.html; do
  [ -e "$f" ] || continue
  s="$(basename "$f")"
  case "$s" in *-mac.html) H=1248 ;; *) H=1080 ;; esac
  shot "$s" 1920 "$H" 1 ""       # 1920 宽
  shot "$s" 1920 "$H" 2 "-4k"    # 3840 宽
  n=$((n + 2))
done
echo "字形线出图完成：${n} 张 -> ${B}"
