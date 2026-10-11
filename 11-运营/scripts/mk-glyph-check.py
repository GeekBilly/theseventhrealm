#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字形核验图：确认「赜」左偏旁是「臣」不是「贝」

左＝系统字体权威结构（Songti SC）；中＝锁定结构的生成稿；
右＝做成印章后的放大（阴文白字）。三处并排，看结构是否一致。

用法：
    python3 mk-glyph-check.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

D = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/底纹"
REF = "/tmp/ref-tanze-songti.png"
SRC = os.path.join(D, "探赜书法-锁定B-行楷气势.png")
SEAL = os.path.join(D, "印章-探赜-v4cleanB-竖排.png")
FONT = "/System/Library/Fonts/Supplemental/Songti.ttc"
BG = (250, 248, 245)
INK = (26, 26, 24)
MUTED = (110, 104, 96)
RED = (158, 43, 37)

H = 380
PAD, GAP, TOP = 46, 56, 118


def load(path, as_ink=False, crop_char=False):
    im = Image.open(path).convert("RGBA")
    if crop_char:                       # 只取下半字「赜」
        im = im.crop((int(im.width * .04), int(im.height * .46),
                      int(im.width * .96), int(im.height * .99)))
    if as_ink:                          # 白底黑字 → 深底白字（用灰度反相当遮罩）
        from PIL import ImageChops
        a = ImageChops.invert(im.convert("L"))
        rgb = Image.new("RGB", im.size, (30, 26, 24))
        rgb.paste((245, 242, 236), mask=a)
        im = rgb.convert("RGBA")
    # 贴纸底
    base = Image.new("RGBA", (im.width + 16, im.height + 16), BG + (255,))
    base.alpha_composite(im, (8, 8))
    return base.resize((int(base.width * H / base.height), H), Image.LANCZOS)


items = [
    ("字体权威结构（宋体）", load(REF, as_ink=True, crop_char=True)),
    ("生成稿（锁定结构）", load(SRC, as_ink=True, crop_char=True)),
    ("做进印章（阴文白字）", load(SEAL, crop_char=True)),
]

W = PAD * 2 + sum(i[1].width for i in items) + GAP * (len(items) - 1)
Hc = TOP + H + 96
cv = Image.new("RGB", (W, Hc), BG)
d = ImageDraw.Draw(cv)
f_t = ImageFont.truetype(FONT, 30, index=0)
f_s = ImageFont.truetype(FONT, 17, index=0)
f_c = ImageFont.truetype(FONT, 22, index=0)

d.text((PAD, 26), "字形核验：「赜」字（左边偏旁必须写作「臣」）", font=f_t, fill=RED)
d.text((PAD, 64), "臣＝竖框内两横隔三格、底横向左伸出；贝＝底部有撇与点。三处结构一致即通过",
       font=f_s, fill=MUTED)

x = PAD
for tag, im in items:
    cv.paste(im.convert("RGB"), (x, TOP))
    d.text((x + im.width // 2, TOP + H + 18), tag, font=f_c, fill=INK, anchor="ma")
    x += im.width + GAP

p = os.path.join(D, "印章-探赜-v4字形核验.png")
cv.save(p)
print(p, cv.size)
