#!/usr/bin/env bash
# 第七境 · 朝代页排版修正：备份 + 提交 + 回读校验
set -uo pipefail
cd /Users/billyhou/WorkBuddy/2026-09-25-15-56-17
source 11-运营/wp-auth.sh

BK="11-运营/风险管控/站点改动备份-20261002"
mkdir -p "$BK" "11-运营/tmp-fix/out"

page_name() {
  case "$1" in
    98) echo "秦" ;;
    99) echo "汉" ;;
    100) echo "三国" ;;
    101) echo "两晋" ;;
    *) echo "page$1" ;;
  esac
}

IDS=("$@")
[ ${#IDS[@]} -eq 0 ] && IDS=(98 99 100 101)

for ID in "${IDS[@]}"; do
  NAME="$(page_name "$ID")"
  echo "================ page $ID $NAME ================"

  # 1) 备份原文（原样）
  cp "11-运营/tmp-fix/raw-$ID.html" "$BK/page-$ID-$NAME-排版前.raw.html"
  echo "  备份 -> $BK/page-$ID-$NAME-排版前.raw.html ($(wc -c < "$BK/page-$ID-$NAME-排版前.raw.html" | tr -d ' ') bytes)"

  # 2) 生成 JSON 请求体
  python3 - "$ID" <<'PY'
import json,sys
pid=sys.argv[1]
new=open('11-运营/tmp-fix/new-%s.html'%pid,encoding='utf-8').read()
json.dump({"content":new}, open('11-运营/tmp-fix/out/payload-%s.json'%pid,'w',encoding='utf-8'),
          ensure_ascii=False)
PY

  # 3) POST（带重试）
  OK=0
  for try in 1 2 3 4; do
    CODE=$(curl -s --max-time 90 --noproxy '*' -o "11-运营/tmp-fix/out/resp-$ID.json" -w '%{http_code}' \
      -X POST -u "$WP_USER:$WP_APP_PASS" \
      -H "Content-Type: application/json; charset=utf-8" \
      --data-binary @"11-运营/tmp-fix/out/payload-$ID.json" \
      "https://theseventhrealm.com/wp-json/wp/v2/pages/$ID")
    echo "  POST try=$try http=$CODE"
    if [ "$CODE" = "200" ]; then OK=1; break; fi
    sleep 3
  done
  [ "$OK" = "1" ] || { echo "  ✗ POST 失败"; continue; }

  sleep 0.8

  # 4) 回读
  GOT=0
  for try in 1 2 3 4; do
    if curl -s --max-time 90 --noproxy '*' -u "$WP_USER:$WP_APP_PASS" \
        "https://theseventhrealm.com/wp-json/wp/v2/pages/$ID?context=edit" \
        -o "11-运营/tmp-fix/out/back-$ID.json"; then
      if python3 -c "
import json,sys
try:
    d=json.load(open('11-运营/tmp-fix/out/back-$ID.json'))
    sys.exit(0 if isinstance(d.get('content',{}).get('raw'),str) else 1)
except Exception:
    sys.exit(1)"; then GOT=1; break; fi
    fi
    echo "  GET 重试 $try"; sleep 3
  done
  [ "$GOT" = "1" ] || { echo "  ✗ 回读失败"; continue; }
  sleep 0.8

  # 5) 比对
  python3 - "$ID" <<'PY'
import json,re,sys
pid=int(sys.argv[1])
want=open('11-运营/tmp-fix/new-%d.html'%pid,encoding='utf-8').read()
got=json.load(open('11-运营/tmp-fix/out/back-%d.json'%pid))['content']['raw']
print('  回读一致:', got==want, '| 线上长度', len(got), '期望', len(want))
if got!=want:
    for i,(a,b) in enumerate(zip(got,want)):
        if a!=b:
            print('   首个差异 @',i,repr(got[max(0,i-40):i+40]),'||',repr(want[max(0,i-40):i+40])); break
    print('   长度差', len(got)-len(want))
PY
done
echo "ALL DONE"
