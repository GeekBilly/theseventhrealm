#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重出 B1 英文文字商标图样：THE SEVENTH REALM → TANTSE（2026-10-02）

复用 `gen_marks.py` 的 text_mark 逻辑（Times New Roman / 黑字白底 / 居中 / 自适应宽度）。
**只出 B1，不动 A / C / D 系列** —— 那 8 件是 2026-09-28 定稿的，重跑整脚本有改动风险。

英文名变更依据：`11-运营/风险管控/品牌命名-候选池-2026-10.md` 顶部终局区块。
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
OUT = os.path.join(ROOT, "11-运营/风险管控/商标证据/图样")
S = 1200                      # 与 gen_marks.py 一致（400–1500 区间内）
JPEG_Q = 92
TNR = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
SONG = ("/System/Library/Fonts/Supplemental/Songti.ttc", 0)


def text_mark(text, fname, size_ratio=0.30, stroke=1, lines=None):
    """纯文字商标图样（黑字白底、居中、无边框）"""
    img = Image.new("RGB", (S, S), "white")
    d = ImageDraw.Draw(img)
    parts = lines if lines else [text]
    fs = int(S * size_ratio)
    f = ImageFont.truetype(TNR, fs, index=0)
    while True:                                     # 自适应缩小以适配画布宽度
        boxes = [d.textbbox((0, 0), t, font=f, stroke_width=stroke) for t in parts]
        wmax = max(b[2] - b[0] for b in boxes)
        if wmax <= S * 0.86 or fs <= 40:
            break
        fs = int(fs * 0.95)
        f = ImageFont.truetype(TNR, fs, index=0)
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
    p = os.path.join(OUT, fname)
    img.save(p, "JPEG", quality=JPEG_Q, optimize=True)
    print(f"  {fname}\n    字号 {fs}px（占画布 {fs/S:.1%}）· {os.path.getsize(p)/1024:.0f}KB")
    return p


print("出 B1（TANTSE）→", OUT)
text_mark("TANTSE", "B1-文字-TANTSE-Times-黑白.jpg", size_ratio=0.30, stroke=1)

# ── 重建预览拼图（保持与 gen_marks.py 相同的版式）──
files = sorted(f for f in os.listdir(OUT)
               if f.lower().endswith(".jpg") and not f.startswith("00"))
cols, cell = 3, 380
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cell, rows * (cell + 26)), "white")
dd = ImageDraw.Draw(sheet)
lf = ImageFont.truetype(SONG[0], 16, index=SONG[1])
for i, f in enumerate(files):
    im = Image.open(os.path.join(OUT, f)).convert("RGB")
    im.thumbnail((cell - 16, cell - 16), Image.LANCZOS)
    cx, cy = (i % cols) * cell, (i // cols) * (cell + 26)
    sheet.paste(im, (cx + 8, cy + 8))
    dd.text((cx + 8, cy + cell - 4), f, font=lf, fill="black")
sheet.save(os.path.join(OUT, "00-预览-全部图样.jpg"), "JPEG", quality=88)
print(f"  预览已重建：{len(files)} 件")
for f in files:
    print(f"    {f}")
