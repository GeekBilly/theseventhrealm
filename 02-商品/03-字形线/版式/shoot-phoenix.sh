#!/bin/zsh
# 出凤凰底纹并渲染周稿（S / AX / AY 可调），最后拼商稿对比图
set -u
ROOT="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY=/Users/billyhou/.workbuddy/binaries/python/envs/default/bin/python
PY3=/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
G="$ROOT/02-商品/03-字形线/版式/gen-wallpaper-classic.py"
B="$ROOT/02-商品/05-承接站/样张"

cd "$ROOT" || exit 1

PHX_S="${PHX_S:-0.86}" PHX_AX="${PHX_AX:-0.76}" PHX_AY="${PHX_AY:-0.34}" \
  "$PY" "02-商品/03-字形线/版式/gen-phoenix-full.py" 云浓

"$PY3" "$G" zhou

for s in zhou-v9-std zhou-v9-mac; do
  case "$s" in *mac) H=1248 ;; *) H=1080 ;; esac
  "$CH" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
        --force-device-scale-factor=1 --window-size=1920,"$H" --virtual-time-budget=9000 \
        --screenshot="$B/$s.png" "file://$B/$s.html" 2>/dev/null
  "$CH" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files \
        --force-device-scale-factor=2 --window-size=1920,"$H" --virtual-time-budget=9000 \
        --screenshot="$B/$s-4k.png" "file://$B/$s.html" 2>/dev/null
  echo "  -> $s.png  $(stat -f '%Sm' -t '%H:%M:%S' "$B/$s.png")"
done

"$PY" - <<'PYEOF'
from PIL import Image
import numpy as np
D = '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/05-承接站/样张/'
w = 900
def rs(im):
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
A = rs(Image.open(D + 'shang-v9-std.png').convert('RGB'))
Bm = rs(Image.open(D + 'zhou-v9-std.png').convert('RGB'))
c = Image.new('RGB', (w, A.height + Bm.height + 16), '#c8c8c8')
c.paste(A, (0, 0)); c.paste(Bm, (0, A.height + 16))
c.save('/tmp/pair-phx.png')
for f in ('shang-v9-std.png', 'zhou-v9-std.png'):
    a = np.asarray(Image.open(D + f).convert('L')).astype(float)
    dark = a[a < 60]
    z = a[(a < 252) & (a > 60)]
    print('%-18s 深墨均值 %.1f | 底纹可见 %.1f%% | 分位 1%%=%.0f 5%%=%.0f 10%%=%.0f'
          % (f, dark.mean(), 100 * z.size / a.size, *np.percentile(z, [1, 5, 10])))
print(c.size, '| 上=商 下=周')
PYEOF
