#!/bin/bash
# ============================================================
# 第七境 · 品牌舆论哨兵（零成本 / 只读 / 本地）
#
# 【实测数据源结论 · 2026-09-30，改脚本前必读】
#   1. Google News RSS   —— http=000，国内不可达
#   2. DuckDuckGo HTML   —— http=000，不可达
#   3. Bing RSS(&format=rss) —— ⚠️ 返回 200 但内容是**与查询无关的兜底结果**
#      查「"第七境"」返回汉字「第」的字典解释，查 theseventhrealm.com 返回 Excel 教程。
#      三个不同查询返回结果几乎一样 → 证明是缓存兜底，不是真实索引。
#      **比不可用更危险**：会让人误以为"监测跑通了、没有提及"。已弃用。
#   4. 搜狗微信 (weixin.sogou.com) —— ✅ 唯一实测可用，返回真实结果
#      ⚠️ 有反爬频率限制，务必低频运行（月度一次），失败一次即降级为人工清单。
#
# 【设计原则】
#   - 只做「自有阵地 + 单一可用源」的最小哨兵，不做全网抓取。
#     真相：对一个零起步的新品牌，99% 的真实反馈发生在自己渠道的评论/私信里，
#     不在全网。全网监测属于 Phase 2 才值得花钱买 API（新榜/清博）的事。
#   - 每条结果都要过「完整品牌词」过滤：搜狗返回模糊结果，
#     只有标题或摘要含"第七境"/"theseventhrealm"才计为命中，其余计为噪声丢弃。
#
# 用法：
#   bash 11-运营/scripts/brand-watch.sh            # 扫描并归档
#   bash 11-运营/scripts/brand-watch.sh --quiet    # 只输出结论行（供自动化读取）
#
# 退出码：0=无提及 2=有提及需人工看 3=抓取失败（降级）
# ============================================================

ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
DATA="${ROOT}/11-运营/data"
OUT="${DATA}/brand-watch.csv"
LOG="${ROOT}/11-运营/reports/品牌舆论哨兵-$(date +%Y-%m).md"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

mkdir -p "$DATA" "${ROOT}/11-运营/reports"
[ -f "$OUT" ] || printf 'date,source,keyword,title,url,hit\n' > "$OUT"

TODAY=$(date +%Y-%m-%d)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

SCAN_OK=0
SCAN_FAIL=0

scan() {
  local kw="$1"
  local enc
  enc=$(/usr/bin/python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$kw")
  local f="${TMP}/$(echo -n "$kw" | md5).html"
  local code
  code=$(curl -s -L --max-time 20 -A "$UA" \
    "https://weixin.sogou.com/weixin?type=2&query=${enc}" -o "$f" -w '%{http_code}')
  if [ "$code" != "200" ] || [ ! -s "$f" ]; then
    SCAN_FAIL=$((SCAN_FAIL + 1))
    return
  fi
  if grep -qE '请输入验证码|antispider|访问过于频繁' "$f"; then
    SCAN_FAIL=$((SCAN_FAIL + 1))
    return
  fi
  SCAN_OK=$((SCAN_OK + 1))
  /usr/bin/python3 - "$kw" "$f" "$OUT" "$TODAY" <<'PY'
import re, sys, csv, html

kw, path, out, today = sys.argv[1:5]
raw = open(path, encoding='utf-8', errors='replace').read()

# 品牌词（判定"真提及"的硬门槛）
BRANDS = ['第七境', 'theseventhrealm', 'the seventh realm']

blocks = re.findall(r'<li id="sogou_vr_1100261_box_\d+".*?</li>', raw, re.S)
if not blocks:
    blocks = re.findall(r'<li[^>]*>.*?</li>', raw, re.S)

rows = []
for b in blocks:
    tm = re.search(r'<h3>(.*?)</h3>', b, re.S)
    if not tm:
        continue
    title = html.unescape(re.sub(r'<[^>]+>', '', tm.group(1))).strip()
    lm = re.search(r'href="(/link\?url=[^"]+|https?://[^"]+)"', b)
    url = lm.group(1) if lm else ''
    if url.startswith('/link'):
        url = 'https://weixin.sogou.com' + url
    dm = re.search(r'<p[^>]*class="txt-info"[^>]*>(.*?)</p>', b, re.S) or \
         re.search(r'<p[^>]*>(.*?)</p>', b, re.S)
    desc = html.unescape(re.sub(r'<[^>]+>', '', dm.group(1))).strip() if dm else ''
    blob = (title + ' ' + desc).lower()
    hit = any(x in blob for x in BRANDS)
    if title:
        rows.append((hit, title, url))

seen = set()
with open(out, 'a', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    for hit, title, url in rows:
        if title in seen:
            continue
        seen.add(title)
        w.writerow([today, '搜狗微信', kw, title, url, '命中' if hit else '噪声'])

hits = [r for r in rows if r[0]]
print(f"[{kw}] 返回 {len(rows)} 条，其中品牌真命中 {len(hits)} 条")
for _, t, u in hits[:5]:
    print(f"    ★ {t[:44]}")
PY
}

echo "── 品牌舆论哨兵 ${TODAY} ──"
for kw in "第七境" "第七境 上下五千年" "theseventhrealm"; do
  scan "$kw"
  sleep 2
done

NOISE=$(/usr/bin/python3 -c "
import csv
rows=list(csv.DictReader(open('$OUT',encoding='utf-8')))
today=[r for r in rows if r['date']=='$TODAY']
print(len([r for r in today if r['hit']=='命中']), len(today))
")
HIT_CNT=$(echo "$NOISE" | awk '{print $1}')
ALL_CNT=$(echo "$NOISE" | awk '{print $2}')

{
  echo ""
  echo "## ${TODAY}"
  echo ""
  if [ "$SCAN_OK" -eq 0 ]; then
    echo "- ⚠️ **抓取失败**（源不可达或触发反爬）→ 降级为人工检索清单"
    echo "  - 人工入口：<https://weixin.sogou.com/weixin?type=2&query=%E7%AC%AC%E4%B8%83%E5%A2%83>"
    echo "  - 并巡查四个自有渠道的消息红点（抖音/小红书/B站/知乎）"
  else
    echo "- 扫描源：搜狗微信 × ${SCAN_OK} 组关键词；本次返回 ${ALL_CNT} 条，品牌真命中 **${HIT_CNT}** 条"
    if [ "$HIT_CNT" -gt 0 ]; then
      echo "- ⚠️ **有命中，需人工判定**：对照 \`11-运营/风险管控/品牌舆论管理.md\` §四 升级矩阵，确认是资产（正面）还是风险（负面/仿冒）"
    else
      echo "- ✅ 无品牌提及，属正常（品牌尚在 Phase 0，无人讨论是预期状态）"
    fi
  fi
  echo ""
} >> "$LOG"

echo ""
if [ "$SCAN_OK" -eq 0 ]; then
  echo "结论：抓取失败 → 请人工检索（见 ${LOG}）"
  exit 3
elif [ "$HIT_CNT" -gt 0 ]; then
  echo "结论：命中 ${HIT_CNT} 条 → 请人工判定（对照升级矩阵）"
  exit 2
else
  echo "结论：无品牌提及（正常）"
  exit 0
fi
