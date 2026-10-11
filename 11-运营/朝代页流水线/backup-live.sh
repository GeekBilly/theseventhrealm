#!/bin/bash
# 把线上 16 个朝代页的当前内容备份到本地，作为发布前的回滚点。
# 只读操作，不改动线上。
#   bash 11-运营/朝代页流水线/backup-live.sh
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
. "$(dirname "$0")/../wp-auth.sh" || exit 1
SITE="${SITE:-https://theseventhrealm.com}"   # 必须 apex：www 会 301，缺 -L 会静默产出空备份
PY=/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3
STAMP=$(date +%F)
DIR="03-页面/备份/线上-$STAMP"
mkdir -p "$DIR"

SLUGS=(sanhuang xia shang zhou qin han sanguo jin sui tang wudai song yuan ming qing juexing)
echo "== 备份线上现版本 → $DIR =="
for slug in "${SLUGS[@]}"; do
  curl -s -L --max-time 30 -u "$WP_USER:$WP_APP_PASS" \
    "$SITE/wp-json/wp/v2/pages?slug=$slug&parent=32&status=any&per_page=1&context=edit" \
    -o /tmp/bk_$slug.json
  $PY - "$slug" "$DIR" <<'PY'
import json, sys, os
slug, outdir = sys.argv[1], sys.argv[2]
try:
    d = json.load(open('/tmp/bk_%s.json' % slug))
except Exception:
    print("  ✗ %s 解析失败（不可视为备份成功）" % slug); sys.exit(1)
if isinstance(d, list):
    d = d[0] if d else {}
if not d.get('id'):
    print("  ✗ %s 线上未找到" % slug); sys.exit(1)
raw = (d.get('content') or {}).get('raw', '') or ''
# 空内容必须报错：一份空备份比没有备份更危险（回滚时才发现救不回来）
if len(raw) < 100:
    print("  ✗ %s 内容为空（%d 字节），备份失败" % (slug, len(raw))); sys.exit(1)
open(os.path.join(outdir, '%s.html' % slug), 'w', encoding='utf-8').write(raw)
open(os.path.join(outdir, '%s.meta.txt' % slug), 'w', encoding='utf-8').write(
    "id=%s\nslug=%s\nstatus=%s\ntitle=%s\nmodified=%s\nlen=%d\n"
    % (d['id'], slug, d.get('status'), (d.get('title') or {}).get('rendered'),
       d.get('modified'), len(raw)))
print("  ✓ %-9s id=%-4s %6d 字节" % (slug, d['id'], len(raw)))
PY
done
echo
echo "回滚方式：把 $DIR/<slug>.html 用 publish.sh 同款 payload 发回对应 id 即可。"
