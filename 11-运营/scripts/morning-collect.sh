#!/bin/zsh
# 第七境 · 晨检一站式采集器 v1.0（2026-11-06 成本手术产物）
#
# 目的：把晨检里十几个「一命令一轮」的采集步骤合并成 1-3 次工具调用，
#       成本 = 轮次 × 上下文高度 ⇒ 轮次是最大杠杆（11-06 诊断：25 轮 93.5 分）。
# 用法：zsh morning-collect.sh [step ...]      # 无参数 = 全部步骤按序执行
# 步骤：sync site baidu perf cf xhs dy draft credits todos ds review slim tidy
# 设计：
#   ① 每步独立容错：单步失败不中断，输出 exit=N，照旧走完 —— 配合「失败一次即降级」铁律；
#   ② 幂等/缓存：perf（morning-perf.json 当日缓存）、credits（/tmp/credits-MMDD.json 当日只取一次）、
#      review（当日报告已存在即跳过）、draft（脚本自带 already-saved 幂等）；
#   ③ 完整日志：11-运营/data/morning-collect/MMDD.log（stdout 每步最多尾部 3500 字符，防上下文爆炸）。
set -u
cd "$(dirname "$0")/../.."   # 定位到空间根
ROOT="$PWD"
NODE="/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-6/bin/node"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
TODAY=$(date +%F)
LOGDIR="11-运营/data/morning-collect"
LOG="$LOGDIR/$(date +%m%d).log"
CAP=3500
mkdir -p "$LOGDIR"

# ---------- 各步骤 ----------
step_gate() {
  python3 11-运营/scripts/model-cost-gate.py
}
step_sync() {
  zsh 11-运营/scripts/qj-sync.sh auto "晨检前自动同步（采集器）"
}
step_site() {
  for u in "https://theseventhrealm.com/" "https://theseventhrealm.com/5000years/"; do
    echo -n "$u → "
    curl -s -o /dev/null -m 30 -A "$UA" -w "%{http_code} / %{time_total}s\n" "$u" || echo "curl 失败"
  done
  echo -n "http→https（应 301/308）: "
  curl -s -o /dev/null -m 15 -A "$UA" -w "%{http_code}\n" "http://theseventhrealm.com/" || echo "curl 失败"
  echo -n "logo-banner.png: "
  curl -s -o /dev/null -m 15 -A "$UA" -w "%{http_code}\n" "https://theseventhrealm.com/wp-content/uploads/2026/09/logo-banner.png" || echo "curl 失败"
  echo "-- 证书（subject 应=theseventhrealm.com；剩余<30天要提醒续期）："
  echo | openssl s_client -servername theseventhrealm.com -connect theseventhrealm.com:443 2>/dev/null | openssl x509 -noout -subject -issuer -enddate 2>/dev/null || echo "取证书失败"
  echo "-- DNS（应为 104.x/172.67.x/188.114.x；118.139.183.234 = 橙云被关🔴）："
  dig +short theseventhrealm.com A | head -4
}
step_baidu() {
  echo "-- 爬虫可达性（Baiduspider）："
  python3 11-运营/scripts/check-crawler-access.py 2>&1 | tail -5
  echo "-- 百度收录数："
  local bi
  bi=$(curl -s -m 15 -A "$UA" "https://www.baidu.com/s?wd=site%3Atheseventhrealm.com" | grep -oE '找到相关结果数[^,，<]{0,30}' | head -1)
  echo "${bi:-取不到（已 35 天+取不到，常态）}"
  echo "-- 百度 API 推送（日额度 10，脚本自动去重）："
  if source 11-运营/baidu-push-auth.sh 2>/dev/null; then
    python3 11-运营/scripts/baidu-push.py --limit 10 2>&1 | tail -3
  else
    echo "baidu-push-auth.sh 加载失败"
    return 1
  fi
}
step_perf() {
  if grep -q "$TODAY" 11-运营/data/morning-perf.json 2>/dev/null; then
    echo "今日已采（缓存），morning-perf.json："
    cat 11-运营/data/morning-perf.json
  else
    python3 11-运营/scripts/perf-check.py
  fi
}
step_budget() {
  python3 11-运营/scripts/credits-budget.py
}
step_cf() {
  python3 11-运营/scripts/cf-analytics.py all
}
step_xhs() {
  zsh 11-运营/scripts/xhs-stats.sh
}
step_dy() {
  zsh 11-运营/scripts/dy-stats.sh
}
step_draft() {
  # 脚本自带幂等：存过的 day 记在 xhs-draft-log.json，重复跑返回 already-saved
  "$NODE" 11-运营/scripts/xhs-draft.mjs
}
step_credits() {
  local cache="/tmp/credits-$(date +%m%d).json"
  if [ -s "$cache" ]; then
    echo "今日已取（缓存，当天只跑一次铁律）："
    cat "$cache"
  else
    local out
    out=$(bash 11-运营/scripts/fetch-credits.sh 2>&1)
    echo "$out"
    if echo "$out" | grep -q '"ok":true'; then
      echo "$out" > "$cache"
      echo "（已落盘 $cache）"
    else
      echo "fetch 失败，未缓存；当天不再重试"
      return 1
    fi
  fi
}
step_todos() {
  python3 11-运营/scripts/daily-todos.py
}
step_ds() {
  echo "DeepSeek 余额（launchd 21:00 自动记账，最后两行）："
  tail -2 11-运营/data/deepseek-balance.csv
}
step_review() {
  local r="11-运营/reports/每日改动评审-$TODAY.md"
  if [ -f "$r" ]; then
    echo "今日报告已存在（缓存）：$r"
    head -30 "$r"
  else
    python3 11-运营/scripts/daily-change-review.py --hours 24
  fi
}
step_slim() {
  python3 11-运营/scripts/context-daily-slim.py --apply
}
step_tidy() {
  python3 11-运营/scripts/memory-tidy.py --check
}

