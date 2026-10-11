# -*- coding: utf-8 -*-
"""样张 PNG 像素体检：① 尺寸是否符合竖版规格（防截图视口配错）；② 墨迹是否贴边（被裁）。
用法：
  python3 verify-ink.py                     # 体检样张目录下全部 *phone*.png
  python3 verify-ink.py <png路径...>         # 只体检指定文件
期望尺寸：iphone/lockpreview = 1179×2556，android = 1080×2400。
"""
import sys, glob, pathlib
from PIL import Image
import numpy as np

BASE = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/05-承接站/样张')


def analyze(path):
    im = Image.open(path).convert('L')
    w, h = im.size
    a = np.asarray(im)
    ink = a < 140
    cols = ink.any(axis=0)
    xs = np.where(cols)[0]
    left = int(xs.min()) if len(xs) else -1
    right = int(xs.max()) if len(xs) else -1
    clip = left >= 0 and (left < 8 or right > w - 8)
    return dict(w=w, h=h, left=left, right=right, clip=clip)


def expect_size(name):
    if 'iphone' in name or 'lockpreview' in name:
        return (1179, 2556)
    if 'android' in name:
        return (1080, 2400)
    return None


if __name__ == '__main__':
    files = sys.argv[1:] or sorted(str(p) for p in BASE.glob('*phone*.png'))
    bad = 0
    for f in files:
        name = pathlib.Path(f).name
        r = analyze(f)
        exp = expect_size(name)
        size_ok = exp is None or (r['w'], r['h']) == exp
        tag = []
        if not size_ok:
            tag.append(f"❌尺寸错({r['w']}×{r['h']}，期望{exp[0]}×{exp[1]})")
            bad += 1
        if r['clip']:
            tag.append(f"❌墨迹贴边(x {r['left']}..{r['right']})")
            bad += 1
        status = '  '.join(tag) if tag else '✅'
        print(f"{name:34} {r['w']}×{r['h']}  墨迹 x={r['left']}..{r['right']}  {status}")
    print(f"\n共 {len(files)} 张，问题 {bad} 处")
