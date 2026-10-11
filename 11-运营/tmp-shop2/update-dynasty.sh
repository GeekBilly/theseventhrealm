#!/bin/bash
cd /Users/billyhou/WorkBuddy/2026-09-25-15-56-17
for pid in 94 95 96 97 98 99 100 101 102 103 104 105 106 107 108 109; do
  echo "--- page $pid ---"
  bash 11-运营/tmp-shop2/pub.sh "pages/$pid" "11-运营/tmp-shop2/stage3/p$pid.body.json" "11-运营/tmp-shop2/out/upd$pid.json"
  sleep 0.5
done
echo "=== UPDATES DONE ==="
