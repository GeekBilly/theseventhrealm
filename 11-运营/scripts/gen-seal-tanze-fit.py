#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印章换字 v2：按「气势」定字，印面尺寸跟着字走（2026-10-02）

与 v1 的区别
----------
v1 是在**固定的 136×195 印面**里塞字 → 两个字竖着叠起来高度就占满，宽度只能收窄，
字号被压到 82px → 笔画只有 2.2px（原印「境」3.18px），显得规矩、没气势。

v2 反过来：**先定目标笔画粗度**（对齐原印「境」3.18px，或更雄浑的 3.8px），
反推字号，再让印面按字撑出来的尺寸长 —— 高宽不限，跟着字走。

关键量（实测）
------------
  · 原印锚点：「境」笔画 3.18px（14 画）、「七」4.70px（2 画）
  · 马善政每 100px 字号：「探」2.99px / 「赜」2.91px
  · 原印留白比例：横向单侧 9.5%，纵向单侧 5.7% → 统一取 5.7%（更撑满＝更有气势）
  · 原印外圈（透明边＋边框带＋空隙环）：左 12 / 右 12 / 上 11 / 下 10

构造方式
--------
  · 外圈用**九宫格**：四角原样取原印，四条边只拉伸长度 → 边框粗细与手作感不变
  · 内区红底用原印印泥均值，斑驳用「高频残差采样」从原印搬运（add_mottle）
  · 仍是阴文：字＝alpha 0 的洞，贴到任何底色都透出底色

用法
----
    python3 gen-seal-tanze-fit.py                  # 竖排，笔画 3.8px
    python3 gen-seal-tanze-fit.py --layout h       # 横排
    python3 gen-seal-tanze-fit.py --target 3.18    # 严格对齐原印「境」
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
SEAL = os.path.join(ROOT, "02-商品/02-素材/底纹/seal.png")
OUTDIR = os.path.dirname(SEAL)
FONT_ROOT = os.path.join(ROOT, "02-商品/02-素材/字体")
FONTS = {
    "马善政": os.path.join(FONT_ROOT, "MaShanZheng.ttf"),
    "龙藏": os.path.join(FONT_ROOT, "fonts/龙藏.ttf"),
    "挚芒行": os.path.join(FONT_ROOT, "fonts/挚芒行.ttf"),
    "柳建毛草": os.path.join(FONT_ROOT, "fonts/柳建毛草.ttf"),
    "宋体Black": ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    "黑体W6": ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
}

TEXT = "探赜"
SS = 4                     # 超采样
THR = 128                  # 二值阈值
MARGIN = 0.057             # 单侧留白 / 内容尺寸（原印纵向实测 5.7%）
GAP_K = 0.08               # 字间距 / 字号（原印 8px @ 100px 字号）
RING = dict(l=12, r=12, t=11, b=10)   # 外圈厚度（原印实测）
FIELD = (12, 11, 124, 185)            # 原印内区（实测，供九宫格取边条/底色）


def _font_path(name):
    v = FONTS[name]
    return (v, 0) if isinstance(v, str) else v


def erode(m):
    e = m.copy()
    e &= np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    e[0, :] = e[-1, :] = False
    e[:, 0] = e[:, -1] = False
    return e


def stroke_w(mask):
    """腐蚀法测笔画平均宽度"""
    a = [int(mask.sum())]
    cur = mask
    while cur.any() and len(a) < 300:
        cur = erode(cur)
        if not cur.any():
            break
        a.append(int(cur.sum()))
    return 2 * sum(a[1:]) / a[0] if a[0] else 0.0


def glyph_img(ch, font_path, fidx, em, ss=SS):
    """渲染单字并裁到实际墨迹外框，返回 (超采样图, 1x 宽, 1x 高)

    ⚠️ 不能用 textbbox 当外框：TrueType 在不同字号下 hinting 会跳变，
    实测 100px→90×88、124px→124×112（宽增长 38% 而字号只增 24%），
    会把印面撑得虚大。一律按渲染后的**实际墨迹**裁。
    """
    f = ImageFont.truetype(font_path, int(em * ss), index=fidx)
    pad = int(30 * ss)
    img = Image.new("L", (int(em * ss * 3), int(em * ss * 3)), 0)
    ImageDraw.Draw(img).text((pad, pad), ch, font=f, fill=255)
    arr = np.asarray(img)
    ys, xs = np.where(arr > 0)
    if len(ys) == 0:
        raise SystemExit(f"书体缺字形：{ch}")
    crop = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h1, w1 = crop.shape[0] / ss, crop.shape[1] / ss
    return Image.fromarray(crop), w1, h1


