# -*- coding: utf-8 -*-
"""第四批：原位减云 + 「等比缩放 + 上移」几何步的参数扫描。

为什么需要几何步：隋·龙舸的 raw 主体太大太低（船体 y178–884，占全高 69%），
船底直接落进品牌行区（源 y765–829）⇒ 违反 §八（源底纹品牌区 <200 必须 0%）。
tex_pos 上下各只有 100px 余量（成品），算下来最多上移 69px 就顶到 §六 裁切区，
光靠取景救不回；**缩放 + 上移**才是解。

约束（源坐标）：
  ① 船/龙顶 ≥ 99.2  → 保证成品顶带 24px 非白 0%（§六）
  ② 主体底 ≤ 755     → 保证品牌行区 y765–829 干净（§八，留 10px 余量）
输出 /tmp/zoom-scan-<slug>.png 供一眼定档。
"""
import importlib.util

import numpy as np
from PIL import Image, ImageDraw

SRC = '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/03-字形线/版式/gen-texture-full.py'
spec = importlib.util.spec_from_file_location('gtf', SRC)
gtf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gtf)

W, H = 1536, 1024
BRAND = (673, 765, 873, 829)
TOP_SRC_Y = (80, 99)      # 成品顶带 24px 反查源区


def zoom_shift(cv, s, t):
    """等比缩放 s 后水平居中、垂直上移 t 源像素，贴回 1536×1024 白画布。"""
    nw, nh = round(W * s), round(H * s)
    im = Image.fromarray(cv.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
    out = Image.new('L', (W, H), 255)
    out.paste(im, ((W - nw) // 2, -int(t)))
    return np.asarray(out).astype(float)


def cover_map(cv):
    """源 1536×1024 → 成品 1920×1080（cover 1.25×，上下各裁 100px）"""
    im = Image.fromarray(cv.astype(np.uint8)).resize((1920, 1280), Image.LANCZOS)
    return np.asarray(im.crop((0, 100, 1920, 1180))).astype(float)


def metrics(cv):
    x0, y0, x1, y1 = BRAND
    brand_src = 100 * (cv[y0:y1, x0:x1] < 200).mean()
    disp = cover_map(cv)
    top = 100 * (disp[0:24, 900:] < 250).mean()
    brand_disp = 100 * (disp[856:936, 841:1091] < 200).mean()
    whole = 100 * (disp < 235).mean()
    return brand_src, top, brand_disp, whole


CASES = {
    'longge': dict(k=0.45, ink=200, span=60,
                   grid=[(1.00, 0), (0.88, 35), (0.86, 25), (0.84, 20)]),
    'fenglong': dict(k=0.45, ink=200, span=60,
                     grid=[(1.00, 0), (0.94, 20), (0.90, 30)]),
}

for slug, cfg in CASES.items():
    L, alf, ys, xs = gtf.build_key(slug)
    mm = alf > 0.02
    base = gtf.compose_inplace(L, mm, cfg['k'], cfg['ink'], cfg['span'])
    tiles = []
    print(f'\n===== {slug}  k={cfg["k"]}  mask y[{ys.min()},{ys.max()}] =====')
    for s, t in cfg['grid']:
        cv = zoom_shift(base, s, t) if (s != 1.0 or t) else base
        bs, top, bd, wh = metrics(cv)
        flag = 'OK ' if (bs < 0.005 and top < 0.005) else '!! '
        print(f'  s={s:.2f} t={t:3d}  源品牌区 {bs:5.2f}%  顶带 {top:5.2f}% {flag} '
              f'成品品牌区 {bd:5.2f}%  整幅 {wh:5.2f}%')
        im = Image.fromarray(cv.astype(np.uint8)).convert('RGB').resize((520, 347), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        # 标出品牌行区（源坐标 → 缩略图）
        bx0, by0 = int(673 * 520 / W), int(765 * 347 / H)
        bx1, by1 = int(873 * 520 / W), int(829 * 347 / H)
        d.rectangle([bx0, by0, bx1, by1], outline=(220, 0, 0))
        d.rectangle([0, 0, 235, 16], fill=(255, 255, 255))
        d.text((3, 3), f's={s:.2f} t={t} brand={bs:.2f}% top={top:.2f}%', fill=(0, 0, 0))
        tiles.append(im)
    tw = sum(t.width for t in tiles) + 10 * (len(tiles) - 1)
    out = Image.new('RGB', (tw, 347), (255, 255, 255))
    x = 0
    for t_ in tiles:
        out.paste(t_, (x, 0))
        x += t_.width + 10
    out.save(f'/tmp/zoom-scan-{slug}.png')
    print(f'  → /tmp/zoom-scan-{slug}.png')
