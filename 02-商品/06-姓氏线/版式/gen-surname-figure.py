#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏线 · 成品出图器（模板驱动，本地零积分）

职责只有两件：
  ① 人物底纹素材处理（生图源 → 带 alpha 的墨迹层）
  ② 取版式模板 → 填数据槽位（交给 gen-surname-v2a.py）→ 替换底纹 → 渲染出图

⚠️ 本脚本**不持有任何版式数值**。版式权威文件只有两个：
     02-商品/06-姓氏线/版式/模板-姓氏-v11.html       （std 1920×1080）
     02-商品/06-姓氏线/版式/模板-姓氏-v11-mac.html   （Mac 1920×1248）

渲染流程（唯一一条写不进 HTML 的规矩，因为它发生在 HTML 之外）：
  按 2× 设备像素渲染 → 再用 LANCZOS 缩回目标尺寸。
  实测：商/周 v9 的 std 图本身就是 4K 缩制品（std 与「4K缩回」差异 mean 0.59、
  墨量完全相同）→ B 线必须同法，否则笔画比商周细一档。

用法：
  python3 gen-surname-figure.py --prep 赵          # 生图源 → 底纹素材（零成本）
  python3 gen-surname-figure.py 赵                 # 出 std 三档（1920×1080 / 3840×2160 / Mac 3840×2496）
  python3 gen-surname-figure.py 赵 钱 --out DIR    # 批量
  python3 gen-surname-figure.py 赵 --no2x          # 应急：直渲 1×（笔画偏细，仅用于快速看版式）
