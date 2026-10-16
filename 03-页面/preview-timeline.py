#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 build-cosmos-v2.py 的时间线画成甘特图：直接看幕与幕之间是硬切还是交叉溶解。

不依赖浏览器 —— 只按 TL / OFF 表算，所以图和片段一定同源。
输出 幕间交叉溶解时间轴.png
"""
import importlib.util
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面")
_sp = importlib.util.spec_from_file_location(
    "b", "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/build-cosmos-v2.py")
B = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(B)

TL, OFF, T_END = B.TL, B.OFF, B.T_END
IN, OUT = 1.2, 1.5

# 幕：(标签, 淡入起, 淡入完, 淡出起, 淡出完)
acts = [
    ("幕1 道 · 虚粒子涨落",   TL["fluct"][0], TL["fluct"][0] + IN, TL["fluct"][1], TL["fluct"][1] + OUT),
    ("幕2 一 · 暴胀",         TL["infl"][0] + .2, TL["infl"][0] + .2 + IN, TL["infl"][1], TL["infl"][1] + OUT),
    ("幕3 二 · 对称破缺",     TL["pairs"][0], TL["pairs"][0] + IN, TL["pairs"][1], TL["pairs"][1] + OUT),
    ("幕4 三 · 三夸克",       TL["quarks"][0], TL["quarks"][0] + IN, TL["quarks"][1], TL["quarks"][1] + OUT),
    ("幕5 万物 · 星点成银河", TL["gal"][0] + OFF["core_at"], TL["gal"][0] + OFF["core_at"] + OFF["core_dur"],
     TL["gal"][0] + OFF["gzoom_at"], TL["gal"][0] + OFF["gzoom_at"] + OFF["gzoom_dur"]),
    ("幕6 太阳系",            TL["solar"][0] + OFF["solin_at"], TL["solar"][0] + OFF["solin_at"] + OFF["solin_dur"],
     TL["solar"][0] + OFF["szoom_at"], TL["solar"][0] + OFF["szoom_at"] + OFF["szoom_dur"]),
    ("幕7 落点 · 地球",       TL["earth"][0] + OFF["earth_at"], TL["earth"][0] + OFF["earth_at"] + OFF["earth_dur"],
     None, None),
]
caps = [("道 · 真空不空…", 0.2), ("道生一 · 暴胀…", TL["infl"][0] + .4),
        ("一生二 · 对称破缺…", TL["pairs"][0] + .4), ("二生三 · 三夸克…", TL["quarks"][0] + .4),
        ("三生万物 · 第一批原子", TL["gal"][0] + .2), ("星辰聚为星系 · 银河系", TL["gal"][0] + OFF["sunmark_at"] + .4),
        ("银河一隅 · 太阳系", TL["solar"][0] + .8), ("地球 · 一切文明都在这里", TL["earth"][0] + .8)]
CAP_D, CAP_LAST = 4.6, 2.4

SCALE, LEFT, TOP, ROW, GAP = 30.0, 250, 96, 30, 11
W = int(LEFT + T_END * SCALE) + 40
H = TOP + len(acts) * (ROW + GAP) + 46 + len(caps) * 19 + 60

img = Image.new("RGB", (W, H), (250, 249, 246))
d = ImageDraw.Draw(img)


def font(sz, bold=False):
    for p in ("/System/Library/Fonts/PingFang.ttc",
              "/System/Library/Fonts/Supplemental/Songti.ttc",
              "/System/Library/Fonts/Hiragino Sans GB.ttc"):
        try:
            return ImageFont.truetype(p, sz, index=0)
        except Exception:
            continue
    return ImageFont.load_default()


F16, F13, F12 = font(16), font(13), font(12)
INK, CIN, DIM = (26, 26, 24), (176, 56, 38), (150, 145, 138)


def X(t):
    return LEFT + t * SCALE


def grad(y0, y1, t0, t1, up):
    """在 [t0,t1] 画一条 0↔1 的透明度渐变条（up=True 由浅到实）"""
    x0, x1 = int(X(t0)), int(X(t1))
    for x in range(x0, x1):
        k = (x - x0) / max(1, x1 - x0)
        a = k if up else 1 - k
        a = a * a * (3 - 2 * a)                      # ease
        col = tuple(int(250 + (c - 250) * a) for c in INK)
        d.rectangle([x, y0, x + 1, y1], fill=col)


# 时间网格
for s in range(0, int(T_END) + 1, 5):
    d.line([X(s), TOP - 24, X(s), H - 50], fill=(232, 228, 220))
    d.text((X(s), TOP - 44), f"{s}s", font=F13, fill=DIM, anchor="mm")

# 幕条
y = TOP
prev = None
for (name, i0, i1, o0, o1) in acts:
    d.text((LEFT - 16, y + ROW // 2), name, font=F16, fill=INK, anchor="rm")
    if o1 is None:                                   # 终态：不淡出
        d.rectangle([X(i0), y, X(i1), y + ROW], fill=(255, 255, 255))
        grad(y, y + ROW, i0, i1, True)
        d.rectangle([X(i1), y, X(T_END), y + ROW], fill=INK)
        d.text((X(T_END) - 8, y + ROW // 2), "终态（不淡出）", font=F12, fill=(250, 249, 246), anchor="rm")
    else:
        d.rectangle([X(i0), y, X(o1), y + ROW], fill=INK)
        grad(y, y + ROW, i0, i1, True)
        grad(y, y + ROW, o0, o1, False)
    if prev is not None:
        lo, hi = max(prev[2], i0), min(prev[3], i1)
        if hi > lo:                                  # 重叠区：斜纹标注
            for xx in range(int(X(lo)), int(X(hi)), 6):
                d.line([xx, y, xx + 6, y + ROW], fill=(250, 249, 246))
            d.text(((X(lo) + X(hi)) / 2, y - 4), f"{hi - lo:.2f}s 重叠", font=F12,
                   fill=CIN, anchor="ms")
    prev = (i0, i1, o0, o1)
    y += ROW + GAP

# 字幕轨
y += 10
d.text((LEFT - 16, y + 11), "字幕（淡入→保持→淡出）", font=F16, fill=INK, anchor="rm")
for (txt, t0) in caps:
    if txt.startswith("地球"):
        dur = CAP_LAST
        d.rectangle([X(t0), y, X(t0 + dur), y + 22], fill=(210, 205, 195))
        d.rectangle([X(t0), y, X(min(T_END, t0 + dur)), y + 22], fill=(196, 191, 181))
    else:
        d.rectangle([X(t0), y, X(t0 + CAP_D), y + 22], fill=(222, 218, 210))
        d.rectangle([X(t0 + CAP_D * .14), y, X(t0 + CAP_D * .74), y + 22], fill=(186, 181, 172))
    d.text((X(t0) + 6, y + 11), txt, font=F12, fill=(60, 58, 54), anchor="lm")
    y += 19

d.text((LEFT, H - 30), "斜纹区＝两幕同时可见（交叉溶解）；纯黑＝单幕满强度；灰白渐变＝淡入/淡出过程",
       font=F13, fill=DIM)
d.text((LEFT, H - 12), f"全片 {T_END}s｜幕间重叠 {', '.join(f'{o:.2f}s' for o in [0.9,1.1,1.2,0.7,0.8,0.7])}",
       font=F13, fill=CIN)

out = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/幕间交叉溶解时间轴.png"
img.save(out)
print(out)
print(f"{W}x{H}")
