# -*- coding: utf-8 -*-
"""凤凰底纹「满幅云雾 + 小凤凰」合成器。

背景（2026-09-29）：用户要底纹图层铺满全图（像商稿玄鸟那样画面饱满），
但凤凰本体要比玄鸟小（凤凰单独缩到 S 倍）。原素材是「白底 + 一只凤凰 +
左下一小团云雾」，整图缩小会让画面四周全白 → 用户看到的是"图层被缩小"。

做法：
  1. 连通域抠出凤凰（含长尾），排除左下云雾团
  2. 左下云雾当贴片，大尺度（2.2~3.0x）镜像多次低权重叠加 → 高斯模糊
     → levels 提白（压缩灰阶、留白干净、云团成形，避免"雾霾感"）
  3. 凤凰附近 halo 留白，云雾不与鸟打架
  4. 凤凰按 S 缩放叠上，略作浓墨补偿（缩小会把细笔触平均掉、发灰）

输出：02-商品/02-素材/底纹/phoenix-full.png
用法：python3 gen-phoenix-full.py [云淡|云浓]      # 默认云淡
"""
import os
import pathlib
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

D = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/底纹')
# 凤凰大小与落位（可用环境变量覆盖，便于出多档对比）
S = float(os.environ.get('PHX_S', '0.62'))            # 凤凰相对原图铺满时的倍数
AX = float(os.environ.get('PHX_AX', '0.607'))         # 凤凰「质心」落在画面的横向比例
AY = float(os.environ.get('PHX_AY', '0.469'))         # 凤凰「质心」落在画面的纵向比例
OPTS = {                                   # 档位: (云权重, 模糊σ, 浓墨补偿, levels(lo,hi,最浓灰度))
    '云淡': (0.30, 11.0, 1.10, (238, 253, 236)),
    '云浓': (0.46, 12.0, 1.25, (236, 252, 226)),
}
SCALES = [2.2, 2.55, 2.9, 2.35, 2.75, 2.4, 3.0, 2.3]      # 每个贴片一个尺度
GRID_X = [-200, 400, 1000, 1600]
GRID_Y = [-150, 350, 850, 1250]

a0 = np.asarray(Image.open(D / 'phoenix-raw.png').convert('L')).astype(float)
H, W = a0.shape
base = np.percentile(a0, 92)
L = np.clip(a0 + (255 - base), 0, 255)      # 纸色抬到纯白，浓淡保留

# ---- 1. 抠凤凰 ----
# 注意：不能简单"保留所有大块" —— 左下云团里混着一块浓墨（面积也 >4000），
# 会被误当凤凰的一部分，缩小后就在画面左侧留下一块突兀的孤立墨斑。
# 所以只保留「最大连通域 + 质心落在它附近」的块。
m = L < 205
lab, n = ndimage.label(m)
sizes = ndimage.sum(m, lab, range(1, n + 1))
big = int(np.argmax(sizes)) + 1
cy0, cx0 = ndimage.center_of_mass(m, lab, big)
keep = [big]
for i, s in enumerate(sizes):
    if s < 4000 or i + 1 == big:
        continue
    cyi, cxi = ndimage.center_of_mass(m, lab, i + 1)
    if (cyi - cy0) ** 2 + (cxi - cx0) ** 2 <= 700 ** 2:
        keep.append(i + 1)
print('抠凤凰：最大块 %d px，并保留邻近大块 %d 个（共 %d 块）'
      % (sizes[big - 1], len(keep) - 1, len(keep)))
mm = np.isin(lab, keep)
mm = ndimage.binary_fill_holes(ndimage.binary_dilation(mm, iterations=4))
ys, xs = np.where(mm)
alf = np.clip((252 - L) / 30.0, 0, 1) * mm

# ---- 2. 云雾贴片 ----
# 贴片取自原图左下云团。注意：云团里混着一小块很浓的墨（最暗 91），
# 放大 2~3 倍铺开后就成了画面上突兀的孤立墨斑 → 先做亮度下限抬白，
# 再轻微柔化内部纹理，得到"纯云气"贴片。
patch = L[470:1024, 0:560]
patch = np.clip(patch, 216, 255)
patch = ndimage.gaussian_filter(patch, 5.0)
pa = np.clip((254 - patch) / 34.0, 0, 1)
PH, PW = patch.shape


