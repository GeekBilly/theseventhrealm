#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把改前/改后两张「同视口同位置」截图拼成并排对比图。

截图由 shot-rhythm.py 生成（视口 1440×900，body 相对上移定位）。
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

A = pathlib.Path("/tmp/qjsp/shot-base-crop.png")
B = pathlib.Path("/tmp/qjsp/shot-new-crop.png")
OUT = pathlib.Path(__file__).resolve().parent / "全站间距-改前改后对比.png"


def font(sz):
    for p in ("/System/Library/Fonts/PingFang.ttc",
              "/System/Library/Fonts/Supplemental/Songti.ttc",
              "/System/Library/Fonts/Hiragino Sans GB.ttc"):
        try:
            return ImageFont.truetype(p, sz, index=0)
        except Exception:
            continue
    return ImageFont.load_default()


def main():
    a = Image.open(A).convert("RGB")
    b = Image.open(B).convert("RGB")
    W = 700
    h = int(a.height * W / a.width)
    a2 = a.resize((W, h), Image.LANCZOS)
    b2 = b.resize((W, h), Image.LANCZOS)

    PAD, TOP, GAP = 44, 104, 26
    cw = PAD * 2 + W * 2 + GAP
    canvas = Image.new("RGB", (cw, TOP + h + 96), (247, 246, 243))
    canvas.paste(a2, (PAD, TOP))
    canvas.paste(b2, (PAD + W + GAP, TOP))

    d = ImageDraw.Draw(canvas)
    ink, cin, grey = (26, 26, 24), (176, 56, 38), (107, 103, 95)
    x2 = PAD + W + GAP

    d.text((PAD, 22), "改 前", font=font(22), fill=ink)
    d.text((PAD + 66, 26), "相邻节空白 139px", font=font(15), fill=grey)
    d.text((x2, 22), "改 后", font=font(22), fill=cin)
    d.text((x2 + 66, 26), "相邻节空白 84px", font=font(15), fill=cin)

    d.text((PAD, 58), "三皇五帝页 · 三张藏品卡 → 终章金句 → 引用出处", font=font(13), fill=grey)
    d.text((x2, 58), "同一视口 1440×900 · 同一滚动位置 · 浏览器实测", font=font(13), fill=grey)

    d.rectangle([PAD, TOP, PAD + W, TOP + h], outline=(214, 210, 202), width=1)
    d.rectangle([x2, TOP, x2 + W, TOP + h], outline=(214, 210, 202), width=1)

    d.text((PAD, TOP + h + 16),
           "金句上方空白 197 → 104px　段落 14 → 20px　金句行框 82 → 63px",
           font=font(16), fill=ink)
    d.text((PAD, TOP + h + 46),
           "全站 43 页统一：相邻节 84px（桌面）／60px（手机）", font=font(13), fill=grey)

    canvas.save(OUT, quality=93)
    print("已出图", OUT.name, canvas.size)


if __name__ == "__main__":
    main()
