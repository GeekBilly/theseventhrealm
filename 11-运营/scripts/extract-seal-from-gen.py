#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 AI 生成的整幅水墨图里抠出朱砂印章（转 RGBA 素材）

AI 直出的印章图是「纸底 + 远山 + 印章」一整幅，印章本身是 RGB 不透明的。
本脚本按「红色度」检出印面 → 闭运算补断口 → 填内部空洞 → 取最大连通域 → 裁 bbox → 转 RGBA。

口径：印面内的一切（含白文阴文的白色笔画）保留为不透明，印外的纸底与远山变透明。
这样得到的印章素材可以直接替换 `seal.png`（尺寸与原印一致更佳，用 --fit 指定）。

用法：
    python3 extract-seal-from-gen.py --src 生图源/xxx.png --out 印章-探赜-直出A.png
    python3 extract-seal-from-gen.py --src xxx.png --out yyy.png --fit 136x195
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi

D = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/底纹"


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def red_mask(rgb, thr_red=110, thr_diff=35):
    r, g, b = rgb[:, :, 0].astype(int), rgb[:, :, 1].astype(int), rgb[:, :, 2].astype(int)
    return (r > thr_red) & (r - g > thr_diff) & (r - b > thr_diff)


def extract(src, out, fit=None, close_r=14, pad=2, feather=1.0):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    m = red_mask(a.astype(int))
    # 补印框断口 → 填内部
    m = ndi.binary_closing(m, structure=disk(close_r), border_value=0)
    m = ndi.binary_fill_holes(m)
    # 只留最大连通域
    lab, n = ndi.label(m, structure=np.ones((3, 3), int))
    if n == 0:
        raise SystemExit("没检出印章（红色度阈值太严？）")
    sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
    m = (lab == (int(np.argmax(sizes)) + 1))

    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
    y1, x1 = min(m.shape[0], y1 + pad), min(m.shape[1], x1 + pad)

    rgb = a[y0:y1, x0:x1].copy()
    alpha = m[y0:y1, x0:x1].astype(np.float32) * 255.0
    if feather > 0:                     # 轻微羽化，避免锯齿
        alpha = np.asarray(Image.fromarray(alpha.astype(np.uint8))
                           .filter(ImageFilter.GaussianBlur(feather)))
        alpha = np.clip(alpha.astype(np.float32) * 1.35, 0, 255)
    # 印外一律白底，避免半透明边缘带出纸底灰
    rgb = np.dstack([rgb, alpha]).astype(np.uint8)
    img = Image.fromarray(rgb, "RGBA")

    if fit:
        w, h = (int(v) for v in fit.lower().split("x"))
        img = img.resize((w, h), Image.LANCZOS)

    p = out if os.path.isabs(out) else os.path.join(D, out)
    img.save(p)
    print(f"检出印面 bbox {x0},{y0} → {x1},{y1}（{x1 - x0}×{y1 - y0}）")
    print(f"输出 {p}  →  {img.width}×{img.height}")
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="生图源文件名或绝对路径")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fit", default=None, help="缩放目标，如 136x195")
    ap.add_argument("--close-r", type=int, default=14, help="闭合半径（补印框断口）")
    ap.add_argument("--feather", type=float, default=1.0)
    args = ap.parse_args()

    src = args.src if os.path.isabs(args.src) else os.path.join(D, "生图源", args.src)
    extract(src, args.out, fit=args.fit, close_r=args.close_r, feather=args.feather)