def stamp(cv, cx, cy, sc, fx, fy, w):
    nh, nw = int(PH * sc), int(PW * sc)
    g = np.asarray(Image.fromarray(patch.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float)
    al = np.asarray(Image.fromarray((pa * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float) / 255
    if fx:
        g, al = g[:, ::-1], al[:, ::-1]
    if fy:
        g, al = g[::-1, :], al[::-1, :]
    x0, y0 = int(cx - nw / 2), int(cy - nh / 2)
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(W, x0 + nw), min(H, y0 + nh)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    gg = g[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0]
    aa = al[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] * w
    sub = cv[sy0:sy1, sx0:sx1]
    cv[sy0:sy1, sx0:sx1] = sub * (1 - aa) + gg * aa


def phoenix_placed(deepen):
    """凤凰按 S 缩放、质心锚定到画面 (AX, AY)，允许溢出画布（压迫感来自裁切）。
    返回：裁剪到画布内的 (灰度片, alpha 片, 画布切片范围, 全幅 mask)"""
    nw, nh = round(W * S), round(H * S)
    gs = np.asarray(Image.fromarray(L.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float)
    als = np.asarray(Image.fromarray((alf * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float) / 255
    gs = np.clip(255 - (255 - gs) * deepen, 0, 255)

    bx = round(AX * W - xs.mean() * S)      # 缩放后质心落在 (AX*W, AY*H)
    by = round(AY * H - ys.mean() * S)
    dx0, dy0 = max(0, bx), max(0, by)
    dx1, dy1 = min(W, bx + nw), min(H, by + nh)
    sx0, sy0 = dx0 - bx, dy0 - by
    sx1, sy1 = sx0 + (dx1 - dx0), sy0 + (dy1 - dy0)

    mm_full = np.zeros((H, W), bool)
    mm_full[dy0:dy1, dx0:dx1] = als[sy0:sy1, sx0:sx1] > 0.08
    return (gs[sy0:sy1, sx0:sx1], als[sy0:sy1, sx0:sx1],
            (dx0, dy0, dx1, dy1), mm_full, (bx, by, nw, nh))


def make_cloud(weight, blur, levels, halo_src):
    cv = np.full((H, W), 255.0)
    lo, hi, darkest = levels
    i = 0
    for r, yy in enumerate(GRID_Y):
        for xx in GRID_X:
            stamp(cv, xx + (90 if r % 2 else 0), yy,
                  SCALES[i % len(SCALES)], i % 3 == 0, i % 2 == 1, weight)
            i += 1
    cv = ndimage.gaussian_filter(cv, blur)
    # levels：把灰阶压缩到 [darkest, 255]，云团成形、留白干净（去"雾霾感"）
    t = np.clip((cv - lo) / (hi - lo), 0, 1)
    cv = 255 - t * (255 - darkest)
    halo = ndimage.gaussian_filter(halo_src.astype(float), 90)   # 凤凰附近留白
    return cv + (255 - cv) * np.clip(halo * 0.85, 0, 1)


def compose(weight, blur, deepen, levels):
    pg, pa, (dx0, dy0, dx1, dy1), mm_full, box = phoenix_placed(deepen)
    cv = make_cloud(weight, blur, levels, mm_full)
    sub = cv[dy0:dy1, dx0:dx1]
    cv[dy0:dy1, dx0:dx1] = sub * (1 - pa) + pg * pa
    return cv, box, mm_full


if __name__ == '__main__':
    want = [x for x in sys.argv[1:] if x in OPTS] or ['云淡']
    print('凤凰 S=%.2f 质心锚定 (%.1f%%, %.1f%%)' % (S, 100 * AX, 100 * AY))
    for name in want:
        w, bl, dp, lv = OPTS[name]
        cv, box, mm_full = compose(w, bl, dp, lv)
        cloud = cv[(cv < 252) & (cv > 60)]
        ys2, xs2 = np.where(mm_full)
        print('%-3s 权重%.2f σ%.0f → 画面可见 %.1f%% | 云雾中位灰度 %.0f | 凤凰落位 %s | 实际占位 x[%.0f%%,%.0f%%] y[%.0f%%,%.0f%%]'
              % (name, w, bl, 100 * ((cv < 252) & (cv > 60)).mean(),
                 np.median(cloud) if cloud.size else 255, box,
                 100 * xs2.min() / W, 100 * xs2.max() / W,
                 100 * ys2.min() / H, 100 * ys2.max() / H))
        out = D / (os.environ.get('PHX_OUT', 'phoenix-full.png') if len(want) == 1
                   else f'phoenix-full-{name}.png')
        Image.fromarray(cv.astype(np.uint8), 'L').convert('RGB').save(out)
        Image.fromarray(cv.astype(np.uint8)).resize((760, round(760 * H / W)), Image.LANCZOS) \
             .save(f'/tmp/cloud-{name}.png')