"""
import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

from scipy import ndimage
import time

import numpy as np
from PIL import Image

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
LINE = ROOT / '02-商品/06-姓氏线'
FIGDIR = LINE / '底纹-人物'
SRCDIR = FIGDIR / '生图源'
OUTDIR = LINE / '成品-桌面-v11'
CH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

# ── 载入 v2A 生成器（数据 + 字形闸门 + 模板填槽；文件名含连字符不能用 import）──
_spec = importlib.util.spec_from_file_location('v2a', LINE / '版式/gen-surname-v2a.py')
v2a = importlib.util.module_from_spec(_spec)
sys.modules['v2a'] = v2a
_spec.loader.exec_module(v2a)

# ── 素材处理 ────────────────────────────────────────────────────
# 与玄鸟/凤凰同法（2026-09-29 踩坑修正后）：底色是纸色 237~248 不是纯白，
# 先按 92% 分位估底 base，整图 +(255-base) 抬白 —— 浓淡关系完全保留。
# ⚠️ CROP/EDGE 都是**为第一张横构图占位图（赵匡胤半身·展脚幞头）量身调的值**，
#    不是通则。人物构图不同（竖幅、骑马、全身）时必须逐张调整，否则会裁掉主体
#    或把边缘淡掉。2026-10-04 起改为命令行可传（`--crop none` / `--edge 0`），
#    下面这两个常量只作为**不传参时的默认值**保留向后兼容。
CROP = (270, 0, 1275, 1024)      # 含完整展脚＋少量留白（⚠️ 曾裁到 430~1120，
                                 #    把展脚横翅切断，画面里留下两条突兀断线）
EDGE = 55                        # 左右边缘渐隐宽度
BIAS = 20                        # 背景偏置：alpha ≤ BIAS 判为纸面/淡雾 → 压成全透明

# ── 真云纹（2026-10-04：把 --haze 的"无形光晕"换成 A 线那种有形的云）────────
# ⚠️ --haze 是**人物自身 alpha 大半径模糊**得来的光晕，它跟着人物轮廓走、没有
#    形状，所以"有雾气但没有云"。A 线玄鸟/凤凰的云是有笔画的：来自生图原图
#    phoenix-raw.png 左下角那团云（gen-phoenix-full.py §2 同法）——大尺度镜像
#    多次低权重叠加 → 高斯模糊 → levels 提白（压掉"雾霾感"、留白干净）。
#    这里只是把画布从 A 线的 1536×1024 横幅换成 B 线的竖幅素材尺寸，其余同法。
CLOUD_SRC = ROOT / '02-商品/02-素材/底纹/phoenix-raw.png'
CLOUD_BOX = (0, 470, 560, 1024)      # 云贴片在原图里的位置 (x0,y0,x1,y1)
CLOUD_SCALES = [2.4, 3.0, 2.7, 2.5, 3.2, 2.8, 2.6, 3.1]   # ⚠️ 双次标定：1.2~1.9 时云团
#   只有画布宽的 0.7~1.1 倍 → 渲出来是"碎点/污渍"，且铺满后成一块**边界硬切的矩形灰块**
#   （2026-10-04 实测比无形光晕更糟）。A 线云贴片放大 2.2~3.0 倍（≈ 画布宽的 1.4~2 倍）
#   才有"大团云气"的观感 —— 竖幅画布取同比例。
CLOUD_W = 0.18                       # 单块贴图权重（尺度放大后重叠更多，权重相应下调）
CLOUD_FEATHER = 0.22                 # 四边羽化比例（⚠️ 不改这个 = 矩形灰块，见上）
CLOUD_BLUR = 8.0                     # 云整体模糊 σ（素材像素）
CLOUD_LEVELS = (238, 253, 236)       # (lo, hi, 最浓灰度)：压缩灰阶 → 云团成形、留白干净
CLOUD_FADE = 0.20                    # 左侧渐隐比例（云比雾更满幅，故比 haze 的 .35 缓）
CLOUD_HALO_S = 60.0                  # 人物周围留白的模糊半径（云不与主体打架）
CLOUD_HALO_K = 0.70                  # 留白强度

# ── 动漫化（2026-10-04：嫌写意水墨"太写实"，改走动漫/赛璐璐笔触）───────────
# ⭐ 关键认知：底纹最终是**单色 alpha 墨迹层**（RGB 恒墨色 26,26,24，只有浓淡），
#    所以"动漫风"不需要重新生图 —— 它的两大特征都能在 alpha 域合成：
#      · 线稿 = 等宽带状边缘（形态学梯度 膨胀−腐蚀，比 Sobel 的双线更像描线）
#      · 平涂 = posterize 分档 + 丢掉最淡档（去掉水墨的碎笔触/皴法）
#    零积分、可批量、对版式零影响。真要"动漫造型"（脸/比例/服饰）才需重新生图。
ANIME_LINE = 0.85                    # 线稿峰值强度（0..1 → 成品墨深 = 值×OPACITY×INK）
ANIME_FLAT = 0.45                    # 平涂块面强度
ANIME_LEVELS = 3                     # 平涂档数（2=硬平涂，3=带一档中间调）
ANIME_BOLD = 2                       # 线宽半径（形态学核 = 2·bold+1，素材像素）
ANIME_SMOOTH = 1.0                   # 提线前预模糊 σ（去噪，防碎线）
ANIME_CUT = 0.22                     # 平涂阈值：alpha 低于此值判为"碎笔触"直接丢

# ── 线条清理（2026-10-04：嫌线条"拖泥带水"、转折处有墨迹顿点）──────────────
# ⭐ 关键认知：用户要的三件事在 alpha 域是**三种不同的东西**，必须分开治：
#      · 碎笔触/飞白/毛刺 = **孤立小连通域** → 按面积阈值整块丢掉（不伤主笔画）
#      · 墨迹顿点（转折处的墨疙瘩） = **局部浓墨尖峰**（高频）→ 削峰，只削高出局部趋势的部分
#      · 水墨气势 = **低频的笔画粗细变化** → 必须保留（所以趋势用较大 σ，别用会保边的算子）
#    ⚠️ 顺序与副作用：削峰会略微降整体墨量，可在 clean 后用 --density 补回。
CLEAN_SPECKLE = 24                   # 孤立墨块面积阈值（px²），小于此值判为碎笔触丢掉
CLEAN_BLOB = 0.40                    # ⚠️ 削顿强度别给大：σ 一大，**细线自己就被当成峰削掉**
                                     #    （实测 σ=9/blob=.9 整幅变淡、墨块失重）
CLEAN_SIGMA = 5.0                    # 局部趋势半径（素材像素）：**只该削掉比这更小的疙瘩**
CLEAN_TOL = 0.12                     # 容差：超出趋势不超过此比例视为"自然粗细变化"，不削
CLEAN_MEDIAN = 0                     # 中值滤波核（0=关；去毛刺/飞白，但会轻微磨损细线）
CLEAN_CLOSE = 0                      # 闭运算核（0=关）：**连接断线**。素材里线条常被生图画断
                                     #    （弓臂、马腿实测），削峰/提线都补不回来，只有闭运算
                                     #    （先膨胀再腐蚀）能把间隙小于核的断口连上。⚠️ 核别大，
                                     #    大了会把两条本该分开的线粘在一起。
CLEAN_OPEN = 0                       # 开运算核（0=关）：去毛刺。与 close 配对＝形态学平滑
CLEAN_CRISP = 0.55                   # ⭐ **主力旋钮**：把线条拉到接近饱和（见 clean_layer ③）
                                     #    "墨迹顿点"的视觉本质是**深浅不匀**（转折处更黑更鼓）；
                                     #    线条整体饱和后，顿点感自然消失 —— 比削峰对症得多

# 素材 alpha ↔ 成品墨深的换算（量测与标定用）
#   成品墨深 d = (alpha/255) · OPACITY · INK，其中 INK=(255-26)/255 是墨色(26,26,24)的最大墨深
OPACITY = 0.32                       # ⚠️ 必须与模板 .figure{opacity} 一致（两线统一 .32）
INK = (255.0 - 26.0) / 255.0


def edge_window(h, w, fw):
    """四边平滑羽化窗（smoothstep）。⚠️ 云贴片本身是**矩形**，直接铺满整幅素材，
    素材贴进成品后就是一块边界直上直下的灰斑（user 2026-10-04 一眼看出"像贴了张灰纸"）。
    A 线之所以没有这个问题，是因为它整幅都是云、且带椭圆径向 mask。"""
    if fw <= 0:
        return 1.0
    fx = np.minimum(np.arange(w), w - 1 - np.arange(w)) / max(1.0, fw * w)
    fy = np.minimum(np.arange(h), h - 1 - np.arange(h)) / max(1.0, fw * h)
    wx = np.clip(fx, 0, 1)
    wy = np.clip(fy, 0, 1)
    wx = wx * wx * (3 - 2 * wx)
    wy = wy * wy * (3 - 2 * wy)
    return wy[:, None] * wx[None, :]


def clean_layer(af, speckle=CLEAN_SPECKLE, blob=CLEAN_BLOB, sigma=CLEAN_SIGMA,
                tol=CLEAN_TOL, median=CLEAN_MEDIAN, crisp=CLEAN_CRISP,
                close=0, open_k=0):
    """墨迹层 alpha（0..1）→ **清理后的墨迹层**：去碎笔触、去墨迹顿点，保留气势。

    三步，各自对应一种"脏"：

    ① 去碎（speckle）：alpha > 0.15 判为墨 → 连通域标记 → 面积 < speckle 的整块置 0。
       专门吃飞白、溅墨点、断开的碎笔；因为是**整块**丢，不会磨损主笔画。
    ② 去毛（median，默认关）：中值滤波抹掉轮廓毛刺。⚠️ 会轻微磨损细线，按需开。
    ③ 削顿（blob）：trend = 高斯模糊(af, σ) 作为**局部趋势**（低频，＝笔画的粗细走势
       ＝水墨气势，必须保住）；over = af − trend·(1+tol) 是**显著高出趋势的部分**
       （＝转折处的墨疙瘩）；af −= over·blob。
       ⚠️ 为什么用高斯而不是中值/开运算做趋势：中值保边 → 会把顿点当成"边"保下来；
       开运算会把比核细的线条整体腐蚀掉 → 断线。高斯是唯一既去疙瘩又留走势的。
       ⚠️ tol 是"自然粗细变化"的容许带：没有它，粗笔画的正常加粗会被一起削平。
       ⚠️⚠️ σ **必须远小于笔画长度、接近顿点尺寸（默认 5）**：σ 给到 9 会把整条细线
       都判为"高出趋势"而削淡（2026-10-04 实测 C 档整幅失重就是这个原因）。
    ④ 提线（crisp，**主力**）：smoothstep(lo, hi, af) 软阈值 —— lo 以下全透（吃掉灰色
       晕带＝"拖泥带水"），hi 以上全实（线条饱和）。**这一步才是"干净利落"的关键**：
       线条满黑之后，转折处那点深浅不匀（＝顿点感）在视觉上就没了。
       放在最后做，前面削峰削掉的墨量由它一并拉回。
    """
    out = af
    if median and median > 0:
        out = ndimage.median_filter(out, size=int(median))
    if speckle and speckle > 0:
        m = out > 0.15
        if m.any():
            lab, n = ndimage.label(m)
            if n:
                sizes = np.bincount(lab.ravel())
                drop = sizes < int(speckle)
                drop[0] = False                      # 0 号是背景，别误杀
                out = np.where(drop[lab], 0.0, out)
    if close and close > 0:                  # 连接断线（断口 < 核）——提线/削峰都补不了
        out = ndimage.grey_closing(out, size=int(close))
    if open_k and open_k > 0:                # 去毛刺（与 close 配对＝形态学平滑）
        out = ndimage.grey_opening(out, size=int(open_k))
    if blob and blob > 0:
        trend = ndimage.gaussian_filter(out, sigma=sigma)
        over = np.clip(out - trend * (1.0 + tol), 0, None)
        out = np.clip(out - over * blob, 0, 1)
    if crisp and crisp > 0:
        lo = 0.18 * crisp
        hi = 0.80 - 0.35 * crisp
        t = np.clip((out - lo) / max(hi - lo, 1e-6), 0, 1)
        out = t * t * (3.0 - 2.0 * t)                # smoothstep：软阈值，不生硬
    return np.clip(out, 0, 1)


def anime_layer(af, line=ANIME_LINE, flat=ANIME_FLAT, levels=ANIME_LEVELS,
                bold=ANIME_BOLD, smooth=ANIME_SMOOTH, cut=ANIME_CUT):
    """墨迹层 alpha（0..1，1=最浓）→ **动漫/赛璐璐笔触**的墨迹层。

    af : float32 二维数组，0=纸 1=墨（prep 里 alpha/255）。
    返回同形状 float32，值域 0..1。

    ① 线稿：**形态学梯度** grey_dilation − grey_erosion。它给出的是**等宽的带状边缘**
       （宽度 = 2·bold+1），观感是"描线"；而 Sobel 在边界两侧各出一条 → 双线、发毛。
       再过幂次曲线压掉弱边缘，线条干净、闭合。
    ② 平涂：round(af·levels)/levels 分档 → 块面；af < cut 的部分直接置 0，
       这一步专门吃掉水墨的皴法/飞白/淡晕 —— 那正是"写实感"的来源。

    ⚠️ 线宽必须按**成品缩放比**反推：素材 1360 高 → 成品 1000 高（0.735×），
       LANCZOS 会把细线平均掉（与 haze 同一个坑）。bold=2（核 5px）→ 成品约 3.7px 可见。
    """
    s = ndimage.gaussian_filter(af, smooth) if smooth > 0 else af
    k = 2 * int(bold) + 1
    # ① 线稿
    mg = ndimage.grey_dilation(s, size=k) - ndimage.grey_erosion(s, size=k)
    if mg.max() > 0:
        mg = mg / mg.max()
    line_l = np.clip(mg, 0, 1) ** 0.70 * line          # 幂次压弱边缘 → 线条干净
    # ② 平涂
    lv = max(int(levels), 1)
    q = np.round(s * lv) / lv
    flat_l = np.where(s > cut, q * flat, 0.0)
    return np.clip(np.maximum(line_l, flat_l), 0, 1)


def cloud_layer(shape, person=None, weight=CLOUD_W, blur=CLOUD_BLUR,
                levels=CLOUD_LEVELS, fade=CLOUD_FADE, halo_s=CLOUD_HALO_S,
                halo_k=CLOUD_HALO_K, feather=CLOUD_FEATHER):
    """真云纹层，返回 **成品墨深** d（0~1），shape=(h,w) 即素材尺寸。

    person : 人物 alpha(0~1)，可选。给定时在其周围做 halo 留白（A 线同款处理）。
    ⚠️ 返回的是墨深不是 alpha——调用方要除以 (OPACITY·INK) 才是素材 alpha。
    """
    h, w = shape
    g = np.asarray(Image.open(CLOUD_SRC).convert('L')).astype(np.float32)
    g = np.clip(g + (255.0 - float(np.percentile(g, 92))), 0, 255)   # 纸色抬白（同 prep）
    x0, y0, x1, y1 = CLOUD_BOX
    patch = np.clip(g[y0:y1, x0:x1], 216, 255)        # 掐掉云团里混着的浓墨块
    patch = ndimage.gaussian_filter(patch, 5.0)       # 柔化内部纹理 → "纯云气"
    pa = np.clip((254.0 - patch) / 34.0, 0, 1)
    PH, PW = patch.shape

    cv = np.full((h, w), 255.0)
    i = 0
    for cy in np.linspace(-0.12, 1.12, 4) * h:
        for cx in np.linspace(-0.12, 1.12, 4) * w:
            sc = CLOUD_SCALES[i % len(CLOUD_SCALES)]
            nh, nw = max(8, int(PH * sc)), max(8, int(PW * sc))
            gg = np.asarray(Image.fromarray(patch.astype(np.uint8))
                            .resize((nw, nh), Image.LANCZOS)).astype(np.float32)
            aa = np.asarray(Image.fromarray((pa * 255).astype(np.uint8))
                            .resize((nw, nh), Image.LANCZOS)).astype(np.float32) / 255.0
            if i % 3 == 0:
                gg, aa = gg[:, ::-1], aa[:, ::-1]
            if i % 2 == 1:
                gg, aa = gg[::-1, :], aa[::-1, :]
            X0, Y0 = int(cx - nw / 2), int(cy - nh / 2)
            sx0, sy0, sx1, sy1 = max(0, X0), max(0, Y0), min(w, X0 + nw), min(h, Y0 + nh)
            i += 1
            if sx1 <= sx0 or sy1 <= sy0:
                continue
            sub = cv[sy0:sy1, sx0:sx1]
            al = aa[sy0 - Y0:sy1 - Y0, sx0 - X0:sx1 - X0] * weight
            cv[sy0:sy1, sx0:sx1] = sub * (1 - al) + gg[sy0 - Y0:sy1 - Y0, sx0 - X0:sx1 - X0] * al

    cv = ndimage.gaussian_filter(cv, blur)
    lo, hi, darkest = levels
    d = np.clip((cv - lo) / (hi - lo), 0, 1) * (255 - darkest) / 255.0
    if person is not None:                            # 人物周围留白，云不压主体
        halo = ndimage.gaussian_filter(person, halo_s)
        if halo.max() > 0:
            halo = halo / halo.max()
        d = d * (1 - halo_k * np.clip(halo, 0, 1))
    x = np.arange(w, dtype=np.float32) / max(w - 1, 1)
    d = d * np.clip(x / fade, 0, 1)[None, :]          # 左侧渐隐，防云漫进大字区
    return d * edge_window(h, w, feather)             # 四边羽化，消掉矩形硬边


def prep(char, order, src=None, crop=CROP, edge=EDGE, outdir=None,
         density=1.0, haze=0.0, haze_sigma=80.0, cloud=0.0, cloud_blur=CLOUD_BLUR,
         cloud_levels=CLOUD_LEVELS, cloud_halo_s=CLOUD_HALO_S,
         cloud_halo_k=CLOUD_HALO_K, cloud_feather=CLOUD_FEATHER,
         anime=0.0, anime_line=ANIME_LINE, anime_flat=ANIME_FLAT,
         anime_levels=ANIME_LEVELS, anime_bold=ANIME_BOLD,
         anime_smooth=ANIME_SMOOTH, anime_cut=ANIME_CUT,
         clean=0.0, clean_speckle=CLEAN_SPECKLE, clean_blob=CLEAN_BLOB,
         clean_sigma=CLEAN_SIGMA, clean_tol=CLEAN_TOL,
         clean_median=CLEAN_MEDIAN, clean_crisp=CLEAN_CRISP,
         clean_close=CLEAN_CLOSE, clean_open=CLEAN_OPEN):
    """生图源 → 底纹素材（**RGBA 墨迹蒙版**）。返回素材路径。

    crop : (x0,y0,x1,y1) 或 None（不裁）。默认沿用横构图占位图的值，换构图必须显式传。
    edge : 左右渐隐宽度 px，0 = 关闭（素材自身已有留白时不需要）。
    outdir : 输出目录，默认 FIGDIR（正式素材位）；试版对比时可指向别处不覆盖正式件。
    density : 墨色浓度倍数（alpha 线性缩放），默认 1.0。
    haze : 淡雾层强度（0=关闭）。**风格对齐用**：A 线底纹是「满幅云雾 + 纹样主体」，
        墨色节奏是「大片极淡 + 少量浓」；B 线只有一块人物 → 中位墨深偏高、缺少层次，
        观感就是"不是一个风格"。加雾（由人物自身 alpha 大半径高斯模糊得到，
        左侧渐隐防侵入大字区）能把覆盖率与墨深分布拉向 A 线。
        赵实测（纯底纹层量测）：无雾 中位 .125/覆盖 5.1% → 加雾 k.45 σ80 中位 .078/
        覆盖 10.6%，A 线玄鸟是 .075/26%（覆盖率差异是构图决定的，不强行拉平）。
    haze_sigma : 雾的模糊半径（素材像素），默认 80。
        ⚠️ 生图给的是"淡墨写意"，细笔触叠 .215 后几乎看不见（实测底纹框内
        仅 13% 像素可辨）。但**不要靠改 CSS opacity 解决**（那是版式值、两线统一）；
        正确做法是在**素材层**提浓。赵实测：裁空白 + 1.6× → 17.7%，
        2.2× → 18.9%（更浓会到"抢主体"边缘）。换姓/换风格都要重新标定。


    ⚠️ 不输出"白底灰度图"，而是输出**带 alpha 的墨迹层**：
       alpha = 255 - L（底色纯白→alpha 0 全透明；墨越浓 alpha 越大），
       RGB 统一取版式墨色 (26,26,24)。理由：白底图直接用 mix-blend-mode:multiply
       在 Chrome 里**不生效**，会整块白矩形压在纸底上。
    ⚠️⚠️ **必须再减背景偏置 BIAS**：抬白只把 248 拉到 255，但画面里大片"纸面"
       其实是 233~245 的**淡墨雾**，抬白后 alpha 仍有 10~22 → 整图以一个**淡灰矩形**
       显形。alpha' = (255-L-BIAS)·255/(255-BIAS) 把 ≤20 全压成 0。
    """
    # ⚠️⚠️ 生图源必须明确指定：早期实现是「不给 --src 就取 生图源/ 里最后一张」，
    #    在 100 姓批量时会把**同一个人的图**当成每一姓的底纹（无声出错、成品上是别人的脸）。
    #    现在：不给 --src 时只允许「生图源里恰好一张」这一种情况，且大声报警；
    #    多于一张直接报错，要求逐姓指定 --src。
    if src:
        p = pathlib.Path(src)
    else:
        cands = sorted(SRCDIR.glob('*.png'))
        if len(cands) != 1:
            raise SystemExit(
                f'生图源不明确：{SRCDIR} 里有 {len(cands)} 张图。\n'
                f'  请用 --src <图片路径> 指定「{char}」本人的生图源；'
                f'不给 --src 只允许目录里恰好一张图的情况。')
        p = cands[0]
        print(f'  ⚠️ 未指定 --src，改用 生图源/ 里唯一的一张：{p.name}\n'
              f'     请确认它确实是「{char}」的图（否则会张冠李戴）')
    if not p.exists():
        raise SystemExit(f'生图源不存在：{p}')
    im = Image.open(p).convert('L')
    a = np.asarray(im).astype(np.float32)
    base = float(np.percentile(a, 92))
    a = np.clip(a + (255.0 - base), 0, 255)
    out = Image.fromarray(a.astype(np.uint8))
    if crop:
        out = out.crop(crop)
    g = np.asarray(out).astype(np.float32)
    raw = np.clip(255.0 - g, 0, 255)
    alpha = np.clip((raw - BIAS) * 255.0 / (255.0 - BIAS), 0, 255)
    W = alpha.shape[1]
    h_orig = alpha.shape[0]
    if edge > 0 and W > 2 * edge:
        x = np.arange(W, dtype=np.float32)
        ramp = np.clip(np.minimum(x, W - 1 - x) / float(edge), 0, 1)  # 左右渐隐，避免硬切断面
        alpha = (alpha * (0.12 + 0.88 * ramp)[None, :]).astype(np.uint8)
    else:
        alpha = alpha.astype(np.uint8)
    if density != 1.0:                       # 素材层提浓（改 CSS opacity 是版式改动，见下）
        alpha = np.clip(alpha.astype(np.float32) * density, 0, 255).astype(np.uint8)
    if anime > 0:                            # 动漫/赛璐璐笔触（线稿 + 平涂，替代写实水墨）
        if haze > 0:
            print('    ⚠️ 同时给了 --haze：水墨雾与动漫笔触冲突，建议 --haze 0')
        af0 = alpha.astype(np.float32) / 255.0
        an = anime_layer(af0, line=anime_line * anime, flat=anime_flat * anime,
                         levels=anime_levels, bold=anime_bold,
                         smooth=anime_smooth, cut=anime_cut)
        alpha = (np.clip(an, 0, 1) * 255).astype(np.uint8)
    if clean > 0:                            # 线条清理（去碎笔触 + 削墨迹顿点）
        af0 = alpha.astype(np.float32) / 255.0
        cl = clean_layer(af0, speckle=int(clean_speckle * clean),
                         blob=clean_blob * clean, sigma=clean_sigma,
                         tol=clean_tol, median=int(clean_median),
                         crisp=clean_crisp * clean,
                         close=int(clean_close), open_k=int(clean_open))
        alpha = (np.clip(cl, 0, 1) * 255).astype(np.uint8)
    if haze > 0:                             # 淡雾层（对齐 A 线玄鸟/凤凰的"云雾氛围"）
        af = alpha.astype(np.float32) / 255.0
        h = ndimage.gaussian_filter(af, sigma=haze_sigma)
        if h.max() > 0:
            h = h / h.max()
        Wf = af.shape[1]
        x = np.arange(Wf, dtype=np.float32) / max(Wf - 1, 1)
        h = h * haze * np.clip(x / 0.35, 0, 1)[None, :]   # 左侧渐隐，防雾漫进大字区
        alpha = (np.clip(af + h * (1.0 - af), 0, 1) * 255).astype(np.uint8)
    if cloud > 0:                            # 真云纹（有形，替代无形光晕 haze）
        af = alpha.astype(np.float32) / 255.0
        cl = cloud_layer(af.shape, person=af, blur=cloud_blur, levels=cloud_levels,
                         halo_s=cloud_halo_s, halo_k=cloud_halo_k,
                         feather=cloud_feather) * cloud / (OPACITY * INK)
        alpha = (np.clip(af + np.clip(cl, 0, 1) * (1.0 - af), 0, 1) * 255).astype(np.uint8)
    rgb = np.zeros(g.shape + (3,), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 26, 26, 24
    odir = pathlib.Path(outdir) if outdir else FIGDIR
    odir.mkdir(parents=True, exist_ok=True)
    dst = odir / f'figure-{order:03d}-{char}.png'
    Image.fromarray(np.dstack([rgb, alpha]), 'RGBA').save(dst)
    print(f'素材 {dst}  {out.size[0]}×{out.size[1]}  底色底 {base:.0f}→255\n'
          f'    墨量(g<200) {100 * (g < 200).mean():.1f}%  |  全透明像素 '
          f'{100 * (alpha == 0).mean():.1f}%（偏置清除前 {100 * (raw <= BIAS).mean():.1f}%）\n'
          f'    crop={crop or "不裁"}  edge={edge}（左右渐隐）  density={density}×  '
          f'haze={haze}' + (f'/σ{haze_sigma:g}' if haze else '（关）') +
          f'  cloud={cloud}' + (f'/σ{cloud_blur:g}' if cloud else '（关）') +
          f'  anime={anime}' + (f'/线{anime_line}/涂{anime_flat}/档{anime_levels}'
                               f'/粗{anime_bold}' if anime else '（关）') +
          f'  clean={clean}' + (f'/碎{clean_speckle:g}/顿{clean_blob}'
                               f'/σ{clean_sigma:g}/提{clean_crisp}'
                               + (f'/闭{clean_close}/开{clean_open}'
                                  if (clean_close or clean_open) else '')
                               if clean else '（关）') +
          f'  源图 {im.size[0]}×{im.size[1]}'
          f'{"" if (crop or edge or density != 1.0) else "  ← 原图直出，换构图常用组合"}')
    return dst


FIG_RE = re.compile(r'(<img class="figure" src=")[^"]*(")')


# Mac 模板 = std 模板改下面这 8 处，其余逐字节照抄（防止两份 CSS 各改各的漂移）
MAC_HEAD = """姓氏线（B 线）版式模板 v11 · Mac 版（1920×1248，截图 2× 得 3840×2496）

  ⚠️ 本文件由 模板-姓氏-v11.html 自动同步生成（gen-surname-figure.py --sync-mac），
     **只差下列 8 处**；改版式请改 std 版后重跑同步，不要手改本文件。
       画幅 1080 → 1248｜画心标题 262 → 343｜四联字区 390 → 474｜字下行 746 → 830
       落款两区 距底 140 → 130（左下角 + 正下中）｜人物底纹 高 1000 → 1156
