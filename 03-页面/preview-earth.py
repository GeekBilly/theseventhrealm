#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v2 里的地球单独光栅化成 PNG，核对大陆形状与极冠（纯 PIL，不依赖浏览器）"""
import math
import re
import sys

from PIL import Image, ImageDraw

import importlib.util  # noqa: E402

sys.path.insert(0, "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面")
_spec = importlib.util.spec_from_file_location(
    "b", "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/build-cosmos-v2.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)   # 复用同一套投影/曲线逻辑


def sample(d, per=24):
    """解析 'M x y C ... A ...' 串 → 点列表"""
    toks = re.findall(r"[MCZAL]|-?[\d.]+", d)
    pts, i, cur = [], 0, None
    while i < len(toks):
        t = toks[i]
        if t == "M":
            cur = (float(toks[i + 1]), float(toks[i + 2]))
            pts.append([cur])
            i += 3
        elif t == "L":
            p = (float(toks[i + 1]), float(toks[i + 2]))
            pts[-1].append(p)
            cur = p
            i += 3
        elif t == "A":
            rx, ry = float(toks[i + 1]), float(toks[i + 2])
            sweep = int(toks[i + 5])
            end = (float(toks[i + 6]), float(toks[i + 7]))
            cx0, cy0 = B.CX, B.EY
            a0 = math.atan2(cur[1] - cy0, cur[0] - cx0)
            a1 = math.atan2(end[1] - cy0, end[0] - cx0)
            if sweep and a1 < a0:
                a1 += 2 * math.pi
            if not sweep and a1 > a0:
                a1 -= 2 * math.pi
            for k in range(per + 1):
                a = a0 + (a1 - a0) * k / per
                pts[-1].append((cx0 + rx * math.cos(a), cy0 + ry * math.sin(a)))
            cur = end
            i += 8
        elif t == "C":
            p1 = (float(toks[i + 1]), float(toks[i + 2]))
            p2 = (float(toks[i + 3]), float(toks[i + 4]))
            p3 = (float(toks[i + 5]), float(toks[i + 6]))
            for k in range(per + 1):
                u = k / per
                x = ((1 - u) ** 3 * cur[0] + 3 * (1 - u) ** 2 * u * p1[0]
                     + 3 * (1 - u) * u * u * p2[0] + u ** 3 * p3[0])
                y = ((1 - u) ** 3 * cur[1] + 3 * (1 - u) ** 2 * u * p1[1]
                     + 3 * (1 - u) * u * u * p2[1] + u ** 3 * p3[1])
                pts[-1].append((x, y))
            cur = p3
            i += 7
        else:
            i += 1
    return pts


S = 2.6
W = H = 300
off = 150  # 地球中心

img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
d = ImageDraw.Draw(img)

# 大气 + 海洋（与 SVG 的 seaG / airG 真实配色对齐）
d.ellipse([off - 126 * S / 2, off - 126 * S / 2, off + 126 * S / 2, off + 126 * S / 2],
          fill=(111, 182, 232, 78))
R = B.ER * S / 2
d.ellipse([off - R, off - R, off + R, off + R], fill=(47, 134, 201, 255))


def draw(dstr, fill, width=0):
    for seg in sample(dstr):
        p = [((x - 600) * S / 2 + off, (y - B.EY) * S / 2 + off) for x, y in seg]
        if len(p) > 2:
            if width:
                d.line(p, fill=fill, width=width, joint="curve")
            else:
                d.polygon(p, fill=fill)


# —— 陆/冰/云画在独立图层，最后用圆形 mask 裁掉球外部分（对应 SVG 的 clipPath）——
layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ld = ImageDraw.Draw(layer)
_save, d = d, ld

def hx(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


for k, v in B.LAND.items():
    dd = B.land_path(v)
    if dd:
        draw(dd, hx(B.LAND_FILL[k]))

draw(B.ice_d, (244, 250, 253, int(255 * 0.85)))
draw(B.ice_n, (244, 250, 253, int(255 * 0.62)))
for (lo, la, rl_, rt, op) in B.CLOUDS:
    if B.visible(lo, la):
        draw(B.cloud_blob(lo, la, rl_, rt), (255, 255, 255, int(255 * op)))

mask = Image.new("L", (W, H), 0)
ImageDraw.Draw(mask).ellipse([off - R, off - R, off + R, off + R], fill=255)
img = Image.alpha_composite(img, Image.composite(layer, Image.new("RGBA", (W, H), (0, 0, 0, 0)), mask))
d = ImageDraw.Draw(img)
d.ellipse([off - R, off - R, off + R, off + R], outline=(255, 255, 255, 55), width=2)

out = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/地球形态校验.png"
img.save(out)
print(out)
for k, v in B.LAND.items():
    dd = B.land_path(v)
    print(f"  {k:10s} {'有' if dd else '背面不可见（已剔除）'}")
