#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印章换字 v4：生成式书法（结构锁定）+ 墨迹清理

为什么有 v4
----------
v3 直接用 `灰度<150` 硬阈值从 AI 黑字图抠墨迹，笔画边缘的毛刺、笔道内的
浅灰碎纹全部被保留；做进阴文印章（字＝alpha 0 的洞）后，这些碎点就是
用户看到的「白色笔触不干净」。

v4 在 v3 基础上加两步：
  A. 原图级清理（1024px 图）：连通域过滤去水印/杂点 → 闭运算填笔道内小孔
     → 开运算磨掉边缘毛刺、游离细丝。
  B. 目标尺寸级清理（内区 1x）：再填一次 <2px 的针孔、磨掉 <1px 的碎边，
     这才是肉眼在壁纸角标尺寸（高 110px）真正看得见的脏点。

字形来源
--------
AI 生成图会自作主张把「赜」左偏旁写成「贝」。v4 的做法是先用系统字体
（Songti SC）渲染一张**结构权威**的参考图，再让生成模型按该结构重写为
毛笔字（`--src` 指向生成结果）。印章构造完全沿用 v2：九宫格外圈
（四角原样、四边只拉伸）+ 印泥均值 + 高频残差斑驳；仍是阴文。

用法
----
    python3 gen-seal-tanze-v4.py --src 生图源/xxx.png --layout v
    python3 gen-seal-tanze-v4.py --src latest --layout h --rtl
    python3 gen-seal-tanze-v4.py --src latest --raw      # 关掉清理，做 A/B
