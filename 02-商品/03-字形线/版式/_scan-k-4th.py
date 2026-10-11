# -*- coding: utf-8 -*-
"""第四批（隋龙舸／清风雷行龙）k 值扫描 + 量化验收。

不改动 gen-texture-full.py，直接用 importlib 复用它的 build_key / compose_inplace。
输出 /tmp/k-scan-<slug>.png（三档 k 并排 + 指标），供一眼定档。
"""
import importlib.util
import numpy as np
from PIL import Image, ImageDraw

SRC = '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/03-字形线/版式/gen-texture-full.py'
spec = importlib.util.spec_from_file_location('gtf', SRC)
gtf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gtf)

# 验收区（底纹原图 1536×1024 坐标，口径同 底纹-朝代/README.md §五 / §八）
TEXT_Y = (376, 586)          # 画心字区
BRAND = (673, 765, 873, 829)  # 品牌行区 x0,y0,x1,y1

CASES = {
    'longge':   dict(k=[0.30, 0.45, 0.60], ink=200, span=60),
    'fenglong': dict(k=[0.30, 0.45, 0.60], ink=200, span=60),
}


def metrics(cv):
    ink_all = 100 * ((cv < 252) & (cv > 60)).mean()
    band = cv[TEXT_Y[0]:TEXT_Y[1], :]
    ink_band = 100 * (band < 235).mean()
    x0, y0, x1, y1 = BRAND
    br = cv[y0:y1, x0:x1]
    brand_dark = 100 * (br < 200).mean()
    return ink_all, ink_band, brand_dark


for slug, cfg in CASES.items():
    L, alf, ys, xs = gtf.build_key(slug)
    mm = alf > 0.02
    tiles = []
    print(f'\n===== {slug}  mask覆盖 {100*mm.mean():.1f}%  '
          f'bbox y[{ys.min()},{ys.max()}] x[{xs.min()},{xs.max()}] =====')
    for k in cfg['k']:
        cv = gtf.compose_inplace(L, mm, k, cfg['ink'], cfg['span'])
        a, b, c = metrics(cv)
        print(f'  k={k:.2f}  全幅可见 {a:5.2f}%  字区墨(<235) {b:5.2f}%  品牌区浓墨(<200) {c:5.2f}%')
        im = Image.fromarray(cv.astype(np.uint8)).convert('RGB').resize((640, 427), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 200, 18], fill=(255, 255, 255))
        d.text((4, 4), f'k={k:.2f} all={a:.1f}% band={b:.1f}%', fill=(0, 0, 0))
        tiles.append(im)
    W = sum(t.width for t in tiles) + 12 * (len(tiles) - 1)
    out = Image.new('RGB', (W, 427), (255, 255, 255))
    x = 0
    for t in tiles:
        out.paste(t, (x, 0))
        x += t.width + 12
    out.save(f'/tmp/k-scan-{slug}.png')
    print(f'  → /tmp/k-scan-{slug}.png')
