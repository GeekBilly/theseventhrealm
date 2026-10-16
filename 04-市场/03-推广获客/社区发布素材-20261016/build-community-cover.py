# -*- coding: utf-8 -*-
"""垂直社区发布 · 通用封面生成器（2026-10-16 立）

为什么需要：站酷作品封面位 / Behance 封面推荐尺寸是 1400×800；
            手上现成的 ji-all-16chao.png 是 1200×785（为面包多做的），
            直接放大到 1400 会软化文字。本脚本从**高清源**重排。

源图：02-商品/09-上架素材/藏品页配图-v3/collection-a-<slug>-v3.jpg（1400×788，无水印）
🔴 禁用水印版 预览/<slug>-preview.jpg

产出：社区封面-十六朝总览-1400x800.png
版式：顶部标题 + 4×4 十六朝总览 + 底部品牌行（全部落在 1400×800 内，裁切安全）

用法：
  python3 build-community-cover.py          # 生成
  python3 build-community-cover.py --dry    # 只看计划
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
SRC = ROOT / '02-商品/09-上架素材/藏品页配图-v3'
OUT = ROOT / '04-市场/03-推广获客/社区发布素材-20261016'

FONT_HEI = '/System/Library/Fonts/STHeiti Medium.ttc'
FONT_SONG = '/Library/Fonts/Songti.ttc'

W, H = 1400, 800
BG = (255, 255, 255)
INK = (34, 34, 34)
GRAY = (120, 120, 120)
LINE = (226, 226, 226)

# 历史时序（与线上 /collection/、交付包目录序号一致）
SLUGS = [
    ('sanhuang', '三皇五帝'), ('xia', '夏'),   ('shang', '商'),   ('zhou', '周'),
    ('qin', '秦'),            ('han', '汉'),   ('sanguo', '三国'), ('jin', '两晋南北朝'),
    ('sui', '隋'),            ('tang', '唐'),  ('wudai', '五代十国'), ('song', '宋'),
    ('yuan', '元'),           ('ming', '明'),  ('qing', '清'),    ('juexing', '觉醒年代'),
]


def f(path, size):
    return ImageFont.truetype(path, size)


def center(d, y, text, font, fill):
    bb = d.textbbox((0, 0), text, font=font)
    d.text(((W - (bb[2] - bb[0])) / 2 - bb[0], y), text, font=font, fill=fill)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- 网格几何 ----
    cols = rows = 4
    gap = 6
    cw = 286
    ch = 161
    grid_w = cols * cw + (cols - 1) * gap
    x0 = (W - grid_w) // 2
    y0 = 94

    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)

    # ---- 顶部标题 ----
    center(d, 18, '十六朝 · 汉字演变', f(FONT_SONG, 36), INK)
    center(d, 64, '从甲骨文到铅字 —— 一个字的三千年', f(FONT_HEI, 16), GRAY)

    # ---- 4×4 网格 ----
    for i, (slug, cn) in enumerate(SLUGS):
        r, c = divmod(i, cols)
        x = x0 + c * (cw + gap)
        y = y0 + r * (ch + gap)
        src = SRC / f'collection-a-{slug}-v3.jpg'
        if not src.exists():
            print(f'  ! 缺图 {src.name}')
            continue
        im.paste(Image.open(src).convert('RGB').resize((cw, ch), Image.LANCZOS), (x, y))
        d.rectangle([x - 1, y - 1, x + cw, y + ch], outline=LINE, width=1)

    # ---- 底部品牌行 ----
    center(d, 772, '第七境 · theseventhrealm.com', f(FONT_HEI, 14), GRAY)

    out = OUT / '社区封面-十六朝总览-1400x800.png'
    im.save(out, optimize=True)
    print(f'OK  {out.relative_to(ROOT)}  {W}×{H}  {out.stat().st_size/1024:.0f}KB')


if __name__ == '__main__':
    if '--dry' in sys.argv:
        print(f'计划：{W}×{H} 封面，4×4 网格（格 {286}×{161}），源 {SRC.name}/')
        for s, cn in SLUGS:
            print(f'  {s:<10} {cn}')
    else:
        main()
