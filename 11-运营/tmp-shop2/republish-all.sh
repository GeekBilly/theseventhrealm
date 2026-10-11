#!/bin/bash
cd /Users/billyhou/WorkBuddy/2026-09-25-15-56-17
PY=/Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
OUT=11-运营/tmp-shop2/out
mkdir -p "$OUT"

emit() {  # emit <id> <htmlfile>
  $PY 11-运营/tmp-shop2/mkcontent.py "11-运营/tmp-shop2/body-re-$1.json" "$2"
}

echo "########## A. 17 个新页（修 style 空行） ##########"
emit 344 03-页面/collection-dynasty.html
bash 11-运营/tmp-shop2/pub.sh pages/344 11-运营/tmp-shop2/body-re-344.json "$OUT/re-344.json"
sleep 0.5
i=345
for slug in sanhuang xia shang zhou qin han sanguo jin sui tang wudai song yuan ming qing juexing; do
  emit $i "03-页面/collection-dynasty-$slug.html"
  bash 11-运营/tmp-shop2/pub.sh "pages/$i" "11-运营/tmp-shop2/body-re-$i.json" "$OUT/re-$i.json"
  sleep 0.5
  i=$((i+1))
done

echo "########## B. 16 个朝代页（修 style 空行） ##########"
for pid in 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109; do
  emit $pid "11-运营/tmp-shop2/stage3/p$pid.after.html"
  bash 11-运营/tmp-shop2/pub.sh "pages/$pid" "11-运营/tmp-shop2/body-re-$pid.json" "$OUT/re-$pid.json"
  sleep 0.5
done
echo "=== REPUBLISH DONE ==="
