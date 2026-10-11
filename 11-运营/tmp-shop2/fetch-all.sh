#!/bin/bash
cd /Users/billyhou/WorkBuddy/2026-09-25-15-56-17
for id in 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109 134; do
  bash 11-运营/tmp-shop2/fetch.sh "$id" "11-运营/tmp-shop2/raw/p$id.json"
  sleep 0.5
done
echo "=== ALL DONE ==="
ls -la 11-运营/tmp-shop2/raw/
