#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印章换字 v3：字形改用 **生成式毛笔书法**（不是字体）

为什么有 v3
----------
原印「七境」是 9-28 从品牌 logo 图里抠出的**毛笔书法字**，不是字体渲染的
（与手上 4 个毛笔字体 IoU 最高仅 0.46）。所以换字用字体必然丢掉笔锋
（斜切入起笔 / 出锋拖尾 / 飞白）。v3 直接把 AI 生成的毛笔「探赜」做进印章。

与 v2 的区别
-----------
  · 字形来源：字体渲染 → **生成式书法图**（`探赜书法候选/*.png`）
  · 印章构造完全沿用 v2：九宫格外圈（四角原样、四边只拉伸）+ 印泥均值 + 高频残差斑驳
  · 仍是阴文：字＝alpha 0 的洞

用法
----
    python3 gen-seal-calligraphy.py --idx 3                # 用第 3 张候选，竖排
    python3 gen-seal-calligraphy.py --idx 3 --layout h     # 横排
    python3 gen-seal-calligraphy.py --all                  # 三张候选各出一枚
"""
import argparse
import glob
import importlib.util
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
SEAL_DIR = os.path.join(ROOT, "02-商品/02-素材/底纹")
CAND_GLOB = "探赜书法-候选*.png"        # 生成式书法候选（1 颜体行楷 / 2 行楷 / 3 行书）
OUTDIR = SEAL_DIR
FIT_PY = os.path.join(ROOT, "11-运营/scripts/gen-seal-tanze-fit.py")

# 复用 v2 的印章构造（九宫格外圈 + 印泥 + 斑驳 + 打孔）
_spec = importlib.util.spec_from_file_location("sealfit", FIT_PY)
sealfit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sealfit)

INK_THR = 150          # 墨迹阈值（右下角 AI 水印是浅灰，会被自然排除）
MIN_BLOB = 40          # 小于此面积的连通块视为噪点
CONTENT_H = 168        # 目标内容高（原印「七」顶到「境」底实测 156，略放大更有气势）
GAP_K = 0.075          # 字间距 / 内容高


def ink_mask(path):
    a = np.asarray(Image.open(path).convert("L"))
    return a < INK_THR


def clean(m):
    """去小噪点（水印、纸纹）"""
    from collections import deque
    h, w = m.shape
    lab = np.zeros((h, w), np.int32); cid = 0; keep = np.zeros((h, w), bool)
    ys, xs = np.where(m)
    for y0, x0 in zip(ys, xs):
        if not m[y0, x0] or lab[y0, x0]:
            continue
        cid += 1
        q = deque([(y0, x0)]); lab[y0, x0] = cid; px = []
        while q:
            cy, cx = q.popleft(); px.append((cy, cx))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and lab[ny, nx] == 0:
                    lab[ny, nx] = cid; q.append((ny, nx))
        if len(px) >= MIN_BLOB:
            for cy, cx in px:
                keep[cy, cx] = True
    return keep


def split_two(m):
    """按空白带切成上、下两字，并各自裁到墨迹外框"""
    rows = m.sum(axis=1)
    nz = np.where(rows > 0)[0]
    y0, y1 = int(nz.min()), int(nz.max())
    lo, hi = y0 + int((y1 - y0) * 0.30), y0 + int((y1 - y0) * 0.70)
    zeros = [y for y in range(lo, hi) if rows[y] == 0]
    if zeros:
        # 取最长连续空白带的中点
        runs, s = [], zeros[0]
        for i in range(1, len(zeros)):
            if zeros[i] != zeros[i - 1] + 1:
                runs.append((s, zeros[i - 1])); s = zeros[i]
        runs.append((s, zeros[-1]))
        runs.sort(key=lambda r: r[1] - r[0], reverse=True)
        cut = (runs[0][0] + runs[0][1]) // 2
    else:
        cut = (y0 + y1) // 2

    def crop(x):
        ys, xs = np.where(x)
        return x[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    return crop(m[:cut]), crop(m[cut:])


def scaled(g, s):
    nh, nw = max(1, int(round(g.shape[0] * s))), max(1, int(round(g.shape[1] * s)))
    return np.asarray(Image.fromarray((g * 255).astype(np.uint8))
                      .resize((nw, nh), Image.LANCZOS)) > 128


def make_mask(g1, g2, vertical=True, content_h=CONTENT_H):
    """把两个字排成内区掩码（1x）"""
    h1, h2 = g1.shape[0], g2.shape[0]
    gap = max(2, int(round(content_h * GAP_K)))
    s = (content_h - gap) / (h1 + h2)
    a1, a2 = scaled(g1, s), scaled(g2, s)
    if vertical:
        cw = max(a1.shape[1], a2.shape[1])
        ch = a1.shape[0] + a2.shape[0] + gap
    else:
        cw = a1.shape[1] + a2.shape[1] + gap
        ch = max(a1.shape[0], a2.shape[0])
    M = sealfit.MARGIN
    W_in = int(round(cw * (1 + 2 * M)))
    H_in = int(round(ch * (1 + 2 * M)))
    mask = np.zeros((H_in, W_in), bool)
    x, y = (W_in - cw) // 2, (H_in - ch) // 2
    if vertical:
        for a in (a1, a2):
            px = (W_in - a.shape[1]) // 2
            mask[y:y + a.shape[0], px:px + a.shape[1]] |= a
            y += a.shape[0] + gap
    else:
        for a in (a1, a2):
            py = (H_in - a.shape[0]) // 2
            mask[py:py + a.shape[0], x:x + a.shape[1]] |= a
            x += a.shape[1] + gap
    return mask, W_in, H_in


def build_seal(mask, W_in, H_in, seed=20261002):
    src = Image.open(os.path.join(SEAL_DIR, "seal.png")).convert("RGBA")
    sa = np.asarray(src)
    src_rgb = sa[:, :, :3].astype(np.float32)
    src_a = sa[:, :, 3]
    rng = np.random.default_rng(seed)
    return sealfit.build(mask, W_in, H_in, src_rgb, src_a, rng)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idx", type=int, default=3, help="第几张候选（1 起）")
    ap.add_argument("--layout", default="v", choices=["v", "h"])
    ap.add_argument("--rtl", action="store_true",
                    help="横排时按传统改为右起（赜在右、探在左）")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--content-h", type=int, default=CONTENT_H)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(SEAL_DIR, CAND_GLOB)))
    if not files:
        raise SystemExit(f"没有候选图：{SEAL_DIR}/{CAND_GLOB}")

    picks = range(1, len(files) + 1) if args.all else [args.idx]
    made = []
    for i in picks:
        f = files[i - 1]
        m = clean(ink_mask(f))
        g1, g2 = split_two(m)
        if args.rtl and args.layout == "h":
            g1, g2 = g2, g1          # 传统右起：赜在右、探在左
        mask, W_in, H_in = make_mask(g1, g2, vertical=(args.layout == "v"),
                                     content_h=args.content_h)
        img, (W, H) = build_seal(mask, W_in, H_in)
        tag = ("竖" if args.layout == "v" else "横") + ("右起" if (args.rtl and args.layout == "h") else "")
        name = f"印章-探赜-书法{i}-{tag}排.png"
        p = os.path.join(OUTDIR, name)
        img.save(p)
        hole = np.asarray(img)[:, :, 3] < 128
        ring = sealfit.RING
        hole[:ring["t"], :] = hole[-ring["b"]:, :] = False
        hole[:, :ring["l"]] = hole[:, -ring["l"]:] = False
        print(f"[{i}] {os.path.basename(f)[:26]}…  内区 {W_in}×{H_in} → 整印 {W}×{H}"
              f"  字洞 {int(hole.sum())}px  笔画 {sealfit.stroke_w(hole):.2f}px")
        print(f"    输出 {p}")
        made.append(p)
    return made


if __name__ == "__main__":
    main()
