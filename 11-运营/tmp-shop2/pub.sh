#!/bin/bash
# WP 发布助手（带 JSON 容错重试）。用法：pub.sh <endpoint> <bodyfile> <outfile>
#   endpoint 例：pages  或  pages/134
cd /Users/billyhou/WorkBuddy/2026-09-25-15-56-17 || exit 1
source 11-运营/wp-auth.sh >/dev/null 2>&1
ep="$1"; body="$2"; out="$3"
PY=/Users/billyhou/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3
for i in 1 2 3 4 5; do
  code=$(curl -s --noproxy '*' -u "$WP_USER:$WP_APP_PASS" -m 180 \
    -H 'Content-Type: application/json; charset=utf-8' \
    -X POST --data-binary @"$body" \
    "https://theseventhrealm.com/wp-json/wp/v2/$ep" -o "$out" -w '%{http_code}')
  ok=$("$PY" -c "
import json
try:
    d=json.load(open('$out'))
    print('OK' if isinstance(d,dict) and 'id' in d else 'NOID')
except Exception:
    print('BAD')
" 2>/dev/null)
  echo "  [$ep] attempt $i http=$code json=$ok"
  if [ "$ok" = "OK" ]; then exit 0; fi
  sleep 3
done
echo "  [$ep] FAILED after 5 attempts"
exit 1
