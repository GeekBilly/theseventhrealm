#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 商标图样生成器（本地运行，零积分）
输出符合商标局要求的图样：JPG、<200KB、边长 400-1500px、白底
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
OUT = os.path.join(ROOT, "11-运营/风险管控/商标图样")
os.makedirs(OUT, exist_ok=True)

S = 1200                      # 画布边长（在 400-1500 区间内）
JPEG_Q = 92

FONTS = {
    "宋体":      ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    "黑体":      ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    "思源宋体Black": (os.path.join(ROOT, "02-商品/02-素材/字体/fonts/NotoSerifSC-Black.ttf"), 0),
    "龙藏毛笔":   (os.path.join(ROOT, "02-商品/02-素材/字体/fonts/龙藏.ttf"), 0),
    "马善政毛笔": (os.path.join(ROOT, "02-商品/02-素材/字体/MaShanZheng.ttf"), 0),
    "TimesNewRoman": ("/System/Library/Fonts/Supplemental/Times New Roman.ttf", 0),
    "Helvetica": ("/System/Library/Fonts/Helvetica.ttc", 0),
}


def bbox_nonwhite(img, thr=240, pad=0.02):
    """定位图中非白内容的包围盒，用于裁掉多余留白"""
    g = img.convert("L")
    w, h = g.size
    mask = g.point(lambda v: 255 if v < thr else 0)
    bb = mask.getbbox()
    if not bb:
        return (0, 0, w, h)
    x0, y0, x1, y1 = bb
    p = int(w * pad)
    return (max(0, x0 - p), max(0, y0 - p), min(w, x1 + p), min(h, y1 + p))


def load(name, size):
    path, idx = FONTS[name]
    try:
        return ImageFont.truetype(path, size, index=idx)
    except Exception as e:
        print(f"  ! 字体 {name} 加载失败({e})，跳过")
        return None


def save(img, name):
    p = os.path.join(OUT, name)
    img.convert("RGB").save(p, "JPEG", quality=JPEG_Q, optimize=True)
    kb = os.path.getsize(p) / 1024
    w, h = img.size
    flag = "OK " if (kb < 200 and 400 <= max(w, h) <= 1500) else "!! "
    print(f"  {flag}{name}  {w}x{h}  {kb:.0f}KB")
    return p


def text_mark(font_name, text, fname, size_ratio=0.30, stroke=0, lines=None):
    """生成纯文字商标图样（黑字白底、居中、无边框）"""
    img = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(img)
    parts = lines if lines else [text]
    fs = int(S * size_ratio)
    f = load(font_name, fs)
    if f is None:
        return None
    # 自适应缩小以适配画布宽度
    while True:
        boxes = [d.textbbox((0, 0), t, font=f, stroke_width=stroke) for t in parts]
        wmax = max(b[2] - b[0] for b in boxes)
        if wmax <= S * 0.86 or fs <= 40:
            break
        fs = int(fs * 0.95)
        f = load(font_name, fs)
        boxes = [d.textbbox((0, 0), t, font=f, stroke_width=stroke) for t in parts]
        wmax = max(b[2] - b[0] for b in boxes)
    gap = int(fs * 0.18)
    hs = [b[3] - b[1] for b in boxes]
    total_h = sum(hs) + gap * (len(parts) - 1)
    y = (S - total_h) / 2
    for t, b, hh in zip(parts, boxes, hs):
        x = (S - (b[2] - b[0])) / 2 - b[0]
        d.text((x, y - b[1]), t, font=f, fill="black",
               stroke_width=stroke, stroke_fill="black")
        y += hh + gap
    return save(img, fname)


def seal_bbox(pad_ratio=0.015):
    """自动定位 logo 中朱红印章的包围盒（比手写坐标可靠）"""
    src = Image.open(os.path.join(ROOT, "logo-qijing.png")).convert("RGB")
    w, h = src.size
    px = src.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r - max(g, b) > 40:          # 明显偏红 = 印泥
                mp[x, y] = 255
    bb = mask.getbbox()
    if not bb:
        return (355, 170, 685, 645)
    x0, y0, x1, y1 = bb
    px_ = int(w * pad_ratio)
    return (max(0, x0 - px_), max(0, y0 - px_), min(w, x1 + px_), min(h, y1 + px_))


