#!/bin/bash
# 姓氏线 v2「方向 A · 一姓四体」· 截图（1x + 4K）
#
# 用法：
#   bash shoot-surname-v2a.sh                      # 全部 HTML，1x + 4K → 成品目录
#   bash shoot-surname-v2a.sh --1x                 # 只出 1x
#   bash shoot-surname-v2a.sh --1x --out DIR       # 输出到别处（测量轮用）
#   bash shoot-surname-v2a.sh --only 001 002       # 只切指定序号
#   bash shoot-surname-v2a.sh --jobs 4             # 并发 4 个 Chrome（默认 3）
#
# ⚠️ 每个截图使用**独立 user-data-dir**（共用会互相抢，试版踩过）
# ⚠️ macOS 上 headless=new 截完图不会自己退出：后台起 + 轮询文件 + kill
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/06-姓氏线/版式/_build-v2a"
OUT="$ROOT/02-商品/06-姓氏线/成品-桌面-v2A"
CPROOT="$B/_cp"
ONLY=()
SCALES=(1 2)
SUFFIX=("" "-4k")
JOBS=3

while [ $# -gt 0 ]; do
  case "$1" in
    --only) shift; while [ $# -gt 0 ] && [[ "$1" != --* ]]; do ONLY+=("$1"); shift; done ;;
    --out)  OUT="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --1x)   SCALES=(1); SUFFIX=(""); shift ;;   # ⚠️ 必须 shift，否则死循环
    *) shift ;;
  esac
done

mkdir -p "$OUT" "$CPROOT"
T0=$(date +%s)

shot() { # $1=stem $2=scale $3=suffix
  local stem="$1" sc="$2" sfx="$3"
  local o="$OUT/$stem$sfx.png"
  local cp="$CPROOT/$stem$sfx"
  rm -rf "$cp"; mkdir -p "$cp"
  rm -f "$o"
  "$CH" --headless=new --no-sandbox --disable-setuid-sandbox --disable-gpu \
    --hide-scrollbars --allow-file-access-from-files --disable-lcd-text \
    --no-first-run --no-default-browser-check --disable-sync \
    --disable-background-networking --disable-component-update \
    --disable-crash-reporter --disable-breakpad \
    --user-data-dir="$cp" --force-device-scale-factor="$sc" \
    --window-size=1920,1080 --virtual-time-budget=8000 \
    --screenshot="$o" "file://$B/$stem.html" >/dev/null 2>&1 &
  local pid=$! i
  for i in $(seq 1 80); do [ -s "$o" ] && break; sleep 0.5; done
  sleep 1.0
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  rm -rf "$cp"
  if [ -s "$o" ]; then echo "  ✓ $(basename "$o")"; else echo "  ✗ $(basename "$o") 失败"; fi
}

seq_of() { basename "$1" .html | sed 's/surname-\([0-9]*\)-.*/\1/'; }

# ⚠️ bash 3.2 没有 wait -n，且 $(jobs -rp) 在子 shell 里看不到父 shell 的任务，
#    所以自己用 PID 数组做并发闸门。
PIDS=()
prune() {
  local keep=() p
  if [ ${#PIDS[@]} -gt 0 ]; then
    for p in "${PIDS[@]}"; do kill -0 "$p" 2>/dev/null && keep[${#keep[@]}]="$p"; done
  fi
  if [ ${#keep[@]} -gt 0 ]; then PIDS=("${keep[@]}"); else PIDS=(); fi
}

NT=0
for f in "$B"/surname-*.html; do
  [ -e "$f" ] || continue
  stem="$(basename "$f" .html)"
  if [ ${#ONLY[@]} -gt 0 ]; then
    hit=0; for o in "${ONLY[@]}"; do [[ "$(seq_of "$f")" == "$o" ]] && hit=1; done
    [ "$hit" -eq 0 ] && continue
  fi
  for i in "${!SCALES[@]}"; do
    shot "$stem" "${SCALES[$i]}" "${SUFFIX[$i]}" &
    PIDS[${#PIDS[@]}]=$!
    NT=$((NT+1))
    while [ ${#PIDS[@]} -ge "$JOBS" ]; do sleep 0.3; prune; done
  done
done
wait

T1=$(date +%s)
echo "── 完成：$(( (T1-T0)/60 ))分$(( (T1-T0)%60 ))秒 · 出图 ${NT} 张 → $OUT"
ls -1 "$OUT"/surname-*.png 2>/dev/null | wc -l | xargs echo "   目录内 PNG 总数："
