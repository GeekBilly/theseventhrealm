#!/bin/bash
cd /Users/billyhou/WorkBuddy/2026-09-25-15-56-17
PY=/Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
PARENT=344
for slug in sanhuang xia shang zhou qin han sanguo jin sui tang wudai song yuan ming qing juexing; do
  name="collection-dynasty-$slug"
  title=$(cat "03-页面/$name.title")
  $PY 11-运营/tmp-shop2/mkbody.py "11-运营/tmp-shop2/body-$slug.json" "$title" "$slug" "$PARENT" "03-页面/$name.html"
  bash 11-运营/tmp-shop2/pub.sh pages "11-运营/tmp-shop2/body-$slug.json" "11-运营/tmp-shop2/out/$slug.json"
  $PY -c "
import json
d=json.load(open('11-运营/tmp-shop2/out/$slug.json'))
print('  => id=%s link=%s parent=%s' % (d['id'], d['link'], d['parent']))
"
  sleep 0.5
done
echo "=== CHILDREN DONE ==="