def measure(ch, font_path, fidx, em):
    img, w, h = glyph_img(ch, font_path, fidx, em)
    small = img.resize((max(1, int(img.size[0] / SS)), max(1, int(img.size[1] / SS))),
                       Image.LANCZOS)
    return stroke_w(np.asarray(small) > THR), w, h


def solve_em(font_path, fidx, target, ref=TEXT[1]):
    """反推：让 ref 字的笔画宽 = target，返回字号"""
    em = 100.0
    for _ in range(8):
        w, _, _ = measure(ref, font_path, fidx, em)
        if abs(w - target) < 0.04:
            break
        em *= target / w
    return em


def layout_canvas(text, font_path, fidx, em, vertical=True):
    """把两字排到内区，返回 (字掩码[1x], 内区宽, 内区高)"""
    imgs, metas = [], []
    for ch in text:
        img, w, h = glyph_img(ch, font_path, fidx, em)
        imgs.append(img)
        metas.append((w, h))
    gap = round(em * GAP_K)
    if vertical:
        content_w = max(m[0] for m in metas)
        content_h = sum(m[1] for m in metas) + gap
    else:
        content_w = sum(m[0] for m in metas) + gap
        content_h = max(m[1] for m in metas)
    W_in = round(content_w * (1 + 2 * MARGIN))
    H_in = round(content_h * (1 + 2 * MARGIN))

    canvas = Image.new("L", (W_in * SS, H_in * SS), 0)
    x0 = (W_in - content_w) / 2
    y0 = (H_in - content_h) / 2
    cx, cy = x0, y0
    for img, (w, h) in zip(imgs, metas):
        px = (W_in - w) / 2 if vertical else cx
        py = cy if vertical else (H_in - h) / 2
        layer = Image.new("L", canvas.size, 0)
        layer.paste(img, (int(px * SS), int(py * SS)))
        canvas = ImageChops.lighter(canvas, layer)
        if vertical:
            cy += h + gap
        else:
            cx += w + gap

    small = np.asarray(canvas.resize((W_in, H_in), Image.LANCZOS))
    return small > THR, W_in, H_in


