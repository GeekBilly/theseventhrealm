#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印章换字：七境 → 探赜（2026-10-02）

原理（关键发现）：`02-商品/02-素材/底纹/seal.png` 是**阴文（白文）印章**——
  - RGBA，alpha **只有 0 / 255 两个值**，没有中间调；
  - 红色印泥 = alpha 255；**字样与边框空隙 = alpha 0（透明孔洞）**；
  - 所以「白字」其实是「透出背景的洞」。

因此换字**不需要动 RGB**，只改 **alpha 通道**：
  1. 把原「七境」两字的孔洞重新填红（alpha=255）；
  2. 按原印的字位、字高，重新打「探赜」两字的孔（alpha=0）。
边框带、空隙、印面斑驳颗粒**原样不动** → 除字以外与旧印完全一致。

用法：
    python3 gen-seal-tanze.py            # 生成
    python3 gen-seal-tanze.py --font 龙藏   # 换书体（默认马善政）
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
SEAL = os.path.join(ROOT, "02-商品/02-素材/底纹/seal.png")
OUTDIR = os.path.dirname(SEAL)
FONT_ROOT = os.path.join(ROOT, "02-商品/02-素材/字体")
FONTS = {
    "马善政": os.path.join(FONT_ROOT, "MaShanZheng.ttf"),
    "龙藏": os.path.join(FONT_ROOT, "fonts/龙藏.ttf"),
    "挚芒行": os.path.join(FONT_ROOT, "fonts/挚芒行.ttf"),
    "柳建毛草": os.path.join(FONT_ROOT, "fonts/柳建毛草.ttf"),
    # 印刷体备选：不如毛笔像原印，但小尺寸可读性高得多
    "宋体Black": ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    "黑体W6": ("/System/Library/Fonts/Hiragino Sans GB.ttc", 2),
}


def _font_path(name):
    """返回 (路径, TTC 索引)"""
    v = FONTS[name]
    return (v, 0) if isinstance(v, str) else v
TEXT = "探赜"
SS = 4                      # 超采样倍数
THR = 128                   # alpha 判定阈值

# 原印几何（实测）：印面内区 + 两字孔洞外框
FIELD = (14, 14, 124, 183)          # 印面内区 x0,y0,x1,y1（不含边框带与空隙）
GLYPH_TOP_MARGIN = 4                # 首字上留白
GLYPH_GAP = 8                       # 两字间距
GLYPH_BOTTOM_MARGIN = 5             # 末字下留白
MIN_HOLE_AREA = 8                   # 小于此面积的透明点＝印面斑驳，不视为字


def field_and_holes(alpha):
    """返回 (印面内区掩码, 字洞掩码)"""
    x0, y0, x1, y1 = FIELD
    inner = np.zeros(alpha.shape, bool)
    inner[y0 + 3:y1 - 2, x0 + 3:x1 - 2] = True
    hole = (alpha < THR) & inner

    # 连通域：按面积过滤，只留字（去掉 1–3px 的斑驳点）
    H, W = hole.shape
    lab = np.zeros(hole.shape, np.int32)
    cur = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if hole[y, x] and lab[y, x] == 0:
                cur += 1
                stack = [(y, x)]
                lab[y, x] = cur
                while stack:
                    cy, cx = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and hole[ny, nx] and lab[ny, nx] == 0:
                            lab[ny, nx] = cur
                            stack.append((ny, nx))
    sizes = np.bincount(lab.ravel())
    keep = np.where(sizes >= MIN_HOLE_AREA)[0]
    keep = keep[keep != 0]
    glyph = np.isin(lab, keep)
    return inner, glyph


