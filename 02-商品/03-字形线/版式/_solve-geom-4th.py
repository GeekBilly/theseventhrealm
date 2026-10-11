# -*- coding: utf-8 -*-
"""第四批几何求解：在「不裁头」与「不压品牌区」两条硬约束之间解出最大缩放比。

判据用**压淡后的实际底纹**（不是 raw）来测，因为交付物就是它：
  约束① 内容顶 ≥ 99.2  → 成品顶带 24px 内容墨(<240) 0%
  约束② 内容底 ≤ 758   → 品牌行区 y765–829 的浓墨(<200) 0%

由「s·yt − t ≥ 99.2」与「s·yb − t ≤ 758」消去 t：
  s ≤ 658.8 / (yb − yt)，t = (s·yt − 99.2 + s·yb − 758)/2
"""
import importlib.util

import numpy as np
from PIL import Image, ImageDraw

SRC = '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/03-字形线/版式/gen-texture-full.py'
spec = importlib.util.spec_from_file_location('gtf', SRC)
gtf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gtf)

W, H = 1536, 1024
TOP_MIN = 99.2      # 成品顶带下沿反查源坐标
BOT_MAX = 758.0     # 品牌区上沿留 7px 余量


def zoom_shift(cv, s, t):
    nw, nh = round(W * s), round(H * s)
    im = Image.fromarray(cv.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
    out = Image.new('L', (W, H), 255)
    out.paste(im, ((W - nw) // 2, -int(round(t))))
    return np.asarray(out).astype(float)


def cover_map(cv):
    im = Image.fromarray(cv.astype(np.uint8)).resize((1920, 1280), Image.LANCZOS)
    return np.asarray(im.crop((0, 100, 1920, 1180))).astype(float)


def rows_of(cv, x0, x1, thr, n=2):
    """在 x[x0,x1) 内找 <thr 像素数 >n 的行范围"""
    col = cv[:, x0:x1]
    r = np.where((col < thr).sum(axis=1) > n)[0]
    return (int(r.min()), int(r.max())) if r.size else None


def report(tag, cv):
    top_rows = rows_of(cv, 720, W, 240)
    bot_rows = rows_of(cv, 673, 873, 200)
    x0, y0, x1, y1 = 673, 765, 873, 829
    brand_src = 100 * (cv[y0:y1, x0:x1] < 200).mean()
    disp = cover_map(cv)
    top250 = 100 * (disp[0:24, 900:] < 250).mean()
    top240 = 100 * (disp[0:24, 900:] < 240).mean()
    brand_disp = 100 * (disp[856:936, 841:1091] < 200).mean()
    whole = 100 * (disp < 235).mean()
    print(f'  {tag}  内容行 y{top_rows}  品牌区浓墨行 y{bot_rows}')
    print(f'       源品牌区<200 {brand_src:5.2f}% ｜ 成品顶带 <250 {top250:5.2f}% <240 {top240:5.2f}% '
          f'｜ 成品品牌区 {brand_disp:5.2f}% 整幅 {whole:5.2f}%')
    return brand_src, top250, top240, brand_disp, whole


for slug, k, ink, span in (('longge', 0.45, 200, 60), ('fenglong', 0.45, 200, 60)):
    print(f'\n========== {slug}（k={k}）==========')
    L, alf, ys, xs = gtf.build_key(slug)
    mm = alf > 0.02
    base = gtf.compose_inplace(L, mm, k, ink, span)
    report('base(s=1.00)', base)

    tr = rows_of(base, 720, W, 240)
    br = rows_of(base, 673, 873, 200)
    print(f'  求解：内容顶 yt={tr[0] if tr else 0}  品牌区浓墨底 yb={br[1] if br else 0}')
    yt = tr[0] if tr else 0
    yb = br[1] if br else 0
    s_max = 658.8 / max(1, yb - yt)
    for s in (round(s_max, 3), round(min(s_max, 0.95), 3)):
        t = (s * yt - TOP_MIN + s * yb - BOT_MAX) / 2
        cv = zoom_shift(base, s, t)
        brd, t250, t240, bd, wh = report(f's={s:.3f} t={t:+.1f}', cv)

    # 出图：base 与推荐参数并排
    s = round(s_max, 3)
    t = (s * yt - TOP_MIN + s * yb - BOT_MAX) / 2
    cvz = zoom_shift(base, s, t)
    tiles = []
    for tag, img in (('base', base), (f's={s:.3f} t={t:+.1f}', cvz)):
        im = Image.fromarray(img.astype(np.uint8)).convert('RGB').resize((520, 347), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([int(673 * 520 / W), int(765 * 347 / H), int(873 * 520 / W), int(829 * 347 / H)],
                    outline=(220, 0, 0))
        d.line([(0, int(99.2 * 347 / H)), (520, int(99.2 * 347 / H))], fill=(0, 120, 220), width=1)
        d.rectangle([0, 0, 190, 15], fill=(255, 255, 255))
        d.text((3, 2), tag, fill=(0, 0, 0))
        tiles.append(im)
    out = Image.new('RGB', (520 * 2 + 10, 347), (255, 255, 255))
    out.paste(tiles[0], (0, 0)); out.paste(tiles[1], (530, 0))
    out.save(f'/tmp/solve-{slug}.png')
    print(f'  → /tmp/solve-{slug}.png')