def build(mask, W_in, H_in, src_rgb, src_a, rng):
    """九宫格拼外圈 + 内区红底斑驳 + 打孔"""
    R = RING
    W = W_in + R["l"] + R["r"]
    H = H_in + R["t"] + R["b"]
    fx0, fy0, fx1, fy1 = FIELD          # 原印内区
    new = np.zeros((H, W, 4), np.uint8)

    def grab(box):                       # 从原印取 RGBA 块
        return np.asarray(
            Image.fromarray(np.dstack([src_rgb, src_a]).astype(np.uint8), "RGBA").crop(box))

    # 四角（原尺寸）
    corners = {
        "tl": ((0, 0, fx0, fy0), (0, 0)),
        "tr": ((fx1, 0, src_a.shape[1], fy0), (W - (src_a.shape[1] - fx1), 0)),
        "bl": ((0, fy1, fx0, src_a.shape[0]), (0, H - (src_a.shape[0] - fy1))),
        "br": ((fx1, fy1, src_a.shape[1], src_a.shape[0]),
               (W - (src_a.shape[1] - fx1), H - (src_a.shape[0] - fy1))),
    }
    for k, (sbox, dpos) in corners.items():
        c = grab(sbox)
        new[dpos[1]:dpos[1] + c.shape[0], dpos[0]:dpos[0] + c.shape[1]] = c

    # 四条边（只拉伸长度）
    edges = [
        # (源框, 目标 x/y, 目标尺寸, 是否横向拉伸)
        ((fx0, 0, fx1, fy0), (R["l"], 0), (W_in, R["t"])),                     # 上
        ((fx0, fy1, fx1, src_a.shape[0]), (R["l"], H - R["b"]), (W_in, R["b"])),  # 下
        ((0, fy0, fx0, fy1), (0, R["t"]), (R["l"], H_in)),                     # 左
        ((fx1, fy0, src_a.shape[1], fy1), (W - R["r"], R["t"]), (R["r"], H_in)),  # 右
    ]
    for sbox, dpos, dsize in edges:
        im = Image.fromarray(grab(sbox), "RGBA").resize(dsize, Image.LANCZOS)
        new[dpos[1]:dpos[1] + dsize[1], dpos[0]:dpos[0] + dsize[0]] = np.asarray(im)

    # 内区：红底 + 斑驳
    opaque = src_a > 200
    inner_src = np.zeros(src_a.shape, bool)
    inner_src[fy0:fy1, fx0:fx1] = True
    donor = inner_src & opaque
    mean_rgb = src_rgb[donor].mean(axis=0)
    fill = np.zeros((H, W, 3), np.float32)
    fill[:] = mean_rgb
    # 高频残差搬运
    from PIL import ImageFilter
    blur = np.asarray(Image.fromarray(src_rgb.astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(3.0))).astype(np.float32)
    tex = src_rgb.astype(np.float32) - blur
    dy, dx = np.where(donor)
    tgt = np.zeros((H, W), bool)
    tgt[R["t"]:R["t"] + H_in, R["l"]:R["l"] + W_in] = True
    n = int(tgt.sum())
    pick = rng.integers(0, len(dy), n)
    fill[tgt] += tex[dy[pick], dx[pick]]
    fill = np.clip(fill, 0, 255)

    alpha = new[:, :, 3].copy()
    alpha[tgt] = 255
    rgb = fill.copy()
    # 打孔
    alpha[R["t"]:R["t"] + H_in, R["l"]:R["l"] + W_in][mask] = 0
    rgb[alpha == 0] = 255
    out = np.dstack([rgb.astype(np.uint8), alpha])
    return Image.fromarray(out, "RGBA"), (W, H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default="马善政", choices=list(FONTS))
    ap.add_argument("--target", type=float, default=3.8,
                    help="目标笔画粗度 px（原印「境」3.18 / 「七」4.70）")
    ap.add_argument("--layout", default="v", choices=["v", "h"], help="v 竖排 / h 横排")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Image.open(SEAL).convert("RGBA")
    sa = np.asarray(src)
    src_rgb = sa[:, :, :3].astype(np.float32)
    src_a = sa[:, :, 3]
    fp, fi = _font_path(args.font)

    for ch in TEXT:
        w100, _, _ = measure(ch, fp, fi, 100)
        if w100 <= 0:
            raise SystemExit(f"书体「{args.font}」缺字：{ch}")

    em = solve_em(fp, fi, args.target)
    w_ref, gw, gh = measure(TEXT[1], fp, fi, em)
    w_a, aw, ah = measure(TEXT[0], fp, fi, em)
    print(f"书体 {args.font}  目标笔画 {args.target}px → 字号 {em:.1f}px")
    print(f"  {TEXT[0]}: 外框 {aw:.0f}×{ah:.0f}  笔画 {w_a:.2f}px")
    print(f"  {TEXT[1]}: 外框 {gw:.0f}×{gh:.0f}  笔画 {w_ref:.2f}px")

    mask, W_in, H_in = layout_canvas(TEXT, fp, fi, em, vertical=(args.layout == "v"))
    rng = np.random.default_rng(20261002)
    img, (W, H) = build(mask, W_in, H_in, src_rgb, src_a, rng)
    print(f"内区 {W_in}×{H_in}  →  整印 {W}×{H}（原印 136×195）")

    tag = "竖" if args.layout == "v" else "横"
    name = args.out or f"印章-探赜-{args.font}-{tag}排-{args.target:g}px.png"
    p = os.path.join(OUTDIR, name)
    img.save(p)
    print("输出：", p)

    # 自检
    a = np.asarray(img)[:, :, 3]
    hole = (a < 128)
    hole[:RING["t"], :] = hole[-RING["b"]:, :] = False
    hole[:, :RING["l"]] = hole[:, -RING["r"]:] = False
    print(f"自检：印面内字洞 {int(hole.sum())} px  笔画 {stroke_w(hole):.2f}px")
    return p, (W, H)


if __name__ == "__main__":
    main()
