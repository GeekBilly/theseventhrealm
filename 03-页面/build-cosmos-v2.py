#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 首页「宇宙演化」动画 v2.1 生成器（桌面宽幅 + 手机竖幅，一次生成拼进同一片段）

v1 → v2 的两处升级：
  1. 每一个圆点对应真实粒子行为（虚粒子涨落 / 暴胀 / 粒子-反粒子对与湮灭 /
     三夸克被胶子束缚成质子中子 / 原初核合成与原子形成）
  2. 「三生万物」落实为银河系 → 放大进入太阳系 → 落在地球

v2 → v2.1（2026-10-16 用户指示）：
  3. 删掉末幕「日 月 山 水 人 文」；地球回画面正中
  4. 地球改真实配色（蓝海 / 绿·黄绿陆 / 白冰冠 / 白云，对齐 🌍）
  5. 幕间交叉溶解（幕容器 --i/--o 淡入淡出，相邻幕重叠 0.7~1.2s）
  6. 整体放慢 26s → 43s

v2.1 竖幅：手机端地球直径只有约 57px，故为窄屏单独生成一套几何
  （银河盘 / 太阳系轨道收小，地球放大到占画幅近一半），两份 SVG 同处一个片段，
  用 max-width:760px 的媒体查询切换；不可见的那份用 animation:none 停掉，不占 CPU。

约束（线上可用 = 硬约束）：
  · 零 JavaScript：WP 区块/代码编辑器会剥脚本标签，只允许 SVG + CSS（SMIL 不算脚本）
  · 零外部图片：银河、太阳系、地球全部由脚本算出坐标后静态预渲染
  · 零 filter/blur：缩放时滤镜逐帧重算会掉帧，光晕一律用 radialGradient
  · 播完停终态、CPU 归零；支持 prefers-reduced-motion

用法：python3 build-cosmos-v2.py
  → 上线片段-首页宇宙演化动画-v2.html（含两套画幅，粘贴这一份即可）
  → 道境-首页-宇宙演化动画-v2-预览.html（本地预览，含手机视图 iframe）
