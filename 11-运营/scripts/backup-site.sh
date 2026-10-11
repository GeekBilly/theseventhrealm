#!/bin/bash
# 第七境 · 站点内容备份（WordPress REST 导出 + 页面快照 + manifest）
#
# 用法：
#   bash 11-运营/scripts/backup-site.sh              # 做一次备份
#   bash 11-运营/scripts/backup-site.sh --verify      # 只校验最近一次备份是否新鲜完整（不写数据）
#   KEEP=12 bash 11-运营/scripts/backup-site.sh       # 保留份数，默认 6
#   BACKUP_MIRROR="/Users/.../某个云盘目录" bash 11-运营/scripts/backup-site.sh   # 异地镜像（可选）
#
# 设计口径：
#   - 凭据从 macOS 钥匙串取（见 11-运营/wp-auth.sh），不落盘、不进 git
#   - 只导出**内容**（页面/文章/媒体清单），不动数据库（编辑角色无此权限）
#   - 每次产出 manifest.json，含条目数、体积、SHA-256，供 --verify 与季度恢复演练比对
#   - 异地 3-2-1：默认只写本地；设了 BACKUP_MIRROR 才同步一份出去

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.."  && pwd)"
cd "$ROOT" || exit 1

SITE="${SITE:-https://theseventhrealm.com}"
KEEP="${KEEP:-6}"
DEST="$ROOT/11-运营/backup"
MIRROR="${BACKUP_MIRROR:-}"
VERIFY_ONLY=0
[ "${1:-}" = "--verify" ] && VERIFY_ONLY=1

latest_dir() { ls -1d "$DEST"/20* 2>/dev/null | tail -1; }

########################################
# 只校验：新鲜度 / 条数 / 完整性
########################################
if [ "$VERIFY_ONLY" -eq 1 ]; then
  d="$(latest_dir)"
  if [ -z "$d" ]; then
    echo "✗ 没有任何备份目录（$DEST/20*），R-02 备份风险未闭合"
    exit 2
  fi
  name="$(basename "$d")"
  age=$(( ( $(date +%s) - $(date -j -f "%Y-%m-%d" "${name:0:10}" "+%s" 2>/dev/null || echo 0) ) / 86400 ))
  mf="$d/manifest.json"
  ok_items=0
  [ -f "$mf" ] && /usr/bin/python3 -c "import json,sys;json.load(open('$mf'))" 2>/dev/null && ok_items=1
  pages=$([ -d "$d/pages" ] && ls -1 "$d/pages" | wc -l | tr -d ' ')
  posts=$([ -d "$d/posts" ] && ls -1 "$d/posts" | wc -l | tr -d ' ')
  snaps=$([ -d "$d/snapshots" ] && ls -1 "$d/snapshots" | wc -l | tr -d ' ')
  size=$(du -sm "$d" | awk '{print $1}')
  echo "最近备份：${name}（${age} 天前，${size}MB）"
  echo "  manifest 可解析： $([ "$ok_items" -eq 1 ] && echo ✅ || echo ✗)"
  echo "  页面 ${pages} / 文章 ${posts} / 快照 ${snaps}"
  bad=0
  [ "$age" -gt 40 ] && { echo "⚠️ 备份已超过 40 天未更新"; bad=1; }
  [ "$pages" -lt 20 ] && { echo "⚠️ 页面数 <20，疑似导出不全（当前站点应有 22+ 条已发布内容）"; bad=1; }
  [ "$ok_items" -ne 1 ] && { echo "⚠️ manifest.json 缺失或损坏"; bad=1; }
  [ "$bad" -eq 0 ] && echo "✅ 备份校验通过" || exit 2
  exit 0
fi

########################################
# 正式备份
########################################
# shellcheck disable=SC1091
. "$ROOT/11-运营/wp-auth.sh" || exit 1

STAMP="$(date +%F)"
OUT="$DEST/$STAMP"
mkdir -p "$OUT/pages" "$OUT/posts" "$OUT/meta" "$OUT/snapshots"
echo "备份目标：$OUT"

api() {  # $1=path
  curl -s -LS --max-time 40 -u "$WP_USER:$WP_APP_PASS" \
    -H "Accept: application/json" "$SITE/wp-json/wp/v2/$1"
}