"""
import argparse
import glob
import importlib.util
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
SEAL_DIR = os.path.join(ROOT, "02-商品/02-素材/底纹")
GEN_DIR = os.path.join(SEAL_DIR, "生图源")      # AI 生成的书法图
OUTDIR = SEAL_DIR
FIT_PY = os.path.join(ROOT, "11-运营/scripts/gen-seal-tanze-fit.py")

# 复用 v2 的印章构造（九宫格外圈 + 印泥 + 斑驳 + 打孔）
_spec = importlib.util.spec_from_file_location("sealfit", FIT_PY)
sealfit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sealfit)

INK_THR = 150          # 墨迹阈值（水印是浅灰，会被自然排除）
MIN_BLOB = 80          # 原图级：小于此面积的连通块视为噪点
CLOSE_R = 5            # 原图级：闭运算半径（填笔道内小孔，保大飞白）
OPEN_R = 2             # 原图级：开运算半径（磨边缘毛刺）
FINE_CLOSE_R = 1       # 目标级：填 <1px 针孔
FINE_OPEN_R = 1        # 目标级：磨 <1px 碎边
CONTENT_H = 168        # 目标内容高（原印「七」顶到「境」底实测 156）
GAP_K = 0.075          # 字间距 / 内容高


def disk(r):
    if r <= 0:
        return None
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def blob_filter(m, min_area):
    """只保留面积 >= min_area 的连通块"""
    lab, n = ndi.label(m, structure=np.ones((3, 3), int))
    if n == 0:
        return m
    keep = np.zeros(n + 1, bool)
    sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
    keep[1:] = sizes >= min_area
    return keep[lab]


def clean_coarse(m):
    """原图级清理：去杂点 → 填小孔 → 磨毛刺 → 再去杂点"""
    m = blob_filter(m, MIN_BLOB)
    m = ndi.binary_closing(m, structure=disk(CLOSE_R), border_value=0)
    m = ndi.binary_opening(m, structure=disk(OPEN_R), border_value=0)
    return blob_filter(m, MIN_BLOB)


def clean_fine(m):
    """目标尺寸级清理：填针孔、磨碎边（字洞在 2~4px 量级）"""
    m = ndi.binary_closing(m, structure=disk(FINE_CLOSE_R), border_value=0)
    m = ndi.binary_opening(m, structure=disk(FINE_OPEN_R), border_value=0)
    return blob_filter(m, 12)


def ink_mask(path, do_clean=True):
    a = np.asarray(Image.open(path).convert("L"))
    m = a < INK_THR
    if do_clean:
        m = clean_coarse(m)
    return m


def split_two(m):
    """按空白带切成上、下两字，并各自裁到墨迹外框"""
    rows = m.sum(axis=1)
    nz = np.where(rows > 0)[0]
    y0, y1 = int(nz.min()), int(nz.max())
    lo, hi = y0 + int((y1 - y0) * 0.30), y0 + int((y1 - y0) * 0.70)
    zeros = [y for y in range(lo, hi) if rows[y] == 0]
    if zeros:
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
    """按比例缩放（LANCZOS，保留抗锯齿过渡）"""
    nh, nw = max(1, int(round(g.shape[0] * s))), max(1, int(round(g.shape[1] * s)))
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
    return np.asarray(im) > 128


def make_mask(g1, g2, vertical=True, content_h=CONTENT_H, do_clean=True):
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
    if do_clean:
        mask = clean_fine(mask)
    return mask, W_in, H_in


def build_seal(mask, W_in, H_in, seed=20261002):
    src = Image.open(os.path.join(SEAL_DIR, "seal.png")).convert("RGBA")
    sa = np.asarray(src)
    src_rgb = sa[:, :, :3].astype(np.float32)
    src_a = sa[:, :, 3]
    rng = np.random.default_rng(seed)
    return sealfit.build(mask, W_in, H_in, src_rgb, src_a, rng)


def resolve_src(v):
    if v == "latest":
        fs = sorted(glob.glob(os.path.join(GEN_DIR, "*.png")))
        if not fs:
            raise SystemExit(f"生图源目录为空：{GEN_DIR}")
        return fs[-1]
    p = v if os.path.isabs(v) else os.path.join(GEN_DIR, v)
    if not os.path.exists(p):
        fs = sorted(glob.glob(os.path.join(GEN_DIR, "*.png")))
        if v.isdigit() and 1 <= int(v) <= len(fs):
            return fs[int(v) - 1]
        raise SystemExit(f"找不到：{p}")
    return p


def main():
    global CLOSE_R, OPEN_R, FINE_CLOSE_R, FINE_OPEN_R
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="latest", help="生图源文件名 / 序号 / latest")
    ap.add_argument("--layout", default="v", choices=["v", "h"])
    ap.add_argument("--rtl", action="store_true", help="横排改为右起（赜在右）")
    ap.add_argument("--raw", action="store_true", help="关掉墨迹清理（做 A/B 对照）")
    ap.add_argument("--close-r", type=int, default=CLOSE_R, help="原图级闭运算半径")
    ap.add_argument("--open-r", type=int, default=OPEN_R, help="原图级开运算半径")
    ap.add_argument("--fine-close-r", type=int, default=FINE_CLOSE_R, help="目标级闭运算半径")
    ap.add_argument("--fine-open-r", type=int, default=FINE_OPEN_R, help="目标级开运算半径")
    ap.add_argument("--content-h", type=int, default=CONTENT_H)
    ap.add_argument("--tag", default=None, help="输出文件名标签")
    args = ap.parse_args()

    CLOSE_R, OPEN_R = args.close_r, args.open_r
    FINE_CLOSE_R, FINE_OPEN_R = args.fine_close_r, args.fine_open_r

    f = resolve_src(args.src)
    do_clean = not args.raw
    m = ink_mask(f, do_clean=do_clean)
    g1, g2 = split_two(m)
    if args.rtl and args.layout == "h":
        g1, g2 = g2, g1
    mask, W_in, H_in = make_mask(g1, g2, vertical=(args.layout == "v"),
                                 content_h=args.content_h, do_clean=do_clean)
    img, (W, H) = build_seal(mask, W_in, H_in)

    tag = args.tag or ("v4-" + ("clean" if do_clean else "raw"))
    lay = ("竖" if args.layout == "v" else "横") + ("右起" if (args.rtl and args.layout == "h") else "")
    name = f"印章-探赜-{tag}-{lay}排.png"
    p = os.path.join(OUTDIR, name)
    img.save(p)

    hole = np.asarray(img)[:, :, 3] < 128
    ring = sealfit.RING
    hole[:ring["t"], :] = hole[-ring["b"]:, :] = False
    hole[:, :ring["l"]] = hole[:, -ring["l"]:] = False
    print(f"源   {os.path.basename(f)[:60]}")
    print(f"清理 {'开' if do_clean else '关'}   内区 {W_in}×{H_in} → 整印 {W}×{H}"
          f"   字洞 {int(hole.sum())}px   笔画 {sealfit.stroke_w(hole):.2f}px")
    print(f"输出 {p}")
    return p


if __name__ == "__main__":
    main()
