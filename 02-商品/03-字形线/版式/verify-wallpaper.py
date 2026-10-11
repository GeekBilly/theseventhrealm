# -*- coding: utf-8 -*-
"""A 线朝代壁纸成品 · 三项量化验收（口径对齐 底纹-朝代/README.md §五 / §八 / §十一）。

用法：
    python3 verify-wallpaper.py                     # 验收全部 1920x1080 成品
    python3 verify-wallpaper.py shang tang song     # 只验指定 slug
    python3 verify-wallpaper.py --src               # 顺带报源底纹的品牌区/字区数

三项判据（均在 1920×1080 成品上测）：
  ① 顶带：y[0,24) × x[900,1920) 的非白(<250)占比 ⇒ **必须 0.00%**（§六 不裁头）
  ② 品牌行区：源 x[673,873] y[765,829] 经 cover 映射到成品 ⇒ 读数应≈九朝基准
     11.54–11.60%（该区只有纯文字墨）；明显高出＝底纹压住落款（§八）
  ③ 字区墨 / 整幅墨：成品 y[371,633) 全宽、全幅的 <235 占比 —— 与同布局的商对比，
     判断墨量是否同档

cover 映射（源 1536×1024 → 成品 1920×1080）：X = x·1.25，Y = y·1.25 − 100
"""
import pathlib
import sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
FIN = ROOT / '02-商品/03-字形线/成品-演变/01-正式成品'
TEX = ROOT / '02-商品/02-素材/底纹'

# 参照基准（九朝 + 第三批，来自 README §十一 验收表）
REF = {
    'shang': (0.07, 11.60, 16.34, 44.39),
    'han':   (0.00, 11.54, 12.11, 22.62),
    'wudai': (0.00, 11.54, 17.35, 42.05),
    'tang':  (0.00, 11.64, 19.91, 50.12),
    'song':  (0.00, 11.64,  5.79, 18.56),
    'ming':  (0.00, 11.75, 15.57, 40.60),
}


def src2disp(x, y):
    return x * 1.25, y * 1.25 - 100


def verify(slug, show_ref=True):
    p = FIN / f'{slug}-1920x1080.png'
    if not p.exists():
        return f'{slug:10s} MISS {p.name}'
    a = np.asarray(Image.open(p).convert('L')).astype(float)
    H, W = a.shape
    top = a[0:24, 900:]
    top_nw = 100 * (top < 250).mean()
    # ⚠️ 两级口径（2026-10-09 定，见 底纹-朝代/README.md §12.5／§13.5）：
    #   `<250` 会把生图自带的**极浅纸纹**（L∈[245,250]）也数进去 ⇒ 隋 0.62%、清 0.25%、元 0.02%；
    #   `<240` 才是「真有内容」的判据（隋/清/元 均为 0.00%）。⇒ **以 <240 为准判定**。
    top_nw240 = 100 * (top < 240).mean()
    bx0, by0 = src2disp(673, 765)
    bx1, by1 = src2disp(873, 829)
    brand = a[int(by0):int(by1), int(bx0):int(bx1)]
    brand_dark = 100 * (brand < 200).mean()
    whole = 100 * (a < 235).mean()
    band = 100 * (a[371:633, :] < 235).mean()
    ok_top = 'OK ' if top_nw240 < 0.005 else '!! '
    ok_br = 'OK ' if brand_dark < 12.2 else '!! '
    line = (f'{slug:10s} {W}x{H}  顶带 {top_nw:5.2f}/{top_nw240:5.2f}% {ok_top}  '
            f'品牌区 {brand_dark:5.2f}% {ok_br}  整幅 {whole:5.2f}%  字区 {band:5.2f}%')
    if show_ref and slug in REF:
        r = REF[slug]
        line += f'   ｜README 基准 {r[0]:.2f}/{r[1]:.2f}/{r[2]:.2f}/{r[3]:.2f}'
    return line


def src_report(slug):
    """源底纹直接读数（未做 cover 映射）：品牌区 <200、顶带 y[80,99) x>720 非白"""
    p = TEX / f'{slug}-raw.png'
    q = TEX / f'{slug}-full.png'
    out = []
    for tag, f in (('raw ', p), ('full', q)):
        if not f.exists():
            continue
        a = np.asarray(Image.open(f).convert('L')).astype(float)
        br = a[765:829, 673:873]
        tb = a[80:99, 720:]
        out.append(f'   {tag} {f.name:22s} 品牌区<200 {100*(br<200).mean():5.2f}%  '
                   f'顶带非白 {100*(tb<250).mean():5.2f}%  整幅<235 {100*(a<235).mean():5.2f}%')
    return '\n'.join(out)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    show_src = '--src' in sys.argv
    if args:
        for s in args:
            print(verify(s))
            if show_src:
                print(src_report(s))
    else:
        order = ['sanhuang', 'xia', 'shang', 'zhou', 'qin', 'han', 'sanguo', 'jin',
                 'sui', 'tang', 'wudai', 'song', 'yuan', 'ming', 'qing', 'juexing']
        for s in order:
            r = verify(s)
            if not r.endswith('MISS'):
                print(r)
