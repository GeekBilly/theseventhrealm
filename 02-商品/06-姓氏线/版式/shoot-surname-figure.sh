#!/bin/bash
# 姓氏线 · 人物底纹版（v3 实验）· 截图
#
# 用法：
#   bash shoot-surname-figure.sh                      # _build-figure 全部 HTML，1x → /tmp 或 --out
#   bash shoot-surname-figure.sh --out DIR            # 指定输出目录
#   bash shoot-surname-figure.sh --only 001           # 只切指定序号
#   bash shoot-surname-figure.sh --4k                 # 加出 4K
#
# ⚠️ 每个截图使用独立 user-data-dir（共用会互相抢）
# ⚠️ macOS 上 headless=new 截完图不会自己退出：后台起 + 轮询文件 + kill
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
B="$ROOT/02-商品/06-姓氏线/版式/_build-figure"
OUT="$ROOT/02-商品/06-姓氏线/成品-桌面-figure"
CPROOT="$B/_cp"
ONLY=()
JOBS=3
K4=0

while [ $# -gt 0 ]; do
  case "$1" in
    --only) shift; while [ $# -gt 0 ] && [[ "$1" != --* ]]; do ONLY+=("$1"); shift; done ;;
    --out)  OUT="$2"; shift 2 ;;
    --4k)   K4=1; shift ;;
    *) shift ;;
  esac
done

mkdir -p "$OUT" "$CPROOT"
T0=$(date +%s)

shot() { # $1=stem $2=scale $3=suffix
  local stem="$1" sc="$2" sfx="$3"
  local o="$OUT/$stem$sfx.png"
  local cp="$CPROOT/$(echo "$stem$sfx" | tr -c 'A-Za-z0-9-_' '_')"
  rm -rf "$cp"; mkdir -p "$cp"; rm -f "$o"
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
  case "$stem" in *--*) ;; *) continue ;; esac
  if [ ${#ONLY[@]} -gt 0 ]; then
    hit=0; for o in "${ONLY[@]}"; do [[ "$stem" == *"-$o-"* ]] && hit=1; done
    [ "$hit" -eq 0 ] && continue
  fi
  shot "$stem" 1 "" &
  PIDS[${#PIDS[@]}]=$!; NT=$((NT+1))
  while [ ${#PIDS[@]} -ge "$JOBS" ]; do sleep 0.3; prune; done
  if [ "$K4" -eq 1 ]; then
    shot "$stem" 2 "-4k" &
    PIDS[${#PIDS[@]}]=$!; NT=$((NT+1))
    while [ ${#PIDS[@]} -ge "$JOBS" ]; do sleep 0.3; prune; done
  fi
done
wait

T1=$(date +%s)
echo "── 完成：$(( (T1-T0)/60 ))分$(( (T1-T0)%60 ))秒 · 出图 $NT 张 → $OUT"
