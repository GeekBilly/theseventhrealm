#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""竖幅版布局核对：把各幕的覆盖范围画在同一张 720×680 画布上，确认不溢出、比例协调。

输出 竖幅布局核对.png（三格：粒子幕 / 银河+太阳系 / 地球终态）
关键结论：iPhone 390px 宽下地球直径多少像素。
"""
import importlib.util
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面")
_sp = importlib.util.spec_from_file_location(
    "b", "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/build-cosmos-v2.py")
B = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(B)

T = B.GEO["tall"]
W, H, CX, CY, EY = T["W"], T["H"], T["CX"], T["CY"], T["EY"]
ER, R_OUT, PK, PS = T["ER"], T["R_OUT"], T["PK"], T["PS"]
GE = B.GAL_ELLIPSE

S = 0.62                                    # 缩到便于查看
cw, ch = int(W * S), int(H * S)
PAD, TOP = 26, 46
N = 3
W_IMG = PAD * 2 + N * cw + (N - 1) * 18
H_IMG = TOP + ch + 96

img = Image.new("RGB", (W_IMG, H_IMG), (250, 249, 246))
d = ImageDraw.Draw(img)


def font(sz):
    for p in ("/System/Library/Fonts/PingFang.ttc",
              "/System/Library/Fonts/Supplemental/Songti.ttc"):
        try:
            return ImageFont.truetype(p, sz, index=0)
        except Exception:
            continue
    return ImageFont.load_default()


F15, F13, F11 = font(15), font(13), font(11)
INK, CIN, DIM = (26, 26, 24), (176, 56, 38), (150, 145, 138)
SEA, LANDC = (47, 134, 201), (93, 138, 74)


def panel(i, title):
    ox = PAD + i * (cw + 18)
    d.rectangle([ox - 1, TOP - 1, ox + cw, TOP + ch], outline=(214, 209, 199))
    d.text((ox, TOP - 22), title, font=F15, fill=INK)
    return ox


def P(ox, x, y):
    return ox + x * S, TOP + y * S


# ── 格1 粒子幕（涨落 / 对称破缺 / 夸克） ──
ox = panel(0, "粒子幕（道·一·二·三）")
d.ellipse([*P(ox, CX - 215 * PK, CY - 215 * PK), *P(ox, CX + 215 * PK, CY + 215 * PK)],
          outline=(206, 201, 191))
for (x, y) in [(p[0], p[1]) for p in T["fluct"]]:
    px, py = P(ox, x, y)
    d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=INK)
for (dx, dy, _, _) in T["pairs"]:
    px, py = P(ox, CX + dx, CY + dy)
    d.ellipse([px - 2.5, py - 2.5, px + 2.5, py + 2.5], fill=CIN)
qoff, qr = T["quarks"]
for cxq in (CX - qoff, CX + qoff):
    d.ellipse([*P(ox, cxq - qr - 7, CY - qr - 7), *P(ox, cxq + qr + 7, CY + qr + 7)],
              outline=(206, 201, 191))

# ── 格2 银河 + 太阳系 ──
ox = panel(1, "银河系 + 太阳系（收小以放进 720 宽）")
d.ellipse([*P(ox, CX - R_OUT, CY - R_OUT * GE), *P(ox, CX + R_OUT, CY + R_OUT * GE)],
          outline=(160, 155, 145))
for (x, y, r, col) in T["stars"]:
    px, py = P(ox, CX + x, CY + y)
    rr = max(0.8, r * S * 1.6)
    d.ellipse([px - rr, py - rr, px + rr, py + rr],
              fill=(176, 56, 38) if col == B.CIN else (90, 88, 82))
for rx in T["planet_rx"]:
    d.ellipse([*P(ox, CX - rx, CY - rx * B.TILT), *P(ox, CX + rx, CY + rx * B.TILT)],
              outline=(200, 196, 188))
sx, sy = P(ox, T["SUN"][0], T["SUN"][1])
d.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=CIN)

# ── 格3 地球终态 ──
ox = panel(2, "地球终态（放大到画幅一半）")
ex, ey = P(ox, CX, EY)
R = ER * S
d.ellipse([ex - R * 1.37, ey - R * 1.37, ex + R * 1.37, ey + R * 1.37], fill=(196, 226, 240))
d.ellipse([ex - R, ey - R, ex + R, ey + R], fill=SEA)
# 用真实陆地 path 的包围盒近似（这里只核大小与位置，形态看 地球形态校验.png）
d.ellipse([ex - R * .8, ey - R * .5, ex + R * .9, ey + R * .55], fill=LANDC)
d.text((ex, ey), "地球", font=F13, fill=(255, 255, 255), anchor="mm")

# ── 结论行 ──
lines = [
    f"画幅 {W}×{H}（宽高比 {W / H:.2f}）  ← 旧版 1200×500（2.40）",
    f"地球直径 {ER * 2:.0f}px ＝ 画幅宽的 {ER * 2 / W:.0%}（旧版 {92 * 2 / 1200:.0%}）",
    f"iPhone 390px 宽下：地球直径 ≈ {ER * 2 * 390 / W:.0f}px（旧版 ≈ {92 * 2 * 390 / 1200:.0f}px）",
]
y = TOP + ch + 18
d.text((PAD, y), "竖幅版定标", font=F15, fill=INK)
for i, t in enumerate(lines):
    d.text((PAD, y + 24 + i * 20), t, font=F13, fill=CIN if i else DIM)

out = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/竖幅布局核对.png"
img.save(out)
print(out)
print("\n".join(lines))
