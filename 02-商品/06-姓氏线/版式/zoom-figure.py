#!/usr/bin/env python3
"""底纹素材**局部放大**对比：自动定位墨量最高的窗口，裁同一窗口放大并排。

用途：判断"线条干不干净、有没有墨迹顿点" —— 整幅缩略图看不出来，必须放大到
      笔画级。窗口由基准图（第一个参数）自动确定，保证各档裁的是同一处。
用法：zoom-figure.py 基准.png 档2.png 档3.png ... -o out.png [--win 360] [--scale 2.4]
"""
import argparse, pathlib
import numpy as np
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument('figs', nargs='+')
ap.add_argument('-o', '--out', required=True)
ap.add_argument('--win', type=int, default=360, help='窗口边长（素材像素）')
ap.add_argument('--box', default=None,
                help='定点窗口 x,y（左上角，素材像素）；不给则自动取墨量最高处')
ap.add_argument('--scale', type=float, default=2.4)
ap.add_argument('--opacity', type=float, default=0.32)
ap.add_argument('--cols', type=int, default=0)
a = ap.parse_args()


def ink(p):
    im = Image.open(p).convert('RGBA')
    arr = np.asarray(im)
    return arr[..., 3].astype(np.float32) / 255.0, arr[..., :3]


def find_window(af, win):
    """找墨量最高的 win×win 窗口（用积分图快速求和）"""
    h, w = af.shape
    win = min(win, h, w)
    c = np.zeros((h + 1, w + 1), np.float64)
    np.cumsum(np.cumsum(af, 0), 1, out=c[1:, 1:])
    s = (c[win:, win:] - c[:-win, win:] - c[win:, :-win] + c[:-win, :-win])
    i = int(np.argmin(s))          # 注意 argmin 展平顺序：这里是"墨最少"，改取 max
    i = int(np.argmax(s))
    y, x = divmod(i, s.shape[1])
    return x, y, win


def render(p, box, scale, op):
    af, rgb = ink(p)
    x, y, win = box
    sub = af[y:y + win, x:x + win]
    # 合成到白纸：out = 255 - alpha*op*(255-ink)
    ink_rgb = rgb[win // 2, win // 2].astype(np.float32)
    layer = (sub * op)[..., None] * (255.0 - ink_rgb)[None, None, :]
    out = 255.0 - layer
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGB')
    im = im.resize((int(win * scale), int(win * scale)), Image.LANCZOS)
    return im


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, 26], fill=(255, 255, 255))
    d.text((6, 6), text, fill=(20, 20, 20))
    return im


base_af, _ = ink(a.figs[0])
if a.box:
    bx, by = (int(v) for v in a.box.split(','))
    box = (bx, by, min(a.win, base_af.shape[1] - bx, base_af.shape[0] - by))
else:
    box = find_window(base_af, a.win)
print(f'窗口 x{box[0]} y{box[1]} 边长 {box[2]}'
      f'{"（定点）" if a.box else "（由基准图墨量最高处自动定位）"}')

tiles = []
for p in a.figs:
    stem = pathlib.Path(p).parent.name or pathlib.Path(p).stem
    tiles.append((stem, label(render(p, box, a.scale, a.opacity), stem)))

cols = a.cols or len(tiles)
rows = (len(tiles) + cols - 1) // cols
tw, th = tiles[0][1].size
sheet = Image.new('RGB', (cols * tw, rows * (th + 8)), (255, 255, 255))
for i, (_, im) in enumerate(tiles):
    sheet.paste(im, ((i % cols) * tw, (i // cols) * (th + 8)))
out = pathlib.Path(a.out)
out.parent.mkdir(parents=True, exist_ok=True)
sheet.save(out)
print('→', out, sheet.size)
