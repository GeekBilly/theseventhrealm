#!/bin/bash
# 单次发布的数据登记 —— 早/晚碎片 5 分钟内做完
#
# 用法（二选一）：
#   ① 交互式（推荐，不用记参数）：   ./log.sh
#   ② 一行式（数字必须是真数字）：  ./log.sh -p 小红书 -a 商-字形演变 -i 320 -l 18 -s 12 -c 2
#
# 参数（不填记 0）：
#   -p 平台：小红书 / 抖音 / B站（也认 IG / Pinterest / Reddit 等旧名）
#   -a 内容标识，如 商-字形演变
#   -i 曝光   -l 赞   -s 收藏   -c 评论
#   -k 外链点击   -e 新增邮箱   -n 备注
#
# ⚠️ 常见坑：别把“占位符”原样粘进命令里。
#   zsh/bash 里 < 和 > 是重定向符号，写 -i <曝光> 会直接报
#   「parse error near '\n'」，脚本根本不会被执行。
#   数字还没抄到就先跑交互式，直接回车即记 0。

set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
CSV="$DIR/发布数据.csv"

usage() {
  sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# 数字兜底：非负整数才收，否则报错退出（不写脏数据）
is_num() { case "$1" in ''|*[!0-9]*) return 1 ;; *) return 0 ;; esac; }

check_nums() {
  for pair in "曝光:$I" "赞:$L" "收藏:$S" "评论:$C" "外链点击:$K" "新增邮箱:$E"; do
    v="${pair#*:}"
    [ -z "$v" ] && continue
    if ! is_num "$v"; then
      echo "❌ ${pair%%:*} 的值「${v}」不是数字，未写入。"
      echo "   数字还没抄到就留空；注意 <曝光> 这类占位符会被 shell 当成重定向符，"
      echo "   命令根本不会执行到脚本（报 parse error near '\\n'）。"
      exit 1
    fi
  done
}

[ -f "$CSV" ] || printf 'date,platform,asset,impressions,likes,saves,comments,clicks,emails,note\n' > "$CSV"

P=""; A=""; I=0; L=0; S=0; C=0; K=0; E=0; N=""

if [ $# -gt 0 ]; then
  while getopts "p:a:i:l:s:c:k:e:n:h" opt; do
    case "$opt" in
      p) P="$OPTARG";; a) A="$OPTARG";; i) I="$OPTARG";;
      l) L="$OPTARG";; s) S="$OPTARG";; c) C="$OPTARG";;
      k) K="$OPTARG";; e) E="$OPTARG";; n) N="$OPTARG";;
      h) usage 0;;
      *) usage 1;;
    esac
  done
  shift $((OPTIND - 1))
  if [ $# -gt 0 ]; then echo "❌ 有多余参数：$*"; usage 1; fi
  if [ -z "$P" ]; then echo "❌ 缺 -p 平台（小红书 / 抖音 / B站）"; usage 1; fi
  check_nums
else
  read -r -p "平台（小红书 / 抖音 / B站）： " P
  read -r -p "内容标识（如 商-字形演变）： " A
  read -r -p "曝光（直接回车＝0）： " I
  read -r -p "赞（回车＝0）： " L
  read -r -p "收藏（回车＝0）： " S
  read -r -p "评论（回车＝0）： " C
  read -r -p "外链点击（回车＝0）： " K
  read -r -p "新增邮箱（回车＝0）： " E
  read -r -p "备注（回车跳过）： " N
  check_nums
fi

DATE="$(date +%F)"
: "${I:=0}" "${L:=0}" "${S:=0}" "${C:=0}" "${K:=0}" "${E:=0}"

printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,"%s"\n' \
  "$DATE" "$P" "$A" "$I" "$L" "$S" "$C" "$K" "$E" "$N" >> "$CSV"

echo "已记：$DATE  $P  $A  (曝光$I 赞$L 藏$S 评$C 点$K 邮箱$E)"

# 主 KPI 已于 2026-10-11 改为平台内四件套（收藏率为主），不再以邮箱为目标
awk -F, 'NR>1 && $3 != "" { n++; imp+=$4; sav+=$6 }
END{
  if (n == 0) { print "台账仍为 0 条数据 —— 第一条要到发布满 72 小时再判。"; exit }
  printf "台账 %d 条｜累计曝光 %d｜平均收藏率 %.2f%%（判据 ≥3%%）\n", n, imp, (imp ? 100*sav/imp : 0)
}' "$CSV"

echo "看板：cd \"$DIR\" && python3 build-dashboard.py  然后打开 看板.html"