def _ink(path, idx, ch, size=100):
    img = Image.new("L", (size * 2, size * 2), 255)
    ImageDraw.Draw(img).text((size // 2, size // 2), ch,
                             font=ImageFont.truetype(path, size, index=idx), fill=0)
    return sum(1 for v in img.getdata() if v < 200)


def font_covers(path, idx, ch):
    """缺字自检：与私用区 U+E000 的豆腐块墨量相同 → 判定缺字
    （教训来自 2026-10-02 商标图样：子集化字体会缺「赜」，印出豆腐块）"""
    try:
        return _ink(path, idx, ch) != _ink(path, idx, "\uE000")
    except Exception:
        return False


def render_pair(font_path, index, field_w, field_h, ss=SS):
    """渲染「探赜」两字，返回 (字体对象, 各字外框, 各字高, 各字宽, 字号)"""
    avail = field_h - GLYPH_TOP_MARGIN - GLYPH_GAP - GLYPH_BOTTOM_MARGIN
    em = int(avail * ss * 1.35)          # 试探字号
    for _ in range(60):
        f = ImageFont.truetype(font_path, em, index=index)
        boxes = []
        tmp = ImageDraw.Draw(Image.new("L", (10, 10)))
        for ch in TEXT:
            bb = tmp.textbbox((0, 0), ch, font=f)
            boxes.append(bb)
        hs = [b[3] - b[1] for b in boxes]
        ws = [b[2] - b[0] for b in boxes]
        if sum(hs) <= avail * ss and max(ws) <= field_w * ss * 0.96:
            break
        em = int(em * 0.96)
        if em < 20:
            break
    hs = [b[3] - b[1] for b in boxes]
    ws = [b[2] - b[0] for b in boxes]
    # 若仍超宽，按宽度再缩一次
    k = min(1.0, (field_w * ss * 0.96) / max(ws)) if max(ws) else 1.0
    if k < 1.0:
        em = max(20, int(em * k))
        f = ImageFont.truetype(font_path, em, index=index)
        boxes = [tmp.textbbox((0, 0), ch, font=f) for ch in TEXT]
        hs = [b[3] - b[1] for b in boxes]
        ws = [b[2] - b[0] for b in boxes]
    return f, boxes, hs, ws, em


def inpaint_red(rgb, opaque, target):
    """把 target 区域的 RGB 用邻近印泥色填上（洋葱皮扩散，保留大尺度明暗）"""
    fill = rgb.astype(np.float32).copy()
    todo = target.copy()
    known = (~target) & opaque
    for _ in range(500):
        if not todo.any():
            break
        acc = np.zeros_like(fill)
        cnt = np.zeros(todo.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                sh_f = np.roll(np.roll(fill, dy, 0), dx, 1)
                sh_k = np.roll(np.roll(known, dy, 0), dx, 1)
                acc += sh_f * sh_k[..., None]
                cnt += sh_k
        ready = todo & (cnt > 0)
        if not ready.any():
            break
        c = np.maximum(cnt, 1)[..., None]
        fill[ready] = (acc / c)[ready]
        known |= ready
        todo &= ~ready
    return fill


def add_mottle(fill, rgb, donor, target, rng, sigma=3.0):
    """洋葱皮填出来是平的 → 从印面已知区取「高频残差」贴回去，恢复斑驳"""
    blur = np.asarray(
        Image.fromarray(rgb.astype(np.uint8)).filter(ImageFilter.GaussianBlur(sigma))
    ).astype(np.float32)
    tex = rgb.astype(np.float32) - blur
    dy, dx = np.where(donor)
    n = int(target.sum())
    if n == 0 or len(dy) == 0:
        return fill
    pick = rng.integers(0, len(dy), n)
    f = fill.copy()
    f[target] += tex[dy[pick], dx[pick]]
    return np.clip(f, 0, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default="马善政", choices=list(FONTS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Image.open(SEAL).convert("RGBA")
    a = np.asarray(src).copy()
    rgb = a[:, :, :3].astype(np.float32)
    alpha = a[:, :, 3].copy()
    print(f"原印 {src.size}  alpha 取值 {np.unique(alpha)}")

    inner, glyph = field_and_holes(alpha)
    ys, xs = np.where(glyph)
    print(f"识别到字洞 {glyph.sum()} px，bbox x {xs.min()}-{xs.max()}  y {ys.min()}-{ys.max()}")

    # ① 抹旧字：孔洞外扩 2px（吃掉毛刺）→ 该区域补回印泥色
    heal = glyph.copy()
    for _ in range(2):
        d = np.zeros_like(heal)
        d[1:, :] |= heal[:-1, :]
        d[:-1, :] |= heal[1:, :]
        d[:, 1:] |= heal[:, :-1]
        d[:, :-1] |= heal[:, 1:]
        heal = d & inner

    x0, y0, x1, y1 = FIELD
    field_box = np.zeros(alpha.shape, bool)
    field_box[y0:y1, x0:x1] = True
    opaque = alpha > 200
    donor = field_box & opaque & ~heal          # 供取色的印面已知区
    rng = np.random.default_rng(20261002)

    fill = inpaint_red(rgb, opaque, heal)
    fill = add_mottle(fill, rgb, donor, heal, rng)
    new_rgb = rgb.copy()
    new_rgb[heal] = fill[heal]
    print(f"抹掉旧字 {heal.sum()} px，用邻近印泥色 + 斑驳残差补回")

    new_alpha = alpha.copy()
    new_alpha[heal] = 255

    # ② 打新孔：超采样渲染 → 缩回原尺寸 → 加噪阈值（模仿原印的硬边+毛刺）
    fw, fh = x1 - x0, y1 - y0
    fpath, fidx = _font_path(args.font)
    for ch in TEXT:                      # 缺字自检（豆腐块防线）
        if not font_covers(fpath, fidx, ch):
            raise SystemExit(f"❌ 书体「{args.font}」缺字形：{ch} —— 换一个字体")
    font, boxes, hs, ws, em = render_pair(fpath, fidx, fw, fh)
    print(f"书体 {args.font}  字号 {em/SS:.1f}px  字高 {[round(h/SS,1) for h in hs]}  字宽 {[round(w/SS,1) for w in ws]}")

    canvas = Image.new("L", (fw * SS, fh * SS), 0)
    d = ImageDraw.Draw(canvas)
    total = sum(hs) + GLYPH_GAP * SS
    y = (fh * SS - total) / 2 + 1
    for ch, bb, gw, gh in zip(TEXT, boxes, ws, hs):
        x = (fw * SS - gw) / 2 - bb[0]
        d.text((x, y - bb[1]), ch, font=font, fill=255)
        y += gh + GLYPH_GAP * SS
    small = np.asarray(canvas.resize((fw, fh), Image.LANCZOS)).astype(np.int16)
    noisy = small + rng.integers(-16, 17, small.shape)
    mask = noisy > THR
    mask &= ~(rng.random(small.shape) < 0.004)      # 啃几个小缺口，避免"太干净"

    reg_a = new_alpha[y0:y1, x0:x1]
    reg_a[mask] = 0
    new_alpha[y0:y1, x0:x1] = reg_a
    reg_c = new_rgb[y0:y1, x0:x1]
    reg_c[mask] = 255                                # 孔洞 RGB 与原图约定一致（白）
    new_rgb[y0:y1, x0:x1] = reg_c
    print(f"打新孔 {int(mask.sum())} px")

    out = Image.fromarray(
        np.dstack([np.clip(new_rgb, 0, 255).astype(np.uint8), new_alpha]), "RGBA")
    name = args.out or f"印章-探赜-{args.font}-v1.png"
    native = os.path.join(OUTDIR, name)
    out.save(native)
    big = os.path.join(OUTDIR, name.replace(".png", "-4x.png"))
    out.resize((out.size[0] * SS, out.size[1] * SS), Image.NEAREST).save(big)
    print("输出：", native)
    print("输出：", big)
    return native, big


if __name__ == "__main__":
    main()