"""

import math
import random
import re

INK = "#1a1a18"            # 墨
CIN = "#b03826"            # 朱砂

# ══════════ 时间线（秒）：每幕 [淡入起点, 淡出起点] ══════════
# 幕与幕之间刻意留 0.6~1.0s 重叠：上一幕淡出与下一幕淡入同时进行，避免硬切。
# 想整体加快/放慢，改这一张表即可（各元素 delay 全部由它派生）。
TL = {
    "fluct":  (0.0,  4.2),    # 幕1 道 · 真空涨落
    "infl":   (4.6,  9.6),    # 幕2 一 · 暴胀
    "pairs":  (10.0, 15.4),   # 幕3 二 · 对称破缺
    "quarks": (15.6, 21.0),   # 幕4 三 · 三夸克成质子中子
    "gal":    (21.4, 30.0),   # 幕5 万物 · 星点涌出成银河系
    "gzoom":  (27.4, 31.4),   # 幕6 推进 · 放大进入银河系
    "solar":  (30.6, 38.6),   # 幕7 太阳系
    "szoom":  (35.0, 39.4),   # 幕8 推进 · 以地球为原点放大
    "earth":  (38.8, 9999),   # 幕9 落点 · 地球（终态，不淡出）
}
# 幕内元素相对幕起点的偏移（秒）
OFF = {
    "fluct_pair": 0.15, "fluct_step": 0.16, "fluct_dur": 2.8,
    "infl_dur": 5.0, "ripple_at": [0.8, 2.0, 3.2], "ripple_dur": 3.6,
    "pair_at": 0.4, "pair_dur": 2.9, "flash_at": 2.15, "flash_dur": 1.1,
    "quark_at": 0.4, "quark_dur": 4.6, "nuc_at": 3.1, "nuc_dur": 1.9,
    "elec_at": 3.8, "elec_dur": 1.6,
    "core_at": 0.4, "core_dur": 2.4, "star_at": 0.5, "star_dur": 3.2,
    "arm_at": 1.4, "arm_dur": 4.4, "sunmark_at": 5.0, "sunmark_dur": 1.6,
    "gzoom_at": 6.2, "gzoom_dur": 4.0, "shrink_at": 6.4, "shrink_dur": 3.6,
    "solin_at": 0.2, "solin_dur": 3.0, "szoom_at": 4.6, "szoom_dur": 4.4,
    "earth_at": 0.1, "earth_dur": 4.2,
}
T_END = 43.2   # 全片播完（之后停终态、CPU 归零）

# ══════════ 两套画幅 ══════════
# PK 粒子幕缩放 ｜ PS 太阳系缩放 ｜ PR 粒子点半径缩放 ｜ EARTH0 地球入场起始 scale
# 竖幅的关键取舍：银河与太阳系收小以放得进 720 宽，地球反过来放大到直径 330
MODES = {
    "wide": dict(key="wide", cls="qjcos-sc-w", pfx="w", seed=20261016,
                 W=1200, H=500, CX=600.0, CY=250.0, EY=250.0,
                 R_OUT=285.0, PK=1.0, PS=1.0, PR=1.0, SUNVIS=1.0, ER=92.0, EARTH0=0.35),
    "tall": dict(key="tall", cls="qjcos-sc-t", pfx="t", seed=20261017,
                 W=720, H=680, CX=360.0, CY=340.0, EY=340.0,
                 R_OUT=270.0, PK=1.3, PS=0.75, PR=1.5, SUNVIS=0.8, ER=180.0, EARTH0=0.22),
}
BP = 760       # 窄屏断点（px）

# ══════════ 形状参数（两套画幅共用） ══════════
GAL_ELLIPSE = 0.62         # 盘面压扁（视觉倾角）
TURNS = 1.75
FORK_AT = 0.55             # 分叉臂自主臂 55% 处岔出
TILT = 0.30                # 太阳系轨道 ry/rx
LON0 = 60.0                # 地球中心经度：非洲+欧洲+亚洲+澳洲同框

PLANETS = [
    # name,    rx,   pr,  color,     a0°
    ("水", 66.0, 3.4, "#8d8579", 15),
    ("金", 95.0, 5.6, "#b09a72", 128),
    ("地", 128.0, 6.0, "#6f93a8", -32),
    ("火", 162.0, 4.4, "#b0705a", 74),
    ("木", 236.0, 9.6, "#bfa77e", -122),
    ("土", 292.0, 8.0, "#c9bfa0", 42),
    ("天", 348.0, 6.6, "#9fb4bd", -66),
    ("海", 400.0, 6.0, "#8ea3ad", 158),
]
SURVIVOR = 3               # 十亿分之一的物质残余

# 真实地球配色（v2.1）：陆地按气候带分色，不再是墨色剪影
LAND_FILL = {
    "eurasia": "#5d8a4a",     # 温带林绿
    "africa": "#94994f",      # 撒哈拉—萨凡纳（黄绿）
    "australia": "#a8915a",   # 内陆赭黄
    "madagascar": "#5f8c48",
    "indonesia": "#4e7f45",
    "borneo": "#4e7f45",
    "guinea": "#4e7f45",
    "japan": "#54834a",
    "greenland": "#e9f1f2",   # 格陵兰冰盖
}
LAND = {
    # 欧亚：伊比利亚 → 斯堪的纳维亚 → 西伯利亚 → 东南亚 → 中东 → 回伊比利亚
    "eurasia": [[-9, 37], [-9, 44], [1, 48], [8, 55], [16, 58], [22, 66], [32, 70],
                [48, 68], [64, 71], [82, 74], [100, 76], [122, 75], [144, 71],
                [162, 68], [172, 64], [168, 58], [155, 52], [143, 45], [134, 36],
                [124, 32], [120, 24], [110, 20], [104, 10], [99, 5], [96, 16],
                [88, 21], [78, 9], [72, 20], [64, 25], [57, 22], [54, 26],
                [46, 30], [42, 38], [36, 36], [30, 41], [24, 36], [18, 40],
                [14, 38], [3, 43], [-3, 43]],
    "africa": [[-17, 15], [-15, 22], [-9, 30], [0, 36], [11, 37], [20, 33], [32, 31],
               [35, 28], [43, 12], [51, 12], [42, -1], [40, -11], [35, -19], [32, -26],
               [26, -34], [18, -34], [13, -24], [12, -16], [9, -1], [9, 4], [3, 6],
               [-8, 4], [-13, 8]],
    "australia": [[114, -22], [126, -14], [138, -17], [148, -21], [154, -28],
                  [152, -38], [140, -38], [130, -33], [120, -34], [114, -30]],
    "madagascar": [[44, -12], [50, -16], [48, -25], [44, -22], [43, -17]],
    "indonesia": [[95, 6], [101, 1], [106, -6], [102, -6], [97, 2]],
    "borneo": [[109, 2], [117, 5], [119, -3], [110, -4]],
    "guinea": [[131, -1], [141, -3], [150, -9], [140, -10], [132, -4]],
    "japan": [[130, 31], [136, 34], [141, 41], [145, 44], [142, 36], [136, 34]],
    "greenland": [[-46, 60], [-30, 68], [-22, 74], [-40, 82], [-58, 78], [-56, 66]],
}
CLOUDS = [(-18, 14, 12, 4.5, .56), (-26, 48, 14, 5.5, .60), (14, 57, 16, 6, .54),
          (74, 47, 17, 6, .56), (4, -8, 13, 4.5, .52), (98, -12, 14, 4.5, .54),
          (32, -37, 15, 5.5, .52), (130, -27, 12, 4.5, .52), (148, 18, 11, 4.5, .54),
          (-6, -50, 17, 5.5, .52)]


GEO = {}          # scene() 会把各画幅的几何存到这里，供 preview-*.py 核对用


def n(v, k=1):
    s = f"{v:.{k}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def catmull(pts, closed=True):
    if len(pts) < 3:
        return ""
    P = pts[:]
    if closed:
        P = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        P = [pts[0]] + pts + [pts[-1]]
    d = f"M{n(P[1][0])} {n(P[1][1])}"
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        d += f" C{n(c1[0])} {n(c1[1])} {n(c2[0])} {n(c2[1])} {n(p2[0])} {n(p2[1])}"
    return d + (" Z" if closed else "")


def arm_points(theta0, r_in, r_out, turns, steps=130):
    b = math.log(r_out / r_in) / (turns * 2 * math.pi)
    pts = []
    for i in range(steps + 1):
        th = theta0 + turns * 2 * math.pi * i / steps
        r = r_in * math.exp(b * (th - theta0))
        pts.append((r * math.cos(th), r * math.sin(th) * GAL_ELLIPSE))
    return pts


def ell_path(cx, cy, rx, ry, a0):
    p = []
    steps = 72
    for i in range(steps + 1):
        a = math.radians(a0) + 2 * math.pi * i / steps
        p.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    # 起点必须落在 a0 上，animateMotion 从此处起跑
    return "M" + " L".join(f"{n(x)} {n(y)}" for x, y in p) + " Z"


def quark_group(cx, cy, r):
    out = []
    for k in range(3):
        a = math.radians(90 + k * 120)
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def gluon(cx, cy, pts, bow=13.0):
    d = ""
    for (px, py) in pts:
        mx, my = (cx + px) / 2, (cy + py) / 2
        nx, ny = -(py - cy), (px - cx)
        L = math.hypot(nx, ny) or 1
        nx, ny = nx / L * bow, ny / L * bow
        d += f"M{n(cx)} {n(cy)} Q{n(mx + nx)} {n(my + ny)} {n(px)} {n(py)} "
    return d.strip()


# ══════════════════════════════════════════════════════════════
#  一套画幅的完整场景（桌面 / 竖屏各调一次）
# ══════════════════════════════════════════════════════════════
def scene(cfg):
    W, H = cfg["W"], cfg["H"]
    CX, CY, EY = cfg["CX"], cfg["CY"], cfg["EY"]
    ER = cfg["ER"]
    R_OUT = cfg["R_OUT"]
    PK, PS, PR, SUNVIS = cfg["PK"], cfg["PS"], cfg["PR"], cfg["SUNVIS"]
    P = cfg["pfx"]                      # id 后缀：两套画幅的 defs id 不能重名
    random.seed(cfg["seed"])

    R_IN = R_OUT * 0.0421               # 与 wide 版 12/285 同比例
    RK = R_OUT / 285.0                  # 银河盘内尺寸比例（臂宽/星点散布/核球）
    B_SPIRAL = math.log(R_OUT / R_IN) / (TURNS * 2 * math.pi)

    # ── 银河系 ──
    _fork_r = R_IN * math.exp(B_SPIRAL * FORK_AT * TURNS * 2 * math.pi)
    _fork_t0 = math.radians(-58) + FORK_AT * TURNS * 2 * math.pi + 0.62
    ARMS = [
        dict(t0=math.radians(-58), rin=R_IN, rout=R_OUT, turns=TURNS, main=True),
        dict(t0=math.radians(122), rin=R_IN, rout=R_OUT, turns=TURNS, main=True),
        dict(t0=_fork_t0, rin=_fork_r, rout=R_OUT * 0.84, turns=TURNS * 0.60, main=False),
        dict(t0=_fork_t0 + math.pi, rin=_fork_r, rout=R_OUT * 0.84, turns=TURNS * 0.60, main=False),
    ]
    arm_paths, ARM_PTS = [], []
    for a in ARMS:
        pts = arm_points(a["t0"], a["rin"], a["rout"], a["turns"])
        ARM_PTS.append(pts)
        arm_paths.append("M" + " L".join(f"{n(CX + x)} {n(CY + y)}" for x, y in pts))

    # 太阳：落在第一条主臂约 0.55R 处（真实太阳在银河半径一半开外）
    _target = 0.55 * R_OUT
    sun_local = min(ARM_PTS[0], key=lambda p: abs(math.hypot(p[0], p[1] / GAL_ELLIPSE) - _target))
    SUN = (CX + sun_local[0], CY + sun_local[1])

    # 星点：沿弧长均匀取 r，再反解 θ（若按 θ 均匀取，密度会全挤进内圈）
    stars = []
    for ai, a in enumerate(ARMS):
        b = math.log(a["rout"] / a["rin"]) / (a["turns"] * 2 * math.pi)
        cnt = 58 if a["main"] else 20
        for _ in range(cnt):
            t = random.random()
            r = a["rin"] + (a["rout"] - a["rin"]) * t
            th = a["t0"] + math.log(r / a["rin"]) / b
            bx, by = r * math.cos(th), r * math.sin(th) * GAL_ELLIPSE
            r2 = min(a["rout"], r + 4.0 * RK)
            th2 = a["t0"] + math.log(r2 / a["rin"]) / b
            tx, ty = r2 * math.cos(th2) - bx, (r2 * math.sin(th2) - r * math.sin(th)) * GAL_ELLIPSE
            L = math.hypot(tx, ty) or 1
            nx, ny = -ty / L, tx / L
            off = random.gauss(0, (4.5 + 7.0 * t) * RK)
            along = random.gauss(0, 4.5 * RK)
            x = bx + nx * off + tx / L * along
            y = by + ny * off + ty / L * along
            if x * x + (y / GAL_ELLIPSE) ** 2 > (R_OUT * 1.04) ** 2:
                continue
            stars.append((x, y, round(random.uniform(0.85, 2.6) * PR * RK, 2),
                          CIN if random.random() < 0.055 else INK))
    for _ in range(60):                                  # 核球：密集球状分布
        rr = abs(random.gauss(0, 21 * RK))
        th = random.uniform(0, 2 * math.pi)
        stars.append((rr * math.cos(th), rr * math.sin(th) * GAL_ELLIPSE,
                      round(random.uniform(0.7, 1.9) * PR * RK, 2), INK))
    stars.sort(key=lambda s: s[2])

    # ── 太阳系 ──
    EARTH = None
    orbit_svg = planet_svg = belt_svg = ""
    _t_sol = TL["solar"][0]
    for i, (nm, rx0, pr0, col, a0) in enumerate(PLANETS):
        rx, pr = rx0 * PS, pr0 * PS
        ry = rx * TILT
        px, py = CX + rx * math.cos(math.radians(a0)), CY + ry * math.sin(math.radians(a0))
        if nm == "地":
            EARTH = (px, py)
        orbit_svg += (f'      <ellipse cx="{n(CX)}" cy="{n(CY)}" rx="{n(rx)}" ry="{n(ry)}" fill="none" '
                      f'stroke="{INK}" stroke-width=".7" opacity=".26"/>\n')
        orbit_svg += (f'      <path id="qjcos-orb{i}{P}" d="{ell_path(CX, CY, rx, ry, a0)}" '
                      f'fill="none" stroke="none"/>\n')
        # 地球做静止锚点：zoom 的缩放原点必须与实际位置严格一致，否则落点会跳。
        # 其余行星用 SMIL 缓慢公转；静止兜底靠 <set> 在 0.1s 后隐去，避免重影。
        spin = round(80 + i * 20, 1)
        if nm == "地":
            planet_svg += f'      <circle cx="{n(px)}" cy="{n(py)}" r="{n(pr)}" fill="{col}"/>\n'
        else:
            planet_svg += (
                f'      <circle r="{n(pr)}" fill="{col}">'
                f'<animateMotion dur="{spin}s" repeatCount="indefinite" begin="{n(_t_sol, 1)}s">'
                f'<mpath xlink:href="#qjcos-orb{i}{P}"/></animateMotion></circle>\n')
            if nm == "土":
                planet_svg += (f'      <g><ellipse rx="{n(pr * 1.9)}" ry="{n(pr * 0.62)}" fill="none" '
                               f'stroke="{col}" stroke-width="1.6" opacity=".55">'
                               f'<animateMotion dur="{spin}s" repeatCount="indefinite" begin="{n(_t_sol, 1)}s">'
                               f'<mpath xlink:href="#qjcos-orb{i}{P}"/></animateMotion></ellipse></g>\n')
            planet_svg += (f'      <circle cx="{n(px)}" cy="{n(py)}" r="{n(pr)}" fill="{col}" opacity=".55">'
                           f'<set attributeName="opacity" to="0" begin="0.1s" fill="freeze"/></circle>\n')
    for _ in range(16):
        a = random.uniform(0, 2 * math.pi)
        rr = random.uniform(178, 208) * PS
        belt_svg += (f'      <circle cx="{n(CX + rr * math.cos(a))}" cy="{n(CY + rr * TILT * math.sin(a))}" '
                     f'r="{round(random.uniform(0.6, 1.5) * PR, 2)}" fill="{INK}" opacity=".38"/>\n')

    TX_GAL = (CX - SUN[0], CY - SUN[1])           # 银河系 zoom：太阳 → 画面中心
    TX_SOL = (CX - EARTH[0], EY - EARTH[1])       # 太阳系 zoom：地球 → 落点

    # ── 地球：正交投影 + Catmull-Rom 平滑大陆 ──
    def proj(lon, lat):
        la, lo = math.radians(lat), math.radians(lon - LON0)
        return math.cos(la) * math.sin(lo) * ER, -math.sin(la) * ER

    def visible(lon, lat):
        la, lo = math.radians(lat), math.radians(lon - LON0)
        return math.cos(la) * math.cos(lo) > 0.02

    def land_path(raw):
        """只保留朝向镜头的一面，被地平面截断处直接闭合（视觉上即地平线）"""
        runs, cur = [], []
        for lon, lat in raw:
            if visible(lon, lat):
                cur.append(proj(lon, lat))
            else:
                if len(cur) >= 3:
                    runs.append(cur)
                cur = []
        if len(cur) >= 3:
            runs.append(cur)
        out = ""
        for seg in runs:
            out += catmull([(CX + x, EY + y) for x, y in seg]) + " "
        return out.strip()

    def polar_cap(lat, sweep):
        """极冠：正交投影下是球冠 —— 一条纬线（投影为水平弦）+ 一段大圆弧"""
        y = -math.sin(math.radians(lat)) * ER
        half = math.cos(math.radians(lat)) * ER
        ax, bx = CX - half, CX + half
        ay = by = EY + y
        return (f"M{n(ax)} {n(ay)} L{n(bx)} {n(by)} "
                f"A{n(ER)} {n(ER)} 0 0 {sweep} {n(ax)} {n(ay)} Z")

    def cloud_blob(lon, lat, rlon, rlat):
        pts = []
        for i in range(14):
            t = 2 * math.pi * i / 14
            w = 1 + 0.20 * math.sin(3 * t + math.radians(lon)) + 0.10 * math.sin(5 * t)
            x, y = proj(lon + rlon * w * math.cos(t), lat + rlat * w * math.sin(t))
            pts.append((CX + x, EY + y))
        return catmull(pts)

    ice_d = polar_cap(-58, 1)   # 南极冰盖
    ice_n = polar_cap(62, 0)    # 北极浮冰
    land_svg = "\n".join(
        f'        <path d="{d}" fill="{LAND_FILL[k]}"/>'
        for k, v, d in [(k, v, land_path(v)) for k, v in LAND.items()] if d
    )
    cloud_svg = "\n".join(
        f'        <path d="{cloud_blob(lo, la, rl, rt)}" fill="#ffffff" opacity="{op}"/>'
        for (lo, la, rl, rt, op) in CLOUDS if visible(lo, la)
    )

    # ── 幕1 量子涨落：10 对虚粒子 ──
    fluct = []
    for i in range(10):
        a = random.uniform(0, 2 * math.pi)
        d = random.uniform(30, 175) * PK
        fluct.append((CX + math.cos(a) * d * 0.55, CY + math.sin(a) * d,
                      round(random.uniform(1.1, 2.2) * PR, 2)))
    _t_fl = TL["fluct"][0]
    fluct_svg = "\n".join(
        f'      <g class="qjcos-fluctpair" style="animation-delay:{round(_t_fl + OFF["fluct_pair"] + i * OFF["fluct_step"], 2)}s;'
        f'animation-duration:{OFF["fluct_dur"]}s">'
        f'<circle cx="{n(x)}" cy="{n(y)}" r="{r}" fill="{INK}" style="--px:{n(-5.5 * PK)}px;--py:{n(-9.5 * PK)}px"/>'
        f'<circle cx="{n(x)}" cy="{n(y)}" r="{r}" fill="none" stroke="{INK}" stroke-width=".9" '
        f'style="--px:{n(5.5 * PK)}px;--py:{n(9.5 * PK)}px"/></g>'
        for i, (x, y, r) in enumerate(fluct)
    )

    # ── 幕3 对称破缺：8 对粒子-反粒子，1 对幸存 ──
    PAIRS = []
    for i in range(8):
        a = (i / 8.0) * 2 * math.pi + 0.42
        d = random.uniform(72, 168) * PK
        PAIRS.append((math.cos(a) * d, math.sin(a) * d * 0.72,
                      round(random.uniform(0, 0.62), 2), i))
    pair_svg = ""
    for (dx, dy, dl, i) in PAIRS:
        t = round(TL["pairs"][0] + OFF["pair_at"] + dl, 2)
        survive = (i == SURVIVOR)
        pair_svg += (
            f'      <g>'
            f'<circle class="qjcos-par qjcos-{"surv" if survive else "mat"}" cx="{n(CX)}" cy="{n(CY)}" r="{n(3.1 * PR)}" '
            f'fill="{INK}" opacity="0" style="--dx:{n(dx)}px;--dy:{n(dy)}px;'
            f'animation-delay:{t}s;animation-duration:{OFF["pair_dur"]}s"/>'
            f'<circle class="qjcos-par qjcos-anti" cx="{n(CX)}" cy="{n(CY)}" r="{n(3.1 * PR)}" fill="none" '
            f'stroke="{INK}" stroke-width="1" opacity="0" '
            f'style="--dx:{n(-dx * 0.86)}px;--dy:{n(-dy * 0.86)}px;'
            f'animation-delay:{t}s;animation-duration:{OFF["pair_dur"]}s"/>'
            + ("" if survive else
               f'<circle class="qjcos-flash" cx="{n(CX + dx)}" cy="{n(CY + dy)}" r="{n(2.4 * PR)}" fill="{CIN}" '
               f'opacity="0" style="animation-delay:{round(t + OFF["flash_at"], 2)}s;'
               f'animation-duration:{OFF["flash_dur"]}s"/>')
            + f'</g>\n'
        )

    # ── 幕4 三夸克：质子 uud / 中子 udd ──
    QOFF, QR = 66.0 * PK, 23.0 * PK
    QP = quark_group(CX - QOFF, CY, QR)
    QN = quark_group(CX + QOFF, CY, QR)
    qp_svg = "".join(
        f'<circle cx="{n(p[0])}" cy="{n(p[1])}" r="{n(7.4 * PR)}" fill="{CIN if k < 2 else INK}"/>'
        for k, p in enumerate(QP))
    qn_svg = "".join(
        f'<circle cx="{n(p[0])}" cy="{n(p[1])}" r="{n(7.4 * PR)}" fill="{CIN if k < 1 else INK}"/>'
        for k, p in enumerate(QN))

    # ── 幕5 星点 ──
    _t_gal = TL["gal"][0]
    star_svg = "\n".join(
        f'      <circle class="qjcos-par" cx="{n(CX)}" cy="{n(CY)}" r="{s[2]}" fill="{s[3]}" opacity="0" '
        f'style="--dx:{n(s[0])}px;--dy:{n(s[1])}px;'
        f'animation-delay:{round(_t_gal + OFF["star_at"] + random.random() * 1.6, 2)}s;'
        f'animation-duration:{OFF["star_dur"]}s"/>'
        for s in stars
    )
    arms_svg = "\n".join(
        f'      <path class="qjcos-arm" d="{d}" pathLength="1000" fill="none" stroke="url(#qjcos-armG{P})" '
        f'stroke-width="{7 * RK if i < 2 else 4.5 * RK}" stroke-linecap="round"/>'
        for i, d in enumerate(arm_paths)
    )

    sunr_out, sunr_in = 46.0 * SUNVIS, 13.0 * SUNVIS
    galcore_rx, galcore_ry = 60.0 * RK, 44.0 * RK
    air_r = ER * 1.37

    # 导出几何供预览脚本核对（不进上线片段）
    GEO[cfg["key"]] = dict(W=W, H=H, CX=CX, CY=CY, EY=EY, ER=ER, R_OUT=R_OUT,
                           PK=PK, PS=PS, PR=PR, SUN=SUN, EARTH=EARTH,
                           stars=stars, arm_paths=arm_paths,
                           fluct=fluct, pairs=PAIRS, quarks=(QOFF, QR),
                           sun_r=sunr_out, planet_rx=[r * PS for _, r, _, _, _ in PLANETS],
                           ice_d=ice_d, ice_n=ice_n, land_svg=land_svg, cloud_svg=cloud_svg,
                           land_d={k: land_path(v) for k, v in LAND.items()},
                           cloud_list=[(cloud_blob(lo, la, rl, rt), op)
                                       for (lo, la, rl, rt, op) in CLOUDS if visible(lo, la)])

    return f'''    <svg class="qjcos-scene {cfg["cls"]}" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice"
         style="--ox:{n(CX)}px;--oy:{n(CY)}px" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true">
      <defs>
        <radialGradient id="qjcos-mistG{P}" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="{INK}" stop-opacity=".30"/>
          <stop offset="45%" stop-color="{INK}" stop-opacity=".13"/>
          <stop offset="100%" stop-color="{INK}" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="qjcos-coreG{P}" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="{INK}" stop-opacity="1"/>
          <stop offset="60%" stop-color="{INK}" stop-opacity=".9"/>
          <stop offset="100%" stop-color="{INK}" stop-opacity="0"/>
        </radialGradient>
        <!-- ⚠️ 用在 <path> 上的渐变必须 userSpaceOnUse，否则会按每条臂各自的包围盒取渐变 -->
        <radialGradient id="qjcos-armG{P}" gradientUnits="userSpaceOnUse"
                        cx="{n(CX)}" cy="{n(CY)}" r="{n(R_OUT)}">
          <stop offset="0%" stop-color="{INK}" stop-opacity=".62"/>
          <stop offset="45%" stop-color="{INK}" stop-opacity=".30"/>
          <stop offset="100%" stop-color="{INK}" stop-opacity=".06"/>
        </radialGradient>
        <radialGradient id="qjcos-galcoreG{P}" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="{INK}" stop-opacity=".85"/>
          <stop offset="52%" stop-color="{INK}" stop-opacity=".34"/>
          <stop offset="100%" stop-color="{INK}" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="qjcos-sunG{P}" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#f2e6cf" stop-opacity="1"/>
          <stop offset="42%" stop-color="#d8b072" stop-opacity=".85"/>
          <stop offset="100%" stop-color="#c8863c" stop-opacity="0"/>
        </radialGradient>
        <!-- 真实海洋色：向阳面浅蓝 → 边缘深蓝（🌍 而非墨色星球） -->
        <radialGradient id="qjcos-seaG{P}" cx="34%" cy="28%" r="78%">
          <stop offset="0%" stop-color="#7cc5ec"/>
          <stop offset="48%" stop-color="#2f86c9"/>
          <stop offset="100%" stop-color="#134a86"/>
        </radialGradient>
        <radialGradient id="qjcos-hiG{P}" cx="30%" cy="24%" r="62%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity=".26"/>
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="qjcos-shG{P}" cx="74%" cy="78%" r="66%">
          <stop offset="0%" stop-color="#05263f" stop-opacity=".32"/>
          <stop offset="100%" stop-color="#05263f" stop-opacity="0"/>
        </radialGradient>
        <radialGradient id="qjcos-airG{P}" cx="50%" cy="50%" r="50%">
          <stop offset="62%" stop-color="#6fb6e8" stop-opacity="0"/>
          <stop offset="80%" stop-color="#6fb6e8" stop-opacity=".34"/>
          <stop offset="100%" stop-color="#6fb6e8" stop-opacity="0"/>
        </radialGradient>
        <clipPath id="qjcos-earthClip{P}"><circle cx="{n(CX)}" cy="{n(EY)}" r="{n(ER)}"/></clipPath>
      </defs>

      <!-- ── 幕1 道 · 真空涨落 ── -->
      <g class="qjcos-st qjcos-mist"><circle cx="{n(CX)}" cy="{n(CY)}" r="{n(215 * PK)}" fill="url(#qjcos-mistG{P})"/></g>
      <g class="qjcos-flucts qjcos-sc" style="--i:{n(TL["fluct"][0])}s;--o:{n(TL["fluct"][1])}s">
{fluct_svg}
      </g>

      <!-- ── 幕2 一 · 暴胀 ── -->
      <g class="qjcos-st qjcos-infl"><circle cx="{n(CX)}" cy="{n(CY)}" r="{n(78 * PK)}" fill="url(#qjcos-coreG{P})"/></g>
      <g class="qjcos-ripples qjcos-sc" style="--i:{n(TL["infl"][0] + .2)}s;--o:{n(TL["infl"][1])}s">
        <circle class="qjcos-par qjcos-ripple" cx="{n(CX)}" cy="{n(CY)}" r="{n(52 * PK)}" fill="none" stroke="{INK}" stroke-width="1" opacity="0" style="animation-delay:{n(TL["infl"][0] + OFF["ripple_at"][0])}s"/>
        <circle class="qjcos-par qjcos-ripple" cx="{n(CX)}" cy="{n(CY)}" r="{n(52 * PK)}" fill="none" stroke="{INK}" stroke-width="1" opacity="0" style="animation-delay:{n(TL["infl"][0] + OFF["ripple_at"][1])}s"/>
        <circle class="qjcos-par qjcos-ripple" cx="{n(CX)}" cy="{n(CY)}" r="{n(52 * PK)}" fill="none" stroke="{INK}" stroke-width="1" opacity="0" style="animation-delay:{n(TL["infl"][0] + OFF["ripple_at"][2])}s"/>
      </g>

      <!-- ── 幕3 二 · 对称破缺：成对而生，湮灭，留下微量物质 ── -->
      <g class="qjcos-pairs qjcos-sc" style="--i:{n(TL["pairs"][0])}s;--o:{n(TL["pairs"][1])}s">
{pair_svg}      </g>

      <!-- ── 幕4 三 · 三夸克被胶子束缚 ── -->
      <g class="qjcos-quarks qjcos-sc" style="--i:{n(TL["quarks"][0])}s;--o:{n(TL["quarks"][1])}s">
        <g class="qjcos-st qjcos-quarkp">
          <path d="{gluon(CX - QOFF, CY, QP, 13.0 * PK)}" fill="none" stroke="{INK}" stroke-width=".9" opacity=".38"/>
{qp_svg}
          <text x="{n(CX - QOFF)}" y="{n(CY + 42 * PK)}" font-size="{n(12 * max(1.0, PR))}" fill="{INK}" opacity=".7" text-anchor="middle" font-family="serif">p</text>
        </g>
        <g class="qjcos-st qjcos-quarkn">
          <path d="{gluon(CX + QOFF, CY, QN, 13.0 * PK)}" fill="none" stroke="{INK}" stroke-width=".9" opacity=".38"/>
{qn_svg}
          <text x="{n(CX + QOFF)}" y="{n(CY + 42 * PK)}" font-size="{n(12 * max(1.0, PR))}" fill="{INK}" opacity=".7" text-anchor="middle" font-family="serif">n</text>
        </g>
        <g class="qjcos-st qjcos-nucleus">
          <circle cx="{n(CX)}" cy="{n(CY)}" r="{n(27 * PK)}" fill="none" stroke="{INK}" stroke-width=".9" opacity=".45"/>
          <text x="{n(CX)}" y="{n(CY + 46 * PK)}" font-size="{n(11 * max(1.0, PR))}" fill="{INK}" opacity=".6" text-anchor="middle" font-family="serif">原子核</text>
        </g>
        <circle class="qjcos-par qjcos-elec" cx="{n(CX)}" cy="{n(CY)}" r="{n(2.1 * PR)}" fill="{INK}" opacity="0" style="--dx:0px;--dy:0px;animation-delay:{n(TL["quarks"][0] + OFF["elec_at"])}s;animation-duration:{OFF["elec_dur"]}s"/>
      </g>

      <!-- ── 幕5~6 万物 · 银河系成形并推进 ── -->
      <g class="qjcos-gal qjcos-zoom qjcos-galzoom" style="--tx:{n(TX_GAL[0])}px;--ty:{n(TX_GAL[1])}px;transform-origin:{n(SUN[0])}px {n(SUN[1])}px">
        <g class="qjcos-st qjcos-galcore">
          <ellipse cx="{n(CX)}" cy="{n(CY)}" rx="{n(galcore_rx)}" ry="{n(galcore_ry)}" fill="url(#qjcos-galcoreG{P})"/>
        </g>
        <g>
{arms_svg}
        </g>
        <g class="qjcos-starshrink">
{star_svg}
        </g>
        <g class="qjcos-st qjcos-sunmark">
          <circle cx="{n(SUN[0])}" cy="{n(SUN[1])}" r="{n(2.6 * PR * RK)}" fill="{CIN}"/>
          <circle cx="{n(SUN[0])}" cy="{n(SUN[1])}" r="{n(11 * PR * RK)}" fill="none" stroke="{CIN}" stroke-width="1" opacity=".7"/>
        </g>
      </g>

      <!-- ── 幕7 太阳系 ── -->
      <g class="qjcos-solar qjcos-zoom qjcos-solzoom" style="--tx:{n(TX_SOL[0])}px;--ty:{n(TX_SOL[1])}px;transform-origin:{n(EARTH[0])}px {n(EARTH[1])}px">
        <g class="qjcos-st qjcos-solin">
          <circle cx="{n(CX)}" cy="{n(CY)}" r="{n(sunr_out)}" fill="url(#qjcos-sunG{P})" opacity=".55"/>
          <circle cx="{n(CX)}" cy="{n(CY)}" r="{n(sunr_in)}" fill="url(#qjcos-sunG{P})"/>
{orbit_svg}{belt_svg}{planet_svg}
        </g>
      </g>

      <!-- ── 幕8~9 落点 · 地球 ── -->
      <g class="qjcos-st qjcos-earth" style="transform-origin:{n(CX)}px {n(EY)}px">
        <circle cx="{n(CX)}" cy="{n(EY)}" r="{n(air_r)}" fill="url(#qjcos-airG{P})"/>
        <circle cx="{n(CX)}" cy="{n(EY)}" r="{n(ER)}" fill="url(#qjcos-seaG{P})"/>
        <g clip-path="url(#qjcos-earthClip{P})">
{land_svg}
          <path d="{ice_d}" fill="#f4fafd" opacity=".85"/>
          <path d="{ice_n}" fill="#f4fafd" opacity=".62"/>
{cloud_svg}
        </g>
        <circle cx="{n(CX)}" cy="{n(EY)}" r="{n(ER)}" fill="url(#qjcos-shG{P})"/>
        <circle cx="{n(CX)}" cy="{n(EY)}" r="{n(ER)}" fill="url(#qjcos-hiG{P})"/>
        <ellipse cx="{n(CX)}" cy="{n(EY)}" rx="{n(ER)}" ry="{n(ER * 0.34)}" fill="none" stroke="#ffffff" stroke-width=".7" opacity=".12"/>
        <ellipse cx="{n(CX)}" cy="{n(EY)}" rx="{n(ER * 0.42)}" ry="{n(ER)}" fill="none" stroke="#ffffff" stroke-width=".7" opacity=".10"/>
      </g>
    </svg>''', dict(stars=len(stars), SUN=SUN, EARTH=EARTH, TX_GAL=TX_GAL, TX_SOL=TX_SOL)


# ══════════════════════════════════════════════════════════════
#  共享 CSS（两套画幅共用；几何相关的原点用 --ox/--oy 由各 SVG 自带）
# ══════════════════════════════════════════════════════════════
_tall_cfg = MODES["tall"]
CSS = f"""
.qjcos-hero{{position:relative;width:100%;max-width:1200px;aspect-ratio:{MODES["wide"]["W"]}/{MODES["wide"]["H"]};margin:0 auto;overflow:hidden}}
.qjcos-scene{{position:absolute;inset:0;width:100%;height:100%;display:block}}
.qjcos-sc-t{{display:none}}
.qjcos-st{{opacity:0;transform-box:view-box;transform-origin:var(--ox) var(--oy)}}
.qjcos-zoom{{transform-box:view-box}}
.qjcos-par{{opacity:0;transform-box:fill-box;transform-origin:center}}
.qjcos-sc{{opacity:0}}
.qjcos-arm{{stroke-dasharray:1000;stroke-dashoffset:1000}}
.qjcos-cap{{position:absolute;left:0;right:0;bottom:22px;text-align:center;font-size:13px;letter-spacing:.30em;color:#a39d92;opacity:0}}
.qjcos-stmt{{max-width:1200px;margin:8px auto 0;padding:54px 24px 0;text-align:center;border-top:1px solid #e6e2d8;opacity:0}}
.qjcos-lead{{font-family:'Ma Shan Zheng','Xingkai SC','STXingkai','KaiTi','STKaiti',serif;font-size:clamp(24px,3.6vw,44px);line-height:1.7;color:#1a1a18;letter-spacing:.10em}}
.qjcos-note{{margin-top:18px;max-width:640px;margin-left:auto;margin-right:auto;font-size:13px;letter-spacing:.10em;color:#6b675f;line-height:2.1}}
.qjcos-acts{{margin-top:30px;display:flex;gap:16px;justify-content:center;flex-wrap:wrap}}
.qjcos-acts a{{display:inline-block;padding:14px 32px;border-radius:2px;font-size:15px;letter-spacing:.16em;text-decoration:none;transition:.25s}}
.qjcos-acts .p{{background:#b03826;color:#fff}}
.qjcos-acts .p:hover{{background:#1a1a18}}
.qjcos-acts .s{{border:1px solid #a39d92;color:#6b675f}}
.qjcos-acts .s:hover{{border-color:#1a1a18;color:#1a1a18}}

/* 窄屏切竖幅：银河与太阳系收小、地球放大到画幅近一半 */
@media (max-width:{BP}px){{
  .qjcos-hero{{aspect-ratio:{_tall_cfg["W"]}/{_tall_cfg["H"]};max-width:560px}}
  .qjcos-sc-w{{display:none}}
  .qjcos-sc-t{{display:block}}
  .qjcos-cap{{font-size:12px;letter-spacing:.22em}}
}}
/* 不可见的那份停掉动画，别白占 CPU（SMIL 的 7 颗行星开销可忽略） */
@media (min-width:{BP + 1}px){{.qjcos-sc-t *{{animation:none !important}}}}
@media (max-width:{BP}px){{.qjcos-sc-w *{{animation:none !important}}}}

@media (prefers-reduced-motion:no-preference){{
  /* 基础：先写通用动画，后面的类再做覆盖（同优先级，后者胜） */
  .qjcos-st{{animation:qjcos-fade 1.4s ease forwards}}
  .qjcos-par{{animation:qjcos-burst 2.7s cubic-bezier(.16,.84,.3,1) forwards}}
  .qjcos-cap{{animation:qjcos-capshow 4.6s ease forwards}}
  /* 幕容器统一淡入淡出：--i 淡入起点 / --o 淡出起点，幕间留重叠做交叉溶解 */
  .qjcos-sc{{animation:qjcos-scin 1.2s ease forwards var(--i,0s),
             qjcos-scout 1.5s ease forwards var(--o,9999s)}}
  /* 幕1 道 · 真空涨落 */
  .qjcos-mist{{animation:qjcos-mistflow {OFF["fluct_dur"] + 2.8}s ease both {n(TL["fluct"][0])}s,
               qjcos-scout 1.5s ease forwards {n(TL["fluct"][1])}s}}
  .qjcos-fluctpair{{animation:qjcos-fluct {OFF["fluct_dur"]}s ease-in-out both}}
  /* 幕2 一 · 暴胀 */
  .qjcos-infl{{animation:qjcos-infl {OFF["infl_dur"]}s ease both {n(TL["infl"][0])}s,
               qjcos-scout 1.5s ease forwards {n(TL["infl"][1])}s}}
  .qjcos-ripple{{animation:qjcos-ripple {OFF["ripple_dur"]}s ease-out both}}
  /* 幕3 二 · 对称破缺 */
  .qjcos-mat{{animation-name:qjcos-pairfly;animation-duration:{OFF["pair_dur"]}s}}
  .qjcos-anti{{animation-name:qjcos-pairfly;animation-duration:{OFF["pair_dur"]}s}}
  .qjcos-surv{{animation:qjcos-pairsurv {OFF["pair_dur"]}s cubic-bezier(.16,.84,.3,1) forwards}}
  .qjcos-flash{{animation:qjcos-flash {OFF["flash_dur"]}s ease-out both}}
  /* 幕4 三 · 三夸克成质子中子（退场交给幕容器淡出，不再单独 lateout） */
  .qjcos-quarkp{{animation:qjcos-quarkp {OFF["quark_dur"]}s cubic-bezier(.2,.7,.4,1) both {n(TL["quarks"][0] + OFF["quark_at"])}s}}
  .qjcos-quarkn{{animation:qjcos-quarkn {OFF["quark_dur"]}s cubic-bezier(.2,.7,.4,1) both {n(TL["quarks"][0] + OFF["quark_at"])}s}}
  .qjcos-nucleus{{animation:qjcos-grow {OFF["nuc_dur"]}s ease both {n(TL["quarks"][0] + OFF["nuc_at"])}s}}
  .qjcos-elec{{animation:qjcos-burst {OFF["elec_dur"]}s ease both {n(TL["quarks"][0] + OFF["elec_at"])}s}}
  /* 幕5 万物 · 星点涌出成银河系 */
  .qjcos-arm{{animation:qjcos-draw {OFF["arm_dur"]}s ease-out both;animation-delay:{n(TL["gal"][0] + OFF["arm_at"])}s}}
  .qjcos-galcore{{animation-delay:{n(TL["gal"][0] + OFF["core_at"])}s;animation-duration:{OFF["core_dur"]}s}}
  /* 幕6 推进 · 以太阳为原点放大 */
  .qjcos-galzoom{{animation:qjcos-galzoom {OFF["gzoom_dur"]}s cubic-bezier(.55,.02,.42,1) both;animation-delay:{n(TL["gal"][0] + OFF["gzoom_at"])}s}}
  .qjcos-starshrink{{animation:qjcos-shrink {OFF["shrink_dur"]}s ease-in both;animation-delay:{n(TL["gal"][0] + OFF["shrink_at"])}s}}
  .qjcos-sunmark{{animation-delay:{n(TL["gal"][0] + OFF["sunmark_at"])}s;animation-duration:{OFF["sunmark_dur"]}s}}
  /* 幕7 太阳系 */
  .qjcos-solin{{animation-delay:{n(TL["solar"][0] + OFF["solin_at"])}s;animation-duration:{OFF["solin_dur"]}s;animation-name:qjcos-solin}}
  /* 幕8 推进 · 以地球为原点放大 */
  .qjcos-solzoom{{animation:qjcos-solzoom {OFF["szoom_dur"]}s cubic-bezier(.55,.02,.42,1) both;animation-delay:{n(TL["solar"][0] + OFF["szoom_at"])}s}}
  /* 幕9 落点 · 地球 */
  .qjcos-earth{{animation-delay:{n(TL["earth"][0] + OFF["earth_at"])}s;animation-duration:{OFF["earth_dur"]}s;animation-name:qjcos-earthrise}}
  .qjcap-c1{{animation-delay:.2s}}  .qjcap-c2{{animation-delay:{n(TL["infl"][0] + .4)}s}}
  .qjcap-c3{{animation-delay:{n(TL["pairs"][0] + .4)}s}} .qjcap-c4{{animation-delay:{n(TL["quarks"][0] + .4)}s}}
  .qjcap-c5{{animation-delay:{n(TL["gal"][0] + .2)}s}}.qjcap-c6{{animation-delay:{n(TL["gal"][0] + OFF["sunmark_at"] + .4)}s}}
  .qjcap-c7{{animation-delay:{n(TL["solar"][0] + .8)}s}}.qjcap-c8{{animation-delay:{n(TL["earth"][0] + .8)}s;animation-name:qjcos-caplast;animation-duration:2.4s}}
  .qjcos-stmt{{animation:qjcos-fade 1.6s ease forwards;animation-delay:{n(T_END)}s}}
}}
@media (prefers-reduced-motion:reduce){{
  .qjcos-gal,.qjcos-solar,.qjcos-pairs,.qjcos-quarks,.qjcos-nucleus,
  .qjcos-flucts,.qjcos-infl,.qjcos-ripples,.qjcos-mist{{display:none}}
  .qjcos-sc{{opacity:1}}
  .qjcos-earth{{opacity:1}}
  .qjcos-stmt{{opacity:1}}
  .qjcos-cap{{display:none}}
}}

@keyframes qjcos-fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes qjcos-scin{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes qjcos-scout{{from{{opacity:1}}to{{opacity:0}}}}
@keyframes qjcos-mistflow{{0%{{opacity:0}}16%{{opacity:.9}}70%{{opacity:.2}}100%{{opacity:.06}}}}
@keyframes qjcos-fluct{{0%{{opacity:0;transform:translate(0,0) scale(.3)}}
  32%{{opacity:.9;transform:translate(calc(var(--px)*.55),calc(var(--py)*.55)) scale(1)}}
  70%{{opacity:.42}}
  100%{{opacity:0;transform:translate(var(--px),var(--py)) scale(.2)}}}}
@keyframes qjcos-infl{{0%{{opacity:0;transform:scale(.04)}}
  20%{{opacity:1}}
  58%{{transform:scale(1);opacity:1}}
  100%{{transform:scale(.26);opacity:.92}}}}
@keyframes qjcos-ripple{{0%{{opacity:0;transform:scale(.1)}}
  20%{{opacity:.55}}
  100%{{opacity:0;transform:scale(3.4)}}}}
@keyframes qjcos-pairfly{{0%{{opacity:0;transform:translate(0,0) scale(.25)}}
  22%{{opacity:.95}}
  72%{{opacity:.9}}
  100%{{opacity:0;transform:translate(var(--dx),var(--dy)) scale(1.05)}}}}
@keyframes qjcos-pairsurv{{0%{{opacity:0;transform:translate(0,0) scale(.25)}}
  22%{{opacity:.95}}
  100%{{opacity:.92;transform:translate(var(--dx),var(--dy)) scale(1.05)}}}}
@keyframes qjcos-flash{{0%{{opacity:0;transform:scale(.3)}}
  30%{{opacity:.95;transform:scale(1.7)}}
  100%{{opacity:0;transform:scale(2.6)}}}}
@keyframes qjcos-grow{{from{{opacity:0;transform:scale(.2)}}to{{opacity:1;transform:scale(1)}}}}
@keyframes qjcos-quarkp{{0%{{opacity:0;transform:translate(0,0) scale(.45) rotate(0deg)}}
  16%{{opacity:1}}
  64%{{transform:translate(0,0) scale(1) rotate(230deg)}}
  100%{{transform:translate(46px,0) scale(.58) rotate(400deg)}}}}
@keyframes qjcos-quarkn{{0%{{opacity:0;transform:translate(0,0) scale(.45) rotate(0deg)}}
  16%{{opacity:1}}
  64%{{transform:translate(0,0) scale(1) rotate(-230deg)}}
  100%{{transform:translate(-46px,0) scale(.58) rotate(-400deg)}}}}
@keyframes qjcos-burst{{0%{{opacity:0;transform:translate(0,0) scale(.2)}}
  22%{{opacity:.9}}
  100%{{opacity:.86;transform:translate(var(--dx),var(--dy)) scale(1)}}}}
@keyframes qjcos-draw{{to{{stroke-dashoffset:0}}}}
/* 缩放幕的淡出拉长到后 40%，让「推进」与下一幕淡入充分交叉，避免硬切 */
@keyframes qjcos-galzoom{{0%{{opacity:1;transform:translate(0,0) scale(1)}}
  40%{{opacity:.95;transform:translate(calc(var(--tx)*.22),calc(var(--ty)*.22)) scale(2.6)}}
  70%{{opacity:.6;transform:translate(calc(var(--tx)*.62),calc(var(--ty)*.62)) scale(5.4)}}
  100%{{opacity:0;transform:translate(var(--tx),var(--ty)) scale(9)}}}}
@keyframes qjcos-shrink{{0%{{opacity:1;transform:scale(1)}}
  100%{{opacity:0;transform:scale(.4)}}}}
@keyframes qjcos-solin{{from{{opacity:0;transform:scale(.42)}}
  to{{opacity:1;transform:scale(1)}}}}
@keyframes qjcos-solzoom{{0%{{opacity:1;transform:translate(0,0) scale(1)}}
  40%{{opacity:.95;transform:translate(calc(var(--tx)*.22),calc(var(--ty)*.22)) scale(2.6)}}
  70%{{opacity:.6;transform:translate(calc(var(--tx)*.62),calc(var(--ty)*.62)) scale(5.4)}}
  100%{{opacity:0;transform:translate(var(--tx),var(--ty)) scale(9)}}}}
/* 起点 scale：接住太阳系 zoom 末态的视觉尺寸，落点不跳 */
@keyframes qjcos-earthrise{{0%{{opacity:0;transform:scale(var(--e0,.35))}}
  100%{{opacity:1;transform:scale(1)}}}}
@keyframes qjcos-capshow{{0%{{opacity:0}}14%{{opacity:1}}74%{{opacity:1}}100%{{opacity:0}}}}
@keyframes qjcos-caplast{{from{{opacity:0}}to{{opacity:1}}}}
"""

# 地球入场起始 scale 随画幅不同（接住各自推进幕的末态尺寸）
CSS += f"""
.qjcos-sc-w .qjcos-earth{{--e0:{MODES["wide"]["EARTH0"]}}}
.qjcos-sc-t .qjcos-earth{{--e0:{MODES["tall"]["EARTH0"]}}}
"""

# ══════════ 组装 ══════════
svg_w, info_w = scene(MODES["wide"])
svg_t, info_t = scene(MODES["tall"])

HTML = f"""<!-- ══════ 第七境 · 首页「宇宙演化」动画 v2.1 · 上线片段 ══════
     用法：WP 后台 → 页面 13 → 【代码编辑器】→ 粘贴 → 更新
     ⚠️ 区块编辑器会剥掉样式标签与脚本标签，必须切到代码编辑器
     v2：圆点全部落到真实粒子行为；「三生万物」= 银河系 → 太阳系 → 地球
     v2.1：删「日月山水人文」／地球真实配色／幕间交叉溶解／26s → 43s
           ＋窄屏自动切竖幅画幅（银河与太阳系收小、地球放大）
     零 JS · 零外部图片 · 零 filter；约 43s 播完停终态；支持 prefers-reduced-motion
     回滚：整段删除即恢复原首页（v1 片段见 上线片段-首页宇宙演化动画.html）
     ══════════════════════════════════════════════════ -->
<style>{CSS}</style>

<div class="qjcos-hero">
{svg_w}
{svg_t}
  <div class="qjcos-cap qjcap-c1">道 · 真空不空，涨落忽生忽灭</div>
  <div class="qjcos-cap qjcap-c2">道生一 · 暴胀：一点能量展开为时空</div>
  <div class="qjcos-cap qjcap-c3">一生二 · 对称破缺：物质与反物质成对而生</div>
  <div class="qjcos-cap qjcap-c4">二生三 · 三夸克被胶子束缚，成质子与中子</div>
  <div class="qjcos-cap qjcap-c5">三生万物 · 原子核与电子结合，第一批原子</div>
  <div class="qjcos-cap qjcap-c6">星辰聚为星系 · 银河系</div>
  <div class="qjcos-cap qjcap-c7">银河一隅 · 太阳系</div>
  <div class="qjcos-cap qjcap-c8">地球 · 一切文明都在这里</div>
</div>

<div class="qjcos-stmt">
  <div class="qjcos-lead">同一个问题，两条路径</div>
  <div class="qjcos-note">面对「万物从何而来」，现代宇宙学给出一条路径，《道德经》给出另一条，两者结构相似。</div>
  <div class="qjcos-acts">
    <a class="p" href="/collection">免费领取 16 朝壁纸</a>
    <a class="s" href="/5000years">进入 · 上下五千年</a>
  </div>
</div>
"""

def wp_safe(html):
    """WP 的 wpautop 会在「空行」处插入 </p><p>（按 \\n\\s*\\n 切块再逐块包 <p>）。

    <style> 内部一旦被插入 </p><p>，CSSOM 遇非法 token 会把后续规则整段吞掉
    ⇒ @media 里的 animation 全部失效 ⇒ 元素停在 opacity:0 ⇒ **整块全白**。
    <svg> 内部被插入 <p> 会多出一堆外来元素。
    实测：主题与 MailerLite 的几个 <style> 都是「内嵌 <p> = 0」，因为它们 CSS 里没有空行
    —— 只有本片段有空行，所以只有本片段被插。⇒ 根治办法＝**发布前消掉所有空行**。
    """
    # 1) <style> 内容压成一行（彻底没有 \n，wpautop 无从切块）
    html = re.sub(
        r"(<style[^>]*>)(.*?)(</style>)",
        lambda m: m.group(1) + re.sub(r"\s+", " ", m.group(2)).strip() + m.group(3),
        html, flags=re.S)
    # 2) 其余位置去掉空行（保留单换行，只为可读性）
    return re.sub(r"\n[ \t]*\n+", "\n", html)


out = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/上线片段-首页宇宙演化动画-v2.html"
with open(out, "w", encoding="utf-8") as f:
    f.write(wp_safe(HTML))

# ── 本地预览页（含播放控制 + 手机视图 iframe；上线时不要用这一份） ──
def preview(extra=""):
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>首页宇宙演化动画 v2.1 · 本地预览</title>
<style>
body{{margin:0;padding:26px 20px 60px;background:#faf9f6;
     font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;color:#1a1a18}}
.bar{{max-width:1200px;margin:0 auto 18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.bar b{{font-size:13px;font-weight:500;letter-spacing:.08em}}
.bar button{{padding:8px 18px;border:1px solid #c9c4b8;background:#fff;border-radius:2px;
     font-size:13px;letter-spacing:.1em;color:#4a463e;cursor:pointer;font-family:inherit}}
.bar button:hover{{border-color:#1a1a18;color:#1a1a18}}
.tip{{max-width:1200px;margin:0 auto 22px;font-size:12px;line-height:1.9;color:#8d8880}}
.qj-tostate *{{animation-delay:-9999s !important}}
.ph{{max-width:1200px;margin:44px auto 0;border-top:1px solid #e6e2d8;padding-top:26px}}
.ph h3{{font-size:14px;font-weight:500;letter-spacing:.1em;margin:0 0 4px}}
.ph p{{font-size:12px;color:#8d8880;margin:0 0 16px;line-height:1.9}}
.frame{{display:flex;justify-content:center;background:#f2f0ea;padding:18px 0;border-radius:4px}}
iframe{{border:1px solid #ddd8cc;border-radius:2px;background:#fff}}
</style></head><body>
<div class="bar">
  <b>首页「宇宙演化」v2.1 · 本地预览</b>
  <button onclick="replay()">重播</button>
  <button onclick="document.getElementById('stage').classList.toggle('qj-tostate')">看终态（地球）</button>
</div>
<div class="tip">
  桌面视图＝宽幅 1200×500。真正要粘贴进 WP 后台的是
  <code>上线片段-首页宇宙演化动画-v2.html</code>（零脚本；本页的控制按钮不会被带过去）。
  把浏览器窗口拉窄到 {BP}px 以下，或看下方手机预览，即可看到竖幅版。
</div>
<div id="stage">
{HTML}
</div>
{extra}
<script>
function replay(){{var s=document.getElementById('stage'),c=s.cloneNode(true);
  c.classList.remove('qj-tostate');s.parentNode.replaceChild(c,s);}}
</script>
</body></html>
"""


def preview_phone():
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>首页宇宙演化动画 v2.1 · 手机预览</title>
<style>
body{{margin:0;padding:14px 12px 40px;background:#faf9f6;
     font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;color:#1a1a18}}
.bar{{margin:0 auto 14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.bar b{{font-size:12px;font-weight:500;letter-spacing:.06em}}
.bar button{{padding:7px 14px;border:1px solid #c9c4b8;background:#fff;border-radius:2px;
     font-size:12px;letter-spacing:.08em;color:#4a463e;cursor:pointer;font-family:inherit}}
.qj-tostate *{{animation-delay:-9999s !important}}
.tip{{font-size:11px;line-height:1.8;color:#8d8880;margin:0 0 14px}}
</style></head><body>
<div class="bar">
  <b>竖幅 720×780</b>
  <button onclick="replay()">重播</button>
  <button onclick="document.getElementById('stage').classList.toggle('qj-tostate')">看终态</button>
</div>
<div class="tip">这一份用来看手机端效果：地球直径 330/720，约占画幅 46%（旧版仅约 15%）。</div>
<div id="stage">
{HTML}
</div>
<script>
function replay(){{var s=document.getElementById('stage'),c=s.cloneNode(true);
  c.classList.remove('qj-tostate');s.parentNode.replaceChild(c,s);}}
</script>
</body></html>
"""


p_main = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/道境-首页-宇宙演化动画-v2-预览.html"
p_phone = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/道境-首页-宇宙演化动画-v2-预览-手机.html"
with open(p_phone, "w", encoding="utf-8") as f:
    f.write(preview_phone())
extra = f"""<div class="ph">
  <h3>手机视图（竖幅 720×780）</h3>
  <p>下面是 400px 宽的 iframe，页面按自身宽度判断，会走 <code>max-width:{BP}px</code> 分支 —— 与真机一致。</p>
  <div class="frame"><iframe src="{p_phone.split('/')[-1]}" width="400" height="880"></iframe></div>
</div>"""
with open(p_main, "w", encoding="utf-8") as f:
    f.write(preview(extra))

print(f"OK  {out}")
for tag, info in (("wide", info_w), ("tall", info_t)):
    print(f"  [{tag}] 星点 {info['stars']} | 太阳 {n(info['SUN'][0])},{n(info['SUN'][1])} | "
          f"地球落点 {n(MODES[tag]['CX'])},{n(MODES[tag]['EY'])} | "
          f"zoom 原点 {n(info['EARTH'][0])}px {n(info['EARTH'][1])}px")
print(f"字节 {len(HTML.encode())}")