"""
MAC_DELTAS = [
    ('html,body{width:1920px;height:1080px', 'html,body{width:1920px;height:1248px'),
    ('.stage{position:relative;width:1920px;height:1080px',
     '.stage{position:relative;width:1920px;height:1248px'),
    ('.series{position:absolute;left:960px;top:262px', '.series{position:absolute;left:960px;top:343px'),
    ('.quat{position:absolute;left:0;right:0;top:390px', '.quat{position:absolute;left:0;right:0;top:474px'),
    ('.meta{position:absolute;left:960px;top:746px', '.meta{position:absolute;left:960px;top:830px'),
    ('.colophon{position:absolute;left:210px;bottom:140px',
     '.colophon{position:absolute;left:210px;bottom:130px'),
    ('.brand-block{position:absolute;left:960px;bottom:140px',
     '.brand-block{position:absolute;left:960px;bottom:130px'),
    ('.figure{position:absolute;right:0;bottom:0;height:1000px',
     '.figure{position:absolute;right:0;bottom:0;height:1156px'),
]


def sync_mac():
    """由 std 模板同步生成 mac 模板。"""
    std = v2a.TPL['std'].read_text(encoding='utf-8')
    for a, b in MAC_DELTAS:
        if std.count(a) != 1:
            raise SystemExit(f'同步失败：std 模板里找不到唯一锚点 {a!r}')
        std = std.replace(a, b)
    old = '姓氏线（B 线）版式模板 v11 · 唯一权威文件'
    if old not in std:
        raise SystemExit('同步失败：std 模板头部标题已改，请同步更新 MAC_HEAD')
    std = std.replace(old, MAC_HEAD, 1)
    v2a.TPL['mac'].write_text(std, encoding='utf-8')
    print(f'  ✓ 已同步 → {v2a.TPL["mac"].name}（8 处差异）')


def inject_figure(html, fig_path):
    """把模板里写死的底纹图换成该姓的人物图（模板默认是赵的图）。

    fig_path=None → 出**无底纹校样**（只隐藏人物层，版式其余部分不动），
    用于底纹还没生图时先验收版式／字形／源流文案，零积分。
    """
    if fig_path is None:
        if '</head>' not in html:
            raise SystemExit('模板里找不到 </head>，无法插入校样样式')
        return html.replace('</head>', '<style>.figure{display:none!important}</style></head>', 1)
    # ⚠️ 只在 </style> 之后的正文里换 —— 若头部注释出现带文件名的底纹标签示例，
    #    全文件替换会先命中注释、正文那份原封不动（A 线 2026-10-04 就因此把周的
    #    凤凰悄悄换成了商的玄鸟）。此处与 A 线 gen-evolution.py 同一道闸门。
    head, sep, body = html.partition('</style>')
    if not sep:
        raise SystemExit('模板缺少 </style> —— 无法定位正文')
    body, n = FIG_RE.subn(lambda m: m.group(1) + 'file://' + str(fig_path) + m.group(2),
                          body, count=1)
    if n != 1:
        raise SystemExit('正文里未找到 .figure 底纹层 —— 模板可能被改坏')
    return head + sep + body


def shot(html, w, h, out_png, scale=2):
    """Chrome 无头截图。⚠️ macOS 上 headless 截完不自退 → 后台起 + 轮询 + kill。"""
    out_png = pathlib.Path(out_png)
    if out_png.exists():
        out_png.unlink()
    cp = '/tmp/dsh-cp-surname'
    p = subprocess.Popen(
        [CH, '--headless=new', '--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
         '--hide-scrollbars', '--allow-file-access-from-files', '--user-data-dir=' + cp,
         '--force-device-scale-factor=%d' % scale, '--window-size=%d,%d' % (w, h),
         '--virtual-time-budget=9000', '--screenshot=%s' % out_png, 'file://%s' % html],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(160):
        if out_png.exists() and out_png.stat().st_size > 0:
            break
        time.sleep(0.4)
    time.sleep(1.2)
    p.kill()
    try:
        p.wait(timeout=10)
    except Exception:
        pass
    if not out_png.exists() or out_png.stat().st_size == 0:
        raise SystemExit('截图失败：%s' % out_png)
    return out_png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chars', nargs='*', default=['赵'])
    ap.add_argument('--prep', metavar='姓', help='只做底纹素材处理')
    ap.add_argument('--src', help='指定生图源（默认取目录内最新一张）')
    ap.add_argument('--out', type=pathlib.Path, default=OUTDIR)
    ap.add_argument('--norm', type=pathlib.Path, help='逐格光学归一化参数 JSON')
    ap.add_argument('--no2x', action='store_true', help='应急：直渲 1×（笔画会偏细）')
    ap.add_argument('--no-figure', action='store_true',
                    help='出无底纹校样（隐藏人物层，底纹未生图时先验收版式，零积分）')
    ap.add_argument('--crop', default=None,
                    help='底纹裁切 "x0,y0,x1,y1"，或 "none" 不裁。'
                         '不传=沿用横构图占位图默认值（换构图必显式传！）')
    ap.add_argument('--edge', type=int, default=None,
                    help='底纹左右渐隐宽度 px，0=关闭。不传=默认 %d' % EDGE)
    ap.add_argument('--prep-out', type=pathlib.Path, default=None,
                    help='底纹素材输出目录（默认正式位 底纹-人物/）；试版比调用')
    ap.add_argument('--density', type=float, default=1.0,
                    help='底纹墨色浓度倍数（素材层 alpha 缩放），默认 1.0；'
                         '淡墨生图叠 .215 后看不清时提浓（赵实测 1.6× 起效）')
    ap.add_argument('--haze', type=float, default=0.0,
                    help='淡雾层强度 k（0=关闭）。A 线玄鸟/凤凰是「满幅云雾 + 纹样」，'
                         'B 线只有一块人物 → 观感"平、闷、像贴了张灰度贴纸"。'
                         '加雾可把覆盖率与墨色节奏拉向 A 线（赵实测 k=0.45/σ80 最佳）')
    ap.add_argument('--haze-sigma', type=float, default=80.0,
                    help='雾的模糊半径（素材像素），默认 80；越大雾越散越淡')
    ap.add_argument('--cloud', type=float, default=0.0,
                    help='真云纹强度 k（0=关闭）。与 --haze 的区别：haze 是人物自身模糊出的'
                         '**无形光晕**；cloud 是复用玄鸟/凤凰那团云贴片铺出的**有形云**，'
                         '更接近 A 线的"满幅云雾"。二者二选一，cloud 模式请 --haze 0')
    ap.add_argument('--cloud-blur', type=float, default=CLOUD_BLUR,
                    help='云的模糊 σ（素材像素），默认 %g；越大云越散越淡' % CLOUD_BLUR)
    ap.add_argument('--cloud-levels', default=','.join(str(x) for x in CLOUD_LEVELS),
                    help='"lo,hi,darkest" 云的灰阶压缩曲线，默认 %s。'
                         'lo 越大=淡处被提白得越狠（中位墨深下降，去"灰蒙蒙"）；'
                         'darkest 越小=云团核心越浓（p90 上升）。'
                         '⚠️ 只调 --cloud 是把整层等比缩放，淡处跟着一起淡，层次仍然"平"；'
                         '要做出 A 线那种「大片极淡 + 少量浓」必须调这条曲线'
                         '（A 线玄鸟纯底纹层：覆盖 40 个百分点，中位 .031，p90 .306）'
                         % ','.join(str(x) for x in CLOUD_LEVELS))
    ap.add_argument('--anime', type=float, default=0.0,
                    help='动漫化总强度（0=关，1=默认档）。把写实水墨笔触换成\n'
                         '动漫/赛璐璐笔触：等宽线稿（形态学梯度）+ 分档平涂。\n'
                         '零积分、不改版式；开它时建议 --haze 0')
    ap.add_argument('--anime-line', type=float, default=ANIME_LINE, help='线稿峰值强度 0..1')
    ap.add_argument('--anime-flat', type=float, default=ANIME_FLAT, help='平涂块面强度 0..1')
    ap.add_argument('--anime-levels', type=int, default=ANIME_LEVELS, help='平涂档数（2=硬平涂）')
    ap.add_argument('--anime-bold', type=int, default=ANIME_BOLD, help='线宽半径（核=2n+1 px）')
    ap.add_argument('--anime-smooth', type=float, default=ANIME_SMOOTH, help='提线预模糊 σ')
    ap.add_argument('--anime-cut', type=float, default=ANIME_CUT,
                    help='平涂阈值：低于此 alpha 判为碎笔触直接丢（水墨写实感来源）')
    ap.add_argument('--clean', type=float, default=0.0,
                    help='线条清理总强度（0=关，1=默认档）：去掉碎笔触/飞白/溅墨点，'
                         '并削平转折处的墨迹顿点；低频的笔画粗细走势（水墨气势）保留')
    ap.add_argument('--clean-speckle', type=float, default=CLEAN_SPECKLE,
                    help='孤立墨块面积阈值（像素数），小于此值的整块丢掉')
    ap.add_argument('--clean-blob', type=float, default=CLEAN_BLOB,
                    help='削顿强度 0..1（1=把超出局部趋势的部分全削平）')
    ap.add_argument('--clean-sigma', type=float, default=CLEAN_SIGMA,
                    help='局部趋势的估计半径（素材像素）——顿点的尺度分界线')
    ap.add_argument('--clean-tol', type=float, default=CLEAN_TOL,
                    help='容差：超出趋势不超过此比例的视为自然粗细变化，不削')
    ap.add_argument('--clean-median', type=int, default=CLEAN_MEDIAN,
                    help='中值滤波核（0=关）：额外去毛刺/飞白，但会轻微磨损细线')
    ap.add_argument('--clean-close', type=int, default=CLEAN_CLOSE,
                    help='闭运算核（0=关）：连接被画断的线条（断口小于核才连得上）')
    ap.add_argument('--clean-open', type=int, default=CLEAN_OPEN,
                    help='开运算核（0=关）：去毛刺，与 close 配对即形态学平滑')
    ap.add_argument('--clean-crisp', type=float, default=CLEAN_CRISP,
                    help='提线强度 0..1（**主力旋钮**）：软阈值把线条拉到接近饱和，'
                         '吃掉灰色晕带、消除转折处的深浅不匀（顿点感）')
    ap.add_argument('--cloud-feather', type=float, default=CLOUD_FEATHER,
                    help='云的四边羽化比例，默认 %g。⚠️ 0 = 保留矩形硬边，云会变成一块'
                         '"边界直上直下的灰斑"（实测比无形光晕更糟）' % CLOUD_FEATHER)
    ap.add_argument('--cloud-halo-s', type=float, default=CLOUD_HALO_S,
                    help='人物周围留白的模糊半径，默认 %g' % CLOUD_HALO_S)
    ap.add_argument('--cloud-halo-k', type=float, default=CLOUD_HALO_K,
                    help='人物周围留白强度 0~1，默认 %g；越大云离人物越远（不压主体）'
                         % CLOUD_HALO_K)
    ap.add_argument('--force-prep', action='store_true',
                    help='素材已存在时也按 --crop/--edge/--density 重做（否则这些参数不生效）')
    ap.add_argument('--sync-mac', action='store_true',
                    help='由 std 模板同步生成 mac 模板（改完 std 版式后必跑）')
    a = ap.parse_args()
    try:
        a.cloud_levels = tuple(float(x) for x in str(a.cloud_levels).replace('，', ',').split(','))
        assert len(a.cloud_levels) == 3
    except Exception:
        raise SystemExit('--cloud-levels 需要 3 个数字：lo,hi,darkest')

    # 底纹裁切/渐隐：不传 → 沿用横构图占位图的默认值（见 CROP/EDGE 注释）
    if a.crop is None:
        crop = CROP
    elif str(a.crop).strip().lower() in ('none', '0', ''):
        crop = None
    else:
        crop = tuple(int(x) for x in str(a.crop).replace('，', ',').split(','))
        if len(crop) != 4:
            raise SystemExit('--crop 需要 4 个数字（x0,y0,x1,y1）或 none')
    edge = EDGE if a.edge is None else a.edge

    if a.sync_mac:
        sync_mac()
        return

    d, seq = v2a.load()
    if a.prep:
        item = next(s for s in seq if s['simplified'] == a.prep)
        prep(a.prep, item['order'], a.src, crop, edge, a.prep_out,
             a.density, a.haze, a.haze_sigma, a.cloud, a.cloud_blur,
             a.cloud_levels, a.cloud_halo_s, a.cloud_halo_k, a.cloud_feather,
             a.anime, a.anime_line, a.anime_flat, a.anime_levels, a.anime_bold,
             a.anime_smooth, a.anime_cut,
             a.clean, a.clean_speckle, a.clean_blob, a.clean_sigma,
             a.clean_tol, a.clean_median, a.clean_crisp,
             a.clean_close, a.clean_open)
        return

    norm = None
    if a.norm:
        norm = json.loads(a.norm.read_text(encoding='utf-8'))
    else:
        dn = LINE / '版式/_build-v2a/norm.json'
        if dn.exists():
            norm = json.loads(dn.read_text(encoding='utf-8'))
            print(f'归一化参数：套用 {dn.name}')

    a.out.mkdir(parents=True, exist_ok=True)
    build = LINE / '版式/_build-figure'
    build.mkdir(parents=True, exist_ok=True)
    scale = 1 if a.no2x else 2

    for ch in a.chars:
        item = next((s for s in seq if s['simplified'] == ch), None)
        if not item:
            print(f'  ✗ {ch}：不在姓氏表里'); continue
        fig = FIGDIR / f"figure-{item['order']:03d}-{ch}.png"
        if a.no_figure:
            fig = None
        elif not fig.exists() or a.force_prep:
            fig = prep(ch, item['order'], a.src, crop, edge, a.prep_out,
                a.density, a.haze, a.haze_sigma, a.cloud, a.cloud_blur,
                a.cloud_levels, a.cloud_halo_s, a.cloud_halo_k, a.cloud_feather,
                a.anime, a.anime_line, a.anime_flat, a.anime_levels, a.anime_bold,
                a.anime_smooth, a.anime_cut,
                a.clean, a.clean_speckle, a.clean_blob, a.clean_sigma,
                a.clean_tol, a.clean_median, a.clean_crisp,
                a.clean_close, a.clean_open)
        elif a.crop is not None or a.edge is not None or a.density != 1.0:
            print(f'    ⚠ {fig.name} 已存在，本次 --crop/--edge/--density **未生效**；'
                  f'要按新参数重做素材请加 --force-prep')
        html, rec, cover, notes, _cf = v2a.build(d, seq, item, 'trad', norm, 'std')
        miss = [k for k, v in cover.items() if v == 'missing']
        if miss:
            print(f'  ⚠ {ch}：{"、".join(miss)} 缺字（仍出图，字形可能回退）')
        for note in notes:
            print(f'    · {note}')
        print(f'[{ch}] 第{item["order"]}位')
        for tpl, w, h in (('std', 1920, 1080), ('mac', 1920, 1248)):
            hh = html if tpl == 'std' else v2a.build(d, seq, item, 'trad', norm, 'mac')[0]
            hh = inject_figure(hh, fig)
            hp = build / f"{v2a.stem_of(item)}--v11-{tpl}.html"
            hp.write_text(hh, encoding='utf-8')
            if tpl == 'std':
                big = a.out / f"{ch}-v11-3840x2160.png"
                shot(hp, w, h, big, scale)
                print(f'  ✓ {big.name}')
                if scale == 2:
                    Image.open(big).resize((w, h), Image.LANCZOS).save(
                        a.out / f"{ch}-v11-1920x1080.png")
                    print(f'  ✓ {ch}-v11-1920x1080.png')
                else:
                    Image.open(big).save(a.out / f"{ch}-v11-1920x1080.png")
            else:
                big = a.out / f"{ch}-v11-3840x2496.png"
                shot(hp, w, h, big, scale)
                print(f'  ✓ {big.name}')
    print(f'\n产出 → {a.out}')


if __name__ == '__main__':
    main()