def seal_mark(color=True, fname="x.jpg", box=None):
    """从 logo 中提取玉玺印章，输出彩色稿 / 黑白稿"""
    src = Image.open(os.path.join(ROOT, "logo-qijing.png")).convert("RGB")
    region = src.crop(box or seal_bbox())
    w, h = region.size
    px = region.load()
    out = Image.new("RGB", (w, h), "white")
    op = out.load()
    if color:
        for y in range(h):
            for x in range(w):
                r, g, b = px[x, y]
                mx, mn = max(r, g, b), min(r, g, b)
                op[x, y] = (255, 255, 255) if mx - mn < 30 else (r, g, b)
    else:
        g_img = region.convert("L")
        g_img = g_img.point(lambda v: 0 if v < 150 else 255)
        out = g_img.convert("RGB")
    # 居中放到白底正方形
    canvas = Image.new("RGB", (S, S), "white")
    scale = min(S * 0.78 / w, S * 0.78 / h)
    nw, nh = int(w * scale), int(h * scale)
    out = out.resize((nw, nh), Image.LANCZOS)
    canvas.paste(out, ((S - nw) // 2, (S - nh) // 2))
    return save(canvas, fname)


print("生成中 →", OUT)
made = []

# A. 中文「第七境」文字商标（标准体优先：保护范围最宽）
for fn, nm in [("宋体", "A1-文字-第七境-宋体-黑白.jpg"),
               ("黑体", "A2-文字-第七境-黑体-黑白.jpg"),
               ("思源宋体Black", "A3-文字-第七境-思源宋体Black-黑白.jpg")]:
    p = text_mark(fn, "第七境", nm, size_ratio=0.30, stroke=2)
    if p: made.append(("中文·标准体", nm))

# A'. 艺术体（备选：若走艺术字方案，保护范围限于该字形）
for fn, nm in [("龙藏毛笔", "A4-文字-第七境-毛笔龙藏-黑白.jpg"),
               ("马善政毛笔", "A5-文字-第七境-毛笔马善政-黑白.jpg")]:
    p = text_mark(fn, "第七境", nm, size_ratio=0.30)
    if p: made.append(("中文·毛笔艺术体", nm))

# B. 英文 THE SEVENTH REALM 文字商标
p = text_mark("TimesNewRoman", "", "B1-文字-THE SEVENTH REALM-黑体-黑白.jpg",
              size_ratio=0.13, lines=["THE SEVENTH", "REALM"], stroke=1)
if p: made.append(("英文·标准体", os.path.basename(p)))

# C. 图形：玉玺印章
seal_mark(color=True, fname="C1-图形-玉玺印章-彩色.jpg")
made.append(("图形·彩色稿", "C1-图形-玉玺印章-彩色.jpg"))
seal_mark(color=False, fname="C2-图形-玉玺印章-黑白.jpg")
made.append(("图形·黑白稿", "C2-图形-玉玺印章-黑白.jpg"))

# D. 组合图样：印章 + 中文（横向，整体等比缩放到画布安全区内）
try:
    seal = Image.open(os.path.join(OUT, "C2-图形-玉玺印章-黑白.jpg")).convert("RGB")
    se = seal.crop(bbox_nonwhite(seal))
    f = load("思源宋体Black", 200)
    d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    b = d0.textbbox((0, 0), "第七境", font=f)
    txt = Image.new("RGB", (b[2] - b[0] + 20, b[3] - b[1] + 20), "white")
    ImageDraw.Draw(txt).text((-b[0] + 10, -b[1] + 10), "第七境", font=f, fill="black")

    H = 400
    s2 = se.resize((int(se.size[0] * H / se.size[1]), H), Image.LANCZOS)
    t2 = txt.resize((int(txt.size[0] * H / txt.size[1]), H), Image.LANCZOS)
    gap = 46
    strip = Image.new("RGB", (s2.size[0] + gap + t2.size[0], H), "white")
    strip.paste(s2, (0, 0))
    strip.paste(t2, (s2.size[0] + gap, 0))
    # 等比缩放到安全区
    k = min(S * 0.86 / strip.size[0], S * 0.5 / strip.size[1])
    strip = strip.resize((int(strip.size[0] * k), int(strip.size[1] * k)), Image.LANCZOS)
    canvas = Image.new("RGB", (S, S), "white")
    canvas.paste(strip, ((S - strip.size[0]) // 2, (S - strip.size[1]) // 2))
    save(canvas, "D1-组合-印章加中文-黑白.jpg")
    made.append(("组合·黑白稿", "D1-组合-印章加中文-黑白.jpg"))
except Exception as e:
    print("  ! 组合图样生成失败：", e)

# 预览拼图（供人工快速核对，不是提交件）
try:
    files = sorted(f for f in os.listdir(OUT) if f.lower().endswith(".jpg") and not f.startswith("00"))
    cols = 3
    rows = (len(files) + cols - 1) // cols
    cell = 380
    sheet = Image.new("RGB", (cols*cell, rows*(cell+26)), "white")
    dd = ImageDraw.Draw(sheet)
    lf = load("宋体", 16)
    for i, f in enumerate(files):
        im = Image.open(os.path.join(OUT, f)).convert("RGB")
        im.thumbnail((cell-16, cell-16), Image.LANCZOS)
        cx, cy = (i % cols)*cell, (i // cols)*(cell+26)
        sheet.paste(im, (cx+8, cy+8))
        dd.text((cx+8, cy+cell-4), f, font=lf, fill="black")
    sheet.save(os.path.join(OUT, "00-预览-全部图样.jpg"), "JPEG", quality=88)
    print("  预览拼图：00-预览-全部图样.jpg")
except Exception as e:
    print("  ! 预览拼图失败：", e)

print("\n完成，共", len(made), "件图样")
for k, v in made:
    print(f"  {k:14s} {v}")
