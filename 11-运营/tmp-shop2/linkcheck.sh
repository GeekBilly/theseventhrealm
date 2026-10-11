#!/bin/bash
cd /Users/billyhou/WorkBuddy/2026-09-25-15-56-17
UA="Mozilla/5.0 (linkcheck)"
chk() { # chk <url>
  local code
  code=$(curl -s -o /dev/null --noproxy '*' -m 90 -A "$UA" -w '%{http_code}' "$1")
  printf '%s  %s\n' "$code" "$1"
}
echo "### 17 个新页（阶段二）"
chk "https://theseventhrealm.com/collection/dynasty/"
for s in sanhuang xia shang zhou qin han sanguo jin sui tang wudai song yuan ming qing juexing; do
  chk "https://theseventhrealm.com/collection/dynasty/$s/"
done
echo "### 16 个长卷页（阶段三链接目标）"
for s in sanhuang xia shang zhou qin han sanguo jin sui tang wudai song yuan ming qing juexing; do
  chk "https://theseventhrealm.com/5000years/$s/"
done
echo "### 商店首页与表单锚点"
chk "https://theseventhrealm.com/collection/"
curl -s --noproxy '*' -m 90 -A "$UA" "https://theseventhrealm.com/collection/" -o 11-运营/tmp-shop2/live-col-home.html
echo "signup 锚点数：$(grep -o 'id="signup"' 11-运营/tmp-shop2/live-col-home.html | wc -l | tr -d ' ')"
