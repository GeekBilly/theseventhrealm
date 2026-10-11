#!/bin/bash
# 用法：fetch.sh <page_id> <outfile>
source /Users/billyhou/WorkBuddy/2026-09-25-15-56-17/11-运营/wp-auth.sh >/dev/null 2>&1
id="$1"; out="$2"
for i in 1 2 3 4 5 6; do
  curl -s --noproxy '*' -u "$WP_USER:$WP_APP_PASS" -m 60 \
    "https://theseventhrealm.com/wp-json/wp/v2/pages/${id}?context=edit" -o "$out"
  sz=$(wc -c < "$out" | tr -d ' ')
  if [ "$sz" -gt 200 ]; then
    if /Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 -c "
import json,sys
try:
  d=json.load(open('$out'))
  assert 'content' in d and 'raw' in d['content']
except Exception:
  sys.exit(1)
" 2>/dev/null; then
      echo "OK $id size=$sz attempt=$i"
      exit 0
    fi
  fi
  sleep 2
done
echo "FAIL $id size=$(wc -c < "$out" | tr -d ' ')"
exit 1
