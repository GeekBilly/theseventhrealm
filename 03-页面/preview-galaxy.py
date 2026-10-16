#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v2 里的银河系 + 太阳系单独光栅化，核对螺旋臂形态、星点密度、太阳位置"""
import importlib.util
import math
import re
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面")
_spec = importlib.util.spec_from_file_location(
    "b", "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/build-cosmos-v2.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

K = 1.6                      # 缩放
W, H = int(1200 * K), int(500 * K)
img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
d = ImageDraw.Draw(img)


def T(x, y):
    return (x * K, y * K)


def polyline(dstr, width, color):
    toks = re.findall(r"[ML]|-?[\d.]+", dstr)
    pts, i = [], 0
    while i < len(toks):
        if toks[i] in "ML":
            pts.append((float(toks[i + 1]), float(toks[i + 2])))
            i += 3
        else:
            i += 1
    if len(pts) > 1:
        # 外宽淡、内窄浓，近似 stroke 渐变
        d.line([T(*p) for p in pts], fill=color[:3] + (70,), width=int(width * K),
               joint="curve")
        d.line([T(*p) for p in pts], fill=color[:3] + (110,), width=max(1, int(width * K / 3)),
               joint="curve")
    return pts


# 核球
d.ellipse([*T(B.CX - 46, B.CY - 34), *T(B.CX + 46, B.CY + 34)], fill=(26, 26, 24, 55))
d.ellipse([*T(B.CX - 22, B.CY - 16), *T(B.CX + 22, B.CY + 16)], fill=(26, 26, 24, 90))

for i, dp in enumerate(B.arm_paths):
    polyline(dp, 7 if i < 2 else 4.5, (26, 26, 24, 255))

for (x, y, r, col) in B.stars:
    c = (176, 56, 38) if col == B.CIN else (26, 26, 24)
    px, py = T(B.CX + x, B.CY + y)
    rr = r * K
    d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=c + (215,))

# 太阳标记
sx, sy = T(*B.SUN)
d.ellipse([sx - 11 * K, sy - 11 * K, sx + 11 * K, sy + 11 * K], outline=(176, 56, 38, 200), width=2)
d.ellipse([sx - 2.6 * K, sy - 2.6 * K, sx + 2.6 * K, sy + 2.6 * K], fill=(176, 56, 38, 255))

out1 = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/银河系形态校验.png"
img.save(out1)

# ── 太阳系 ──
img2 = Image.new("RGBA", (W, H), (255, 255, 255, 255))
d2 = ImageDraw.Draw(img2)
for (nm, rx, pr, col, a0) in B.PLANETS:
    ry = rx * B.TILT
    d2.ellipse([600 * K - rx * K, 250 * K - ry * K, 600 * K + rx * K, 250 * K + ry * K],
               outline=(26, 26, 24, 90), width=1)
    x, y = B.planet_pos(rx, ry, a0)
    px, py = T(x, y)
    rr = max(1.6, pr * K)
    rgb = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
    d2.ellipse([px - rr, py - rr, px + rr, py + rr], fill=rgb + (255,))
d2.ellipse([600 * K - 34 * K, 250 * K - 34 * K, 600 * K + 34 * K, 250 * K + 34 * K],
           fill=(216, 176, 114, 90))
d2.ellipse([600 * K - 13 * K, 250 * K - 13 * K, 600 * K + 13 * K, 250 * K + 13 * K],
           fill=(242, 230, 207, 255))
ex, ey = T(*B.EARTH)
d2.ellipse([ex - 9 * K, ey - 9 * K, ex + 9 * K, ey + 9 * K], outline=(176, 56, 38, 230), width=2)
for _ in range(16):
    pass

out2 = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/太阳系形态校验.png"
img2.save(out2)

print(out1)
print(out2)
print(f"太阳距银心 {math.hypot(B.SUN[0]-600, (B.SUN[1]-250)/B.GAL_ELLIPSE):.0f}px / 盘半径 {B.R_OUT:.0f}px "
      f"= {math.hypot(B.SUN[0]-600, (B.SUN[1]-250)/B.GAL_ELLIPSE)/B.R_OUT:.0%}")
print(f"地球 {B.EARTH[0]:.0f},{B.EARTH[1]:.0f} | zoom 位移 {B.TX_SOL[0]:.0f},{B.TX_SOL[1]:.0f}")
