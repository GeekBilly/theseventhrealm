#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把银河系 / 太阳系单独光栅化，核对螺旋臂形态、星点密度、太阳位置。

用法：python3 preview-galaxy.py [wide|tall]   （默认 wide）
"""
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

MODE = sys.argv[1] if len(sys.argv) > 1 else "wide"
G = B.GEO[MODE]
CX, CY = G["CX"], G["CY"]
PS = G["PS"]

K = 1.6 if MODE == "wide" else 2.0
SCALE = K * (1200 / G["W"]) if MODE == "tall" else K      # 竖版按宽比放大到同一观感
W, H = int(G["W"] * SCALE), int(G["H"] * SCALE)


def T(x, y):
    return (x * SCALE, y * SCALE)


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
        d.line([T(*p) for p in pts], fill=color[:3] + (70,), width=int(width * SCALE),
               joint="curve")
        d.line([T(*p) for p in pts], fill=color[:3] + (110,), width=max(1, int(width * SCALE / 3)),
               joint="curve")


# ── 银河系 ──
img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
d = ImageDraw.Draw(img)
core_k = G["R_OUT"] / 285.0
d.ellipse([*T(CX - 46 * core_k, CY - 34 * core_k), *T(CX + 46 * core_k, CY + 34 * core_k)],
          fill=(26, 26, 24, 55))
d.ellipse([*T(CX - 22 * core_k, CY - 16 * core_k), *T(CX + 22 * core_k, CY + 16 * core_k)],
          fill=(26, 26, 24, 90))
for i, dp in enumerate(G["arm_paths"]):
    polyline(dp, (7 if i < 2 else 4.5) * G["PK"], (26, 26, 24, 255))
for (x, y, r, col) in G["stars"]:
    c = (176, 56, 38) if col == B.CIN else (26, 26, 24)
    px, py = T(CX + x, CY + y)
    rr = r * SCALE
    d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=c + (215,))
sx, sy = T(*G["SUN"])
d.ellipse([sx - 11 * G["PR"] * SCALE, sy - 11 * G["PR"] * SCALE,
           sx + 11 * G["PR"] * SCALE, sy + 11 * G["PR"] * SCALE], outline=(176, 56, 38, 200), width=2)
d.ellipse([sx - 2.6 * G["PR"] * SCALE, sy - 2.6 * G["PR"] * SCALE,
           sx + 2.6 * G["PR"] * SCALE, sy + 2.6 * G["PR"] * SCALE], fill=(176, 56, 38, 255))
out1 = f"/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/银河系形态校验-{MODE}.png"
img.save(out1)

# ── 太阳系 ──
img2 = Image.new("RGBA", (W, H), (255, 255, 255, 255))
d2 = ImageDraw.Draw(img2)
for (nm, rx0, pr0, col, a0) in B.PLANETS:
    rx, pr = rx0 * PS, pr0 * PS
    ry = rx * B.TILT
    d2.ellipse([*T(CX - rx, CY - ry), *T(CX + rx, CY + ry)], outline=(26, 26, 24, 90), width=1)
    x, y = CX + rx * math.cos(math.radians(a0)), CY + ry * math.sin(math.radians(a0))
    px, py = T(x, y)
    rr = max(1.6, pr * SCALE)
    rgb = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5))
    d2.ellipse([px - rr, py - rr, px + rr, py + rr], fill=rgb + (255,))
d2.ellipse([*T(CX - 34, CY - 34), *T(CX + 34, CY + 34)], fill=(216, 176, 114, 90))
d2.ellipse([*T(CX - 13, CY - 13), *T(CX + 13, CY + 13)], fill=(242, 230, 207, 255))
ex, ey = T(*G["EARTH"])
d2.ellipse([ex - 9 * SCALE, ey - 9 * SCALE, ex + 9 * SCALE, ey + 9 * SCALE],
           outline=(176, 56, 38, 230), width=2)
out2 = f"/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/太阳系形态校验-{MODE}.png"
img2.save(out2)

print(out1)
print(out2)
sd = math.hypot(G["SUN"][0] - CX, (G["SUN"][1] - CY) / B.GAL_ELLIPSE)
print(f"[{MODE}] 太阳距银心 {sd:.0f}px / 盘半径 {G['R_OUT']:.0f}px = {sd / G['R_OUT']:.0%}")
print(f"[{MODE}] 地球 {G['EARTH'][0]:.0f},{G['EARTH'][1]:.0f} | 画幅 {G['W']}×{G['H']} | "
      f"地球直径占比 {G['ER'] * 2 / G['W']:.0%}")
