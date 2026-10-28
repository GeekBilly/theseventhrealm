#!/bin/bash
# mac-health.sh — 本机（MacBook）健康只读采集，月度执行一次
#
#   ⚠️ 硬约束：全程只读。绝不移动 / 重命名 / 删除 / 压缩任何文件。
#   ⚠️ 不触碰在线网站相关文件（seventhrealm-child 等仅统计体积，不读写其内容）。
#   ⚠️ 禁止对 02-商品 做全树 find/grep（实测会被 OOM kill，exit 137）；
#      本脚本只做 du -sk（体积）与 find -type f | wc -l（计数），不读文件内容。
#
# 用法：  bash 11-运营/scripts/mac-health.sh
# 产出：  1) stdout  人类可读摘要
#         2) 追加 CSV → 11-运营/data/mac-health-history.csv（长表，供下月环比）
#
# CSV 长表格式： date,category,item,size_mb,files,note
#   category: disk | root | project | hidden | personal | bigfile
#   长表好处：目录增删不需要改表头，环比直接按 (category,item) 配对。

set -u

PROJ="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
WB="/Users/billyhou/WorkBuddy"
CSV="$PROJ/11-运营/data/mac-health-history.csv"
TODAY="$(date +%F)"
NOW="$(date +'%F %H:%M')"

# 项目一级目录（NN-中文名 规范；旧名 wallpapers/ops/course/audio/community/plans 已作废，不再查找）
PROJECT_DIRS=(01-内容 02-商品 03-页面 04-市场 05-发布包 06-品牌 07-课程 \
              08-音频 09-社区 10-规划 11-运营 99-归档 seventhrealm-child)

# 需要单独盯的隐藏目录（du -sh */ 扫不到，历史上一度漏统计 554M）
HIDDEN_DIRS=("11-运营/.browser-profiles")

mkdir -p "$(dirname "$CSV")"
if [ ! -s "$CSV" ]; then
  echo "date,category,item,size_mb,files,note" > "$CSV"
fi

emit() { printf '%s,%s,"%s",%s,%s,%s\n' "$TODAY" "$1" "$2" "$3" "$4" "${5:-}" >> "$CSV"; }

# 体积（MB，一位小数）
mb() { local k; k=$(du -sk "$1" 2>/dev/null | awk '{print $1}'); [ -z "$k" ] && k=0; awk -v k="$k" 'BEGIN{printf "%.1f", k/1024}'; }
# 文件数
nf() { find "$1" -type f 2>/dev/null | wc -l | tr -d ' '; }

echo "===== Mac 健康采集 $NOW （只读）====="

# --- 1. 磁盘 ---
read -r AVAIL_GI USED_PCT <<<"$(df -h /System/Volumes/Data 2>/dev/null | awk 'NR==2{gsub(/Gi|G/,"",$4); gsub(/%/,"",$5); print $4, $5}')"
echo
echo "[磁盘] 剩余 ${AVAIL_GI}Gi / 已用 ${USED_PCT}%"
emit disk avail_gi "$AVAIL_GI" 0 "系统盘剩余Gi"
emit disk used_pct "$USED_PCT" 0 "系统盘占用率"

# --- 2. WorkBuddy 根一级子目录 ---
echo
echo "[WorkBuddy 根] 体积 / 文件数"
while IFS= read -r d; do
  s=$(mb "$d"); n=$(nf "$d")
  printf '  %-28s %8sM  %6s\n' "$(basename "$d")" "$s" "$n"
  emit root "$(basename "$d")" "$s" "$n" ""
done < <(find "$WB" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort)

# --- 3. 项目一级目录 ---
echo
echo "[项目一级目录] 体积 / 文件数"
for d in "${PROJECT_DIRS[@]}"; do
  p="$PROJ/$d"
  [ -d "$p" ] || { echo "  ⚠️ 缺失：$d"; continue; }
  s=$(mb "$p"); n=$(nf "$p")
  printf '  %-20s %8sM  %6s\n' "$d" "$s" "$n"
  emit project "$d" "$s" "$n" ""
done

# --- 4. 隐藏目录 ---
echo
echo "[隐藏目录] 体积 / 文件数"
for d in "${HIDDEN_DIRS[@]}"; do
  p="$PROJ/$d"
  [ -d "$p" ] || continue
  s=$(mb "$p"); n=$(nf "$p")
  printf '  %-28s %8sM  %6s\n' "$d" "$s" "$n"
  emit hidden "$d" "$s" "$n" "du -sh */ 扫不到，需单独盯"
done

# --- 5. 个人目录（只读出清单，绝不处理） ---
echo
echo "[个人目录] 体积 / 文件数（只读）"
for d in Downloads Desktop Documents; do
  p="/Users/billyhou/$d"
  [ -d "$p" ] || continue
  s=$(mb "$p"); n=$(nf "$p")
  printf '  %-28s %8sM  %6s\n' "$d" "$s" "$n"
  emit personal "$d" "$s" "$n" "只读，不处理"
done

# --- 6. 大文件 TOP 20（>20M），标注 >1GB ---
echo
echo "[大文件 TOP20 >20M] 个人目录"
# 用字节数排序（不能按 741M/21M 这类字符串排，会错序）。
# ⚠️ 必须写绝对路径 /usr/bin/stat 且用 "|" 分隔：实测 find -exec 里 `stat -f "%z %N"`（含空格的 format）
#    会被退化解析成「显示文件系统信息」，输出 "Inodes: Total: ..." 而非文件大小。
while IFS= read -r line; do
  bytes=${line%%|*}
  fp=${line#*|}
  m=$(awk -v b="$bytes" 'BEGIN{printf "%.0f", b/1048576}')
  flag=""
  [ "$bytes" -gt 1073741824 ] && flag="  ⚠️ >1GB"
  printf '  %6sM  %s%s\n' "$m" "$fp" "$flag"
  emit bigfile "$fp" "$m" 1 "${flag:+gt1GB}"
done < <(for d in /Users/billyhou/Downloads /Users/billyhou/Desktop /Users/billyhou/Documents; do
           find "$d" -type f -size +20M -exec /usr/bin/stat -f "%z|%N" {} \; 2>/dev/null
         done | sort -rn | head -20)

echo
echo "===== 采集完成，已追加 → $CSV ====="
echo "⚠️ 本脚本只读；任何归档/删除动作必须由用户确认具体路径后人工执行。"