# 1) 页面
echo -n "  导出页面… "
api "pages?per_page=100&status=publish,draft&_fields=id,slug,title,content,modified,status,parent,link" > "$OUT/meta/pages.json"
PAGES_N=$(/usr/bin/python3 -c "import json;d=json.load(open('$OUT/meta/pages.json'));print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo 0)
if [ "$PAGES_N" -gt 0 ]; then
  /usr/bin/python3 - "$OUT/meta/pages.json" "$OUT/pages" <<'PY'
import json,sys,os,re
src,dst=sys.argv[1],sys.argv[2]
for p in json.load(open(src,encoding='utf-8')):
    slug=re.sub(r'[^0-9A-Za-z\-_.]','_',p.get('slug') or str(p.get('id')))
    json.dump(p,open(os.path.join(dst,f"{p['id']}-{slug}.json"),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
PY
fi
echo "${PAGES_N} 条"

# 2) 文章
echo -n "  导出文章… "
api "posts?per_page=100&status=publish,draft&_fields=id,slug,title,content,modified,status,link" > "$OUT/meta/posts.json"
POSTS_N=$(/usr/bin/python3 -c "import json;d=json.load(open('$OUT/meta/posts.json'));print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo 0)
if [ "$POSTS_N" -gt 0 ]; then
  /usr/bin/python3 - "$OUT/meta/posts.json" "$OUT/posts" <<'PY'
import json,sys,os,re
src,dst=sys.argv[1],sys.argv[2]
for p in json.load(open(src,encoding='utf-8')):
    slug=re.sub(r'[^0-9A-Za-z\-_.]','_',p.get('slug') or str(p.get('id')))
    json.dump(p,open(os.path.join(dst,f"{p['id']}-{slug}.json"),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
PY
fi
echo "${POSTS_N} 条"

# 3) 媒体清单（可能无权限，失败不致命）
echo -n "  导出媒体清单… "
code=$(curl -s -L -o "$OUT/meta/media.json" -w "%{http_code}" --max-time 40 \
  -u "$WP_USER:$WP_APP_PASS" "$SITE/wp-json/wp/v2/media?per_page=100&_fields=id,slug,source_url,title,mime_type" 2>/dev/null)
if [ "$code" = "200" ]; then echo "ok"; else echo "跳过（HTTP ${code}，编辑角色可能无权限）"; rm -f "$OUT/meta/media.json"; fi

# 4) 关键页面 HTML 快照
echo -n "  抓取页面快照… "
SNAP_N=0
while IFS= read -r u; do
  [ -z "$u" ] && continue
  f="$OUT/snapshots/$(echo "$u" | sed 's#[^0-9A-Za-z]#_#g').html"
  if curl -s -LS --max-time 30 -o "$f" "$u"; then SNAP_N=$((SNAP_N+1)); fi
done <<EOF
$SITE/
$SITE/5000years/
$SITE/5000years/shang/
$SITE/5000years/zhou/
$SITE/5000years/qin/
$SITE/about/
$SITE/contact/
EOF
echo "${SNAP_N} 个"

# 5) manifest + 哈希
/usr/bin/python3 - "$OUT" "$PAGES_N" "$POSTS_N" "$SNAP_N" <<'PY'
import sys,os,json,hashlib,datetime
out,pages,posts,snaps=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4])
files={}
for dp,_,fs in os.walk(out):
    for f in fs:
        p=os.path.join(dp,f)
        if os.path.basename(p)=='manifest.json': continue
        h=hashlib.sha256()
        with open(p,'rb') as fh:
            for b in iter(lambda: fh.read(1<<20), b''): h.update(b)
        files[os.path.relpath(p,out)]={'size':os.path.getsize(p),'sha256':h.hexdigest()[:32]}
m={'created':datetime.datetime.now().isoformat(timespec='seconds'),
   'counts':{'pages':pages,'posts':posts,'snapshots':snaps,'files':len(files)},
   'total_bytes':sum(v['size'] for v in files.values()),'files':files}
json.dump(m,open(os.path.join(out,'manifest.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f"  manifest：{len(files)} 个文件 / {m['total_bytes']:,} 字节")
PY

# 6) 异地镜像（仅在设置了 BACKUP_MIRROR 时）
if [ -n "$MIRROR" ]; then
  echo -n "  异地镜像 → $MIRROR … "
  if mkdir -p "$MIRROR" 2>/dev/null && cp -R "$OUT" "$MIRROR/" 2>/dev/null; then echo "ok"; else echo "失败（检查路径是否有写权限）"; fi
fi

# 7) 保留策略（macOS 的 head 不支持 -n -N，改用 python 算保留列表）
/usr/bin/python3 - "$DEST" "$KEEP" <<'PY'
import sys,os,shutil
dest,keep=sys.argv[1],int(sys.argv[2])
ds=sorted(d for d in os.listdir(dest) if d.startswith('20'))
for old in ds[:-keep]:
    shutil.rmtree(os.path.join(dest,old),ignore_errors=True)
    print("  清理旧备份：%s" % old)
PY

echo "✅ 备份完成：$OUT"