# ---------- 执行器 ----------
# todos 用「头部截断」（Top5 在输出开头）；其余步骤默认尾部截断（摘要在结尾）
run_step() {
  local name="$1" fn="$2" mode="${3:-tail}"
  echo ""
  echo "===== [$name] ====="
  local out rc n
  out=$("$fn" 2>&1); rc=$?
  { echo ""; echo "===== [$name] exit=$rc ====="; printf '%s\n' "$out"; } >> "$LOG"
  n=$(printf '%s' "$out" | wc -c | tr -d ' ')
  if [ "$n" -gt "$CAP" ]; then
    if [ "$mode" = "head" ]; then
      printf '%s' "$out" | head -c "$CAP"
    else
      printf '%s' "$out" | tail -c "$CAP"
    fi
    echo ""
    echo "...（已截断 / 全量 ${n} 字符，完整输出见 $LOG，需要再定向读）"
  else
    printf '%s\n' "$out"
  fi
  echo "[$name] exit=$rc"
}

ALL_STEPS=(sync site baidu perf budget cf xhs dy draft credits todos ds review slim tidy)
steps=("$@")
[ $# -eq 0 ] && steps=("${ALL_STEPS[@]}")

echo "morning-collect v1.2 $(date '+%F %T')｜参数：$*｜工作目录：$ROOT" | tee -a "$LOG"

# ---------- 模型性价比闸门（2026-11-06 用户指令：晨检第一步）----------
# 倍率过高 ⇒ 直接中止，一个采集步骤都不跑、不做 Git 落盘。
GATE_OUT=$(python3 11-运营/scripts/model-cost-gate.py 2>&1); GATE_RC=$?
{ echo ""; echo "===== [gate] ====="; printf '%s\n' "$GATE_OUT"; echo "===== [gate] exit=$GATE_RC ====="; } >> "$LOG"
echo ""
echo "===== [gate] ====="
printf '%s\n' "$GATE_OUT"
if [ "$GATE_RC" -eq 3 ]; then
  echo "[gate] exit=3"
  echo "🔴 模型性价比不合格 ⇒ 采集器已中止（未执行任何采集步骤，未做任何落盘）。请切换到低成本模型后重跑。"
  exit 3
fi
echo "[gate] exit=$GATE_RC"

bad=0
for s in "${steps[@]}"; do
  case "$s" in
    gate)
      echo "[gate] 已在闸门检查中执行过，跳过重复运行"
      ;;
    sync|site|baidu|perf|budget|cf|xhs|dy|draft|credits|todos|ds|review|slim|tidy)
      if [ "$s" = "todos" ]; then
        run_step "$s" "step_$s" head
      else
        run_step "$s" "step_$s" tail
      fi
      ;;
    *)
      echo "未知步骤：$s（合法：${ALL_STEPS[*]}）"
      bad=1
      ;;
  esac
done
echo ""
echo "采集完成。完整日志：$LOG"
[ "$bad" -eq 1 ] && exit 2
exit 0
