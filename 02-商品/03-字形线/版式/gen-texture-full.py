# -*- coding: utf-8 -*-
"""朝代底纹「满幅云雾 + 主体」通用合成器（A 线 16 朝底纹产线）。

背景：底纹铁律要求「每期须有自己底纹才允许上架」。生图产出的是「白底 + 一只瑞兽 +
左下一小团云雾」的方图，直接当底纹用会四周全白、画面空。做法沿用 2026-09-29
为周·凤凰写死的 `gen-phoenix-full.py`，这里抽成通用版，后面每期加一条配置即可。

四步（与凤凰脚本同法，已逐像素验证过）：
  1. 纸色抬白：按 P92 分位把纸底抬到 255，墨色浓淡保留
     （同时把生图平台右下角的浅色水印一起抬掉）
  2. 连通域抠主体：**只保留最大连通域 + 质心落在它附近的大块**。
     ⚠️ 不能"保留所有大块" —— 左下云雾里常混着一块浓墨（面积也 >4000），
     会被误当主体的一部分，缩小后就在画面左侧留下一块突兀的孤立墨斑。
  3. 云雾贴片：从原图左下那团淡云取贴片（先抬白、再柔化），大尺度镜像多次
     低权重平铺 → 高斯模糊 → levels 提白，得到「云团成形、留白干净」的满幅云气。
  4. 主体按 S 缩放、**质心锚定**到 (AX, AY)，允许溢出画布（压迫感来自裁切），
     略作浓墨补偿（缩小会把细笔触平均掉、发灰）；主体附近做 halo 留白，云不打架。

输出：`02-商品/02-素材/底纹/<out>.png`（1536×1024，灰阶转 RGB）

用法：
    python3 gen-texture-full.py longma                 # 单期
    python3 gen-texture-full.py longma linggui         # 多期
    python3 gen-texture-full.py longma --out longma-full-浓.png --deepen 1.25
    # 环境变量可覆盖：TEX_S / TEX_AX / TEX_AY
"""
import os
import pathlib
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

D = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/底纹')

# 云雾平铺网：两套网格
#   '宽' = 凤凰当年的参数（贴片放大 2.2–3.0×）——主体小的时候够用；
#   '细' = 2026-10-04 为龙马/灵龟加：**贴片近原尺寸、5×5 密铺、弱模糊**。
#         原因：放 2.2–3× 后整幅只有 ~2 个贴片宽，云变成大片均匀灰块（还有条带），
#         模糊 σ11 又把内部纹理抹平 → 看着既不像云、又像整幅脏灰（实测云区覆盖 95%）。
#         密铺 + 原尺寸 + σ6 才出"云团成形、留白干净"的效果。
GRID_WIDE = ([-200, 400, 1000, 1600], [-150, 350, 850, 1250],
             [2.2, 2.55, 2.9, 2.35, 2.75, 2.4, 3.0, 2.3], 11.0)
GRID_FINE = ([-140, 230, 600, 970, 1340], [-90, 200, 490, 780, 1070],
             [0.95, 1.25, 0.85, 1.35, 1.05, 0.9, 1.3, 1.0, 1.15, 0.8], 6.0)
GRIDS = {'宽': GRID_WIDE, '细': GRID_FINE}

# 云雾档位: (云权重, 网格, 浓墨补偿, levels(lo, hi, 最浓灰度))
#   levels 是"云团成形"的关键：lo 越高 → 只有最浓处显现、其余归白（留白干净、不成雾霾）；
#   darkest 越低 → 云心越浓。判定标准不是"看着像云"，而是量化：
#   已上线的 phoenix-full.png 云区占 46%、P5 206、中位 240 —— 新底纹要跟它同档。
OPTS = {
    '云淡': (0.30, '宽', 1.10, (238, 253, 236)),
    '云浓': (0.46, '宽', 1.25, (236, 252, 226)),
    '云聚': (0.40, '宽', 1.15, (246, 253, 208)),
    '云细': (0.42, '细', 1.15, (243, 253, 212)),
    '云细浓': (0.55, '细', 1.25, (240, 253, 200)),
}
SCALES = [2.2, 2.55, 2.9, 2.35, 2.75, 2.4, 3.0, 2.3]      # 每个贴片一个尺度
GRID_X = [-200, 400, 1000, 1600]
GRID_Y = [-150, 350, 850, 1250]

# 主体附近留白强度（可用环境变量覆盖，便于出多档对比）
HALO_SIG = float(os.environ.get('TEX_HALO_SIG', '45'))
HALO_W = float(os.environ.get('TEX_HALO_W', '0.85'))

# ── 每期配置 ────────────────────────────────────────────────
# patch : 云雾贴片在原图上的取景框 (x0, y0, x1, y1)，取左下那团淡云
# scale : 主体相对"原图铺满"的倍数    ax/ay : 主体质心落在画面的比例
# opt   : 云雾档位（mode='平铺' 时用）  mode : '平铺' | '雾'
# haze  : mode='雾' 时的雾底权重（0.10–0.15；越小越淡）
TEX = {
    # ⚠️ S/ax/ay 是**用户定稿值**（2026-10-04）：S0.85 大小 + 质心(75%, 39.6%/41.3%)，
    #    即"D 版大小整体下移到露头"。⚠️ 改 ay 前必读 底纹-朝代/README.md §六 ——
    #    ay 是**墨迹质心**比例且成品被 cover 上下各裁 100px，肉眼调必裁头。
    'longma':  dict(out='longma-full.png',  patch=(0, 470, 520, 770),
                    scale=0.85, ax=0.75, ay=0.3965, opt='云淡', mode='雾', haze=0.13),
    'linggui': dict(out='linggui-full.png', patch=(0, 480, 520, 780),
                    scale=0.85, ax=0.75, ay=0.4131, opt='云淡', mode='雾', haze=0.13),
    # ⭐ 2026-10-05 第二批三朝（REQ-2026-10-05-02）：ay 一律由 §六「不裁头」公式反解
    #   —— ay = (110 + (ȳ − ymin)·S) / 1024，成品 y≥110 才不会被 cover 切到主体顶部。
    #   提示词已带「大写意、枯笔飞白、通幅墨韵」，治的就是§五那条「白色纸上贴一只兽」。
    'luoshen': dict(out='luoshen-full.png', patch=(0, 470, 520, 770),
                    scale=0.85, ax=0.75, ay=0.4565, opt='云淡', mode='雾', haze=0.13),
    #   ⚠️ 白鹅原用 S0.85/ay0.5737 ⇒ 下缘 y859，**品牌区浓墨 32.2%（压住落款，2026-10-05 发现并修正）**。
    #      降到 S0.72/ay0.5024 → 下缘 y744、品牌区 0.0%。代价：全幅可见由 11.8% 降到 9.7%（生图本身墨量仅 10%）。
    'baie':    dict(out='baie-full.png',    patch=(0, 470, 520, 770),
                    scale=0.72, ax=0.75, ay=0.5024, opt='云淡', mode='雾', haze=0.13),
    #   ⚠️ 生图主体几乎满幅（墨量 41%、只有 22% 云、占宽 85%）——S0.85 会压到画面中央，
    #      收到 **S0.60** 后占位 x[44%,100%] y[11%,67%]，与另两朝同档。
    'mojie':   dict(out='mojie-full.png',   patch=(0, 470, 520, 770),
                    scale=0.60, ax=0.75, ay=0.4340, opt='云淡', mode='雾', haze=0.13),
    #   ⚠️ 黑龙生图主体很高（原高 992px，占画幅 97%）⇒ S0.85 下缘压到 y953、品牌区浓墨 21.9%（压住落款）。
    #      S0.75 → 品牌区 0.0%、全幅可见 18.9%（各档最高）⇒ **定稿 S0.75**。
    'heilong': dict(out='heilong-full.png', patch=(0, 470, 520, 770),
                    scale=0.75, ax=0.75, ay=0.5053, opt='云淡', mode='雾', haze=0.13),
    'baihu':   dict(out='baihu-full.png',   patch=(0, 470, 520, 770),
                    scale=0.85, ax=0.75, ay=0.4578, opt='云淡', mode='雾', haze=0.13),
    # ⭐ 2026-10-05 第三批三朝（唐贡狮／宋瑞鹤／明麒麟，REQ-2026-10-05-04）：
    #   ⚠️ 本批生图**云雾与兽体粘连**（狮/麟脚踩浓云）⇒ 走「雾」模式抠图会在成品里留下
    #      1px 硬边（2026-10-05 实测，窗口+羽化都救不回）⇒ **改走 mode='原位'**
    #      （云原地压淡、浓墨原地保留，不缩放不位移）；上下取景由 gen-evolution.py 的
    #      `tex_pos`（object-position）承担。实录见底纹-朝代/README.md §十一。
    #   haze ← 云压淡系数 k（越小云越淡）；ink/span ← 浓墨保留阈值（L<ink−span 全保留）
    'gongshi': dict(out='gongshi-full.png', mode='原位', haze=0.16, ink=135, span=50),
    'ruihe':   dict(out='ruihe-full.png',   mode='原位', haze=0.20, ink=170, span=50),
    'qilin':   dict(out='qilin-full.png',   mode='原位', haze=0.16, ink=135, span=50),
    # ⭐ 2026-10-05 第四批两朝（隋龙舸／清风雷行龙，REQ-2026-10-05-05）：
    #   ⚠️ 与第三批的**关键差别**：第三批是「一团浓云与兽体粘连」（云浓 35–40%），本文两朝的
    #      淡墨是**通幅铺开的水纹／风弧**（浓墨只 15–17%，与商 12.1% 同档）⇒ 没有硬边问题，
    #      但**k 不能照抄 0.16**：水纹本身极淡（L≈235–245），k=0.16 压完 ≈251 等于抹掉，
    #      成品会退回「白纸上贴一条船/一条龙」。⇒ 本批 k 取 0.45–0.55，让通幅淡纹留住。
    'longge':   dict(out='longge-full.png',   mode='原位', haze=0.45, ink=200, span=60,
                     zoom=0.98, shift=76, xshift=160),
    'fenglong': dict(out='fenglong-full.png', mode='原位', haze=0.45, ink=200, span=60),
    # ⭐ 2026-10-09 第五批三朝（清·甪端／元·六月飞雪／觉醒年代·铅字肌理，REQ-2026-10-09-08）：
    #   ⚠️ 与第四批的差别：这三张的主体**本身就是水墨主体**（不是通幅水纹），
    #      淡墨占比 甪端 13.9%／寒林 22.4%／铅字 45.7%（抬白后 <235 口径）。
    #      ⇒ 仍走 mode='原位'（无抠图硬边风险）；k 先按 0.45 试，按成品再收。
    #   ⚠️ 铅字是**满幅网格**（唯一一张「无单一主体」的底纹）⇒ ink 收到 180，
    #      只保留最浓的格线，避免满幅格子压住文字区。
    #   ⭐ 2026-10-09 用户「清朝往右边来」⇒ 加 `xshift=140`：甪端兽头**朝左**（独角在左、
    #      尾向右上卷），原构图落在中偏右；右移 140 后兽头更靠右、左侧留白更整。
    #      ⚠️ 上限由**右列引文区**决定（底纹坐标 x1238–1437 ＝ 成品竖排引文列）：
    #         再往右尾巴与云脚就越过 1238 压到引文字上（实测见 §十四）。
    'luduan':   dict(out='luduan-full.png',   mode='原位', haze=0.45, ink=200, span=60,
                     xshift=140),
    #   ⚠️ 寒林主体（抠图 bbox）y378–983，下缘 983 直接压进品牌区（§八 要求 0%）。
    #      跨度 605px < 净空 658.8px ⇒ **只上移、不缩放**：983→758 需上移 225px，
    #      移后顶部 378−225=153 > 99.2（§六 不裁头）✓ ⇒ shift=225 一次到位。
    #      ⚠️ 上移 225 后底部露 225px 补白，raw 的雪地淡墨一直延到原图底边 ⇒ 补白
    #         与原内容之间出现**横向分界线**（成品里肉眼可见）⇒ fade=150 羽化抹平。
    'feixue':   dict(out='feixue-full.png',   mode='原位', haze=0.45, ink=200, span=60,
                     shift=225, fade=150),
    #   ⚠️ 铅字这一张前后生了 4 版才定：①泼墨方块（墨 45.7% 太脏）②稀疏孤点（太空）
    #      ③满幅方阵（= 格子布，且中间「觉醒年代」4 个大字本身就是方块 ⇒ 打架）
    #      ④**一托盘字模 + 大留白**（采用，浓墨 6.3%／淡墨 22.2%）。
    #      ③的 raw 留档为 `qianzi-grid-raw.png`，另两版实物见 _gen-20261009/。
    #   🔴 ④直接 k=0.45 上机时整幅墨 **14.7%**（别朝 6–7%）、字区 35.4%，托盘太实太大，
    #      与中间 4 个方块大字正面打架 ⇒ **缩小 + 羽化**：zoom0.75 把托盘退成「背景的一块墨」，
    #      fade=120 抹掉几何步的补白边界。
    #   ⭐ 2026-10-09 用户「觉醒年代镜像一下」⇒ 加 `flip=True`：字模托盘由**左下**翻到**右下**，
    #      与中间 4 个方块大字左右错开（原来是「左上托盘 + 中间方块」同侧压叠）。
    #      ⚠️ 镜像后托盘 bbox x[385,1318]（翻转＝缩放/居中可交换，等价于终图翻转）；
    #         右缘 1318 与右列引文区（x1238–1437）重叠 80px ⇒ 渲成品复核引文叠墨。
    'qianzi':   dict(out='qianzi-full.png',   mode='原位', haze=0.45, ink=200, span=60,
                     zoom=0.75, shift=70, fade=120, flip=True),
    #   ⚠️ `zoom`/`shift`（第四批新增的几何步，见 §十二）：
    #      隋的 raw 主体太高太低（压淡后内容 y183–846 = 663px），而「不裁头」与「不压品牌区」
    #      之间的可用净空只有 658.8px ⇒ 必须等比缩 0.98 再把内容整体上移 76px。
    #      清不需要（s=1.00 时品牌区已 0.00%）。
    #   ⭐ 2026-10-06 用户反馈「隋的船往右边靠，不要放正中间」⇒ 加 `xshift=160`（见 §十三）：
    #      **成品横向没有 overflow**（cover 后 1536→1920 正好铺满，不裁左右）⇒
    #      `object-position` 的 X 分量在成品里完全无效，**想左右挪只能烘进底纹**。
    #      实测：实墨质心 x 1064→1268（幅宽 1920，中心 960）；再大到 300 会把右列引文
    #      叠墨由 21% 拉到 52%，且船帆贴右缘 ⇒ **160 定为上限**。
    #   `flip=True` 可水平镜像（治「方向反了」，0 积分；见 §十三）。
    # ── 商周：⚠️ **不走本产线**（2026-10-05 用户定「商周不动了，切回原版，只做原版大小的
    #   稍微下移」）。商＝`xuanniao-raw.png`（原始生图，无雾底）；周＝09-29 老脚本
    #   `gen-phoenix-full.py` 的平铺云版 `phoenix-full.png`（备份在 02-素材/底纹/
    #   `_备份-20261005-商周改版前/`）。下移由 gen-evolution.py 的 `tex_pos`
    #   （CSS object-position）在成品里挪可见窗口完成，**不要**用本脚本重合成。
}

# ⚠️ 两条路都试过了，结论记在这里，后面 12 朝别再重复踩：
#   ① mode='平铺'（贴片网格平铺，= 凤凰当年的做法）：**龙马/灵龟这组图不合适**。
#      贴片是矩形，平铺后**矩形边界肉眼可见**，整幅变成"格子布/脏灰"；开大模糊又会
#      糊成大片均匀灰块（实测云区覆盖 95%、中位 236 → 看着根本没有云）。
#      姓氏线 2026-10-04 换真云纹失败也是同一个根因（矩形贴片成灰块）。
#   ② mode='雾'（**本组采用**）：雾底直接用生图自带的那团云（整幅抬白后按 haze 权重
#      反相压淡），不做任何平铺 ⇒ 无网格伪影、云团形状天然合理、与主体同源。
#      代价是没有"通幅云海"，只有原图左侧那一团淡云 —— 与**商（玄鸟直接用 raw）**同档，
#      正是"与商周同源"想要的结果。
# ⚠️ 取景框不能凭目测框「看着有云的那块」：2026-10-04 实测同一张图，
#    y340–660 那块云对比度只有 21（几乎全白纸）→ 平铺出来是"整幅均匀的灰"，
#    云区覆盖 95%、中位 236，看着根本没有云。换成 y470–770 那块（对比 62）才对。
#    换框后云区覆盖降到 ~46%、P5 降到 ~205，与已上线的 phoenix-full.png 同档。


# ⭐ 兽体窗口（2026-10-05 第三批实测新增）：**仅这三张用**，九朝不给窗口＝行为不变。
#   🔴 为什么需要：本批生图的云雾**比九朝浓得多**（体积墨 35–40% vs 九朝 ~12%），
#      205 阈值抠主体时云雾大片被并进来 ⇒ mask 均值被拽到画面中心 ⇒ place() 按错的锚点
#      落位，**主体上半身被裁**（2026-10-05 实测三张全部裁头 100–140px）。
#   ⚠️ 别用「降低阈值」代替窗口：鹤身是淡墨（L>212），降阈值会把鹤一起丢掉。
#      ⇒ 正解＝用**空间窗口**先排除左半幅与下方的大片云雾，再在窗口内跑原有抠取逻辑。
#      窗口＝目视 raw 主体的外接范围（留余量），坐标是**底纹原图 1536×1024** 系。
WINDOW = {
    'gongshi': (620, 0, 1536, 660),
    'ruihe':   (520, 0, 1240, 650),
    'qilin':   (580, 0, 1536, 640),
}


def build_key(slug):
    """抠主体 → 返回 (抬白后的灰度图 L, 主体alpha, 主体x/y坐标)"""
    a0 = np.asarray(Image.open(D / f'{slug}-raw.png').convert('L')).astype(float)
    base = np.percentile(a0, 92)
    L = np.clip(a0 + (255 - base), 0, 255)          # 纸色抬白（顺带抬掉右下角水印）

    m = L < 205
    if slug in WINDOW:                              # 兽体窗口：窗外一律不算主体
        x0, y0, x1, y1 = WINDOW[slug]
        keep_win = np.zeros(L.shape, bool)
        keep_win[y0:y1, x0:x1] = True
        m &= keep_win
    lab, n = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    big = int(np.argmax(sizes)) + 1
    cy0, cx0 = ndimage.center_of_mass(m, lab, big)
    # 兽体窗口模式收紧邻近块判据（窗口内不会有大片孤立云雾，收紧可避免把云脚当主体）
    _near = 450 if slug in WINDOW else 700
    _minsz = 3000 if slug in WINDOW else 4000
    keep = [big]
    for i, s in enumerate(sizes):
        if s < _minsz or i + 1 == big:
            continue
        cyi, cxi = ndimage.center_of_mass(m, lab, i + 1)
        if (cyi - cy0) ** 2 + (cxi - cx0) ** 2 <= _near ** 2:
            keep.append(i + 1)
    print('  抠主体：最大块 %d px，邻近大块保留 %d 个（共 %d 块）'
          % (sizes[big - 1], len(keep) - 1, len(keep)))
    mm = np.isin(lab, keep)
    mm = ndimage.binary_fill_holes(ndimage.binary_dilation(mm, iterations=4))
    ys, xs = np.where(mm)
    print('  主体mask：bbox y[%d,%d] x[%d,%d] 均值 y=%.1f x=%.1f（place 锚点就是这两个均值）'
          % (ys.min(), ys.max(), xs.min(), xs.max(), ys.mean(), xs.mean()))
    alf = np.clip((252 - L) / 30.0, 0, 1) * mm
    if slug in WINDOW:
        # ⚠️ 窗口模式下 mm 只覆盖主体+脚边云，**边界会变成肉眼可见的直边**
        #    （2026-10-05 实测：贡狮右下出现直角裁切感）。
        #    🔴 σ=3 不够用：mm 把「脚边云雾」也带进来了，那团云本身墨浓、边界锐利，
        #       3px 过渡在成品里仍是一道硬线。改用 **σ=12**（成品 ≈15px 渐变），
        #       视觉上变成云雾自然淡出。九朝不给窗口、mm 覆盖整片云雾，边界落在画面外，
        #       所以原先没暴露这个问题。
        alf = alf * ndimage.gaussian_filter(mm.astype(float), 12.0)
    return L, alf, ys, xs


def build_patch(L, box):
    """从原图取云雾贴片（抬白 + 柔化，避免把浓墨斑一起放大）"""
    x0, y0, x1, y1 = box
    patch = L[y0:y1, x0:x1]
    patch = np.clip(patch, 216, 255)
    patch = ndimage.gaussian_filter(patch, 5.0)
    pa = np.clip((254 - patch) / 34.0, 0, 1)
    return patch, pa


def make_placer(L, alf, ys, xs, scale, ax, ay):
    """主体按 scale 缩放、质心锚定到 (ax·W, ay·H)，允许溢出画布（压迫感来自裁切）。
    返回 place(deepen) → (灰度片, alpha片, 画布切片, 全幅mask, box)

    ⚠️ 质心是**墨迹质心**（墨量加权），不等于主体外接框中心：长尾、飞白拖笔会把质心
       往后拽。凤凰的长尾使质心比视觉中心靠右下 —— 所以别拿本函数算出来的质心
       去反推"主体看着在哪"。
    """
    H, W = L.shape

    def place(deepen):
        nw, nh = round(W * scale), round(H * scale)
        gs = np.asarray(Image.fromarray(L.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float)
        als = np.asarray(Image.fromarray((alf * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float) / 255
        gs = np.clip(255 - (255 - gs) * deepen, 0, 255)
        bx = round(ax * W - xs.mean() * scale)      # 缩放后质心落在 (ax*W, ay*H)
        by = round(ay * H - ys.mean() * scale)
        dx0, dy0 = max(0, bx), max(0, by)
        dx1, dy1 = min(W, bx + nw), min(H, by + nh)
        sx0, sy0 = dx0 - bx, dy0 - by
        sx1, sy1 = sx0 + (dx1 - dx0), sy0 + (dy1 - dy0)
        mm_full = np.zeros((H, W), bool)
        mm_full[dy0:dy1, dx0:dx1] = als[sy0:sy1, sx0:sx1] > 0.08
        return (gs[sy0:sy1, sx0:sx1], als[sy0:sy1, sx0:sx1],
                (dx0, dy0, dx1, dy1), mm_full, (bx, by, nw, nh))

    return place


def make_composer(slug, L, alf, ys, xs, patch, pa, scale, ax, ay):
    H, W = L.shape
    PH, PW = patch.shape
    place = make_placer(L, alf, ys, xs, scale, ax, ay)

    def stamp(cv, cx, cy, sc, fx, fy, w):
        nh, nw = int(PH * sc), int(PW * sc)
        g = np.asarray(Image.fromarray(patch.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float)
        al = np.asarray(Image.fromarray((pa * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)).astype(float) / 255
        if fx:
            g, al = g[:, ::-1], al[:, ::-1]
        if fy:
            g, al = g[::-1, :], al[::-1, :]
        x0, y0 = int(cx - nw / 2), int(cy - nh / 2)
        sx0, sy0 = max(0, x0), max(0, y0)
        sx1, sy1 = min(W, x0 + nw), min(H, y0 + nh)
        if sx1 <= sx0 or sy1 <= sy0:
            return
        gg = g[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0]
        aa = al[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] * w
        sub = cv[sy0:sy1, sx0:sx1]
        cv[sy0:sy1, sx0:sx1] = sub * (1 - aa) + gg * aa

    def compose(weight, grid, deepen, levels):
        mg, ma, (dx0, dy0, dx1, dy1), mm_full, box = place(deepen)
        gx, gy, scales, blur = GRIDS[grid]
        cv = np.full((H, W), 255.0)
        lo, hi, darkest = levels
        i = 0
        for r, yy in enumerate(gy):
            for xx in gx:
                stamp(cv, xx + (70 if r % 2 else 0), yy,
                      scales[i % len(scales)], i % 3 == 0, i % 2 == 1, weight)
                i += 1
        cv = ndimage.gaussian_filter(cv, blur)
        t = np.clip((cv - lo) / (hi - lo), 0, 1)
        cv = 255 - t * (255 - darkest)
        # 主体附近留白：⚠️ σ 必须按**主体规模**定，不能照抄凤凰的 90。
        #   凤凰主体小，σ90 只影响它周围一圈；龙马/灵龟主体宽度是凤凰的 ~2 倍，
        #   σ90 会把大半个画面都削白 → 云雾全看不见（实测可见云几乎为 0）。
        #   ⇒ 收到 45（≈影响半径 90px），并在下面按主体宽度自适应兜底。
        sig = HALO_SIG
        halo = ndimage.gaussian_filter(mm_full.astype(float), sig)   # 主体附近留白
        cv = cv + (255 - cv) * np.clip(halo * HALO_W, 0, 1)
        sub = cv[dy0:dy1, dx0:dx1]
        cv[dy0:dy1, dx0:dx1] = sub * (1 - ma) + mg * ma
        return cv, box, mm_full

    return compose


def compose_haze(L, alf, k, deepen, place):
    """同源薄雾：纸底与云团整体压淡成雾，主体按 scale 缩放后锚定叠回（浓墨不减淡）。

    σ/网格全都不需要 —— 因为雾底就是生图自带的那团云，天然没有矩形边界。
    k 越小越淡（0.10–0.18）；主体单独用 alpha 叠加，所以纸变淡、墨不变淡。
    雾底用**原尺寸**（不跟着主体缩放），云团位置才与生图一致。
    """
    H, W = L.shape
    # ⚠️ 雾底**必须把原主体位置抹掉**：否则雾底里"原来那只大兽"会和缩放后叠上去的
    #    实体形成**重影**（2026-10-04 实测，一眼就能看出来）。做法＝主体 mask 膨胀
    #    后做成平滑权重，让该处的雾权重降到 0（把原兽抬白），云团照旧保留。
    m = alf > 0.05
    keep_cloud = 1.0 - ndimage.gaussian_filter(
        ndimage.binary_dilation(m, iterations=40).astype(float), 25)
    cv = 255 - (255 - L) * (k * keep_cloud)
    cv = np.clip(255 - (255 - cv) * deepen, 0, 255)      # 整幅提浓（一般 deepen≈1）
    mg, ma, (dx0, dy0, dx1, dy1), mm_full, box = place(1.0)
    sub = cv[dy0:dy1, dx0:dx1]
    cv[dy0:dy1, dx0:dx1] = sub * (1 - ma) + mg * ma
    return cv, box, mm_full


def load_white(slug):
    """只做纸色抬白，不抠主体（原位模式用）"""
    a0 = np.asarray(Image.open(D / f'{slug}-raw.png').convert('L')).astype(float)
    base = np.percentile(a0, 92)
    return np.clip(a0 + (255 - base), 0, 255)


def zoom_shift(cv, zoom=1.0, shift=0.0, xshift=0.0, flip=False, fade=0.0):
    """⭐ 原位模式的几何步（2026-10-05 第四批新增）：等比缩放 + 位移 + 可选水平镜像。

    🔴 为什么需要：raw 的构图未必落在「不裁头」(§六) 与「不压品牌区」(§八) 之间的净空里。
    隋·龙舸就是——压淡后内容 y183–846（663px），而净空只有 99.2→758（658.8px），
    差 4px 就放不下 ⇒ 只能等比缩一点点再整体上移。
    缩放比由 `_solve-geom-4th.py` 解出：s ≤ (758−99.2)/(yb−yt)，t 取两端余量均分的中点。

    ⭐ 2026-10-06 增补 `xshift`（水平位移）与 `flip`（水平镜像）：
      · 成品横向**没有 overflow**（cover 缩放后 1536→1920 正好铺满），所以
        `object-position` 的 X 分量在这里**完全无效**（上下可以用 tex_pos，左右不能）。
        ⇒ 想把主体往右挪，**只能烘进底纹本身**。
      · `flip` 用于纠正生图的方向（用户反馈「清朝的龙反了」）：镜像后头朝左。
        注意 fileName:// 原地reduce 的涟漪/风弧也会被镜像，观感对称，无副作用。

    ⭐ 2026-10-09 增补 `fade`（上下羽化，专治补白边界）：
      🔴 上移 shift 后，画面底部会露出 `H−nh+shift` 行纯白补白，而 raw 的内容（淡墨）
         一直延伸到原图边缘 ⇒ 补白与原内容之间**出现一条横向分界线**（2026-10-09 元·寒林
         实测，在成品里肉眼可见）。做法＝缩放后的图**上下各 fade 行渐变淡出到白**，
         让边界处已经是白纸 ⇒ 与补白无缝。fade=0 时行为完全不变（longge/fenglong 不受影响）。

    ⚠️ 用**白纸**(255) 填新画布：本产线的底纹纸色已被抬到 255，所以四周补白
       **肉眼无边界**；反过来若补灰就会露边。
    """
    if flip:
        cv = cv[:, ::-1]
    H, W = cv.shape
    nw, nh = round(W * zoom), round(H * zoom)
    im = Image.fromarray(cv.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
    if fade:
        a = np.asarray(im).astype(float)
        f = int(min(fade, nh // 3))
        ramp = np.ones(nh)
        ramp[:f] = np.linspace(0, 1, f)
        ramp[-f:] = np.linspace(1, 0, f)
        a = 255 - (255 - a) * ramp[:, None]
        im = Image.fromarray(a.astype(np.uint8))
    out = Image.new('L', (W, H), 255)
    out.paste(im, ((W - nw) // 2 + int(round(xshift)), -int(round(shift))))
    return np.asarray(out).astype(float)


def compose_inplace(L, mm, k, ink=130.0, span=50.0):
    """⭐ 原位减云（2026-10-05 第三批新增，**不缩放、不位移、不抠图**）。

    🔴 为什么需要这条路：本批生图的**云雾与兽体粘连**（狮/麟的脚踩在浓云上）。
    走雾模式时必须把「兽 + 脚边云」抠成一块再缩放叠回，而那块云的**下缘边界**
    在成品里是一条 1px 硬线（实测 y=701 处灰度 207→242 直接跳变，羽化 σ12 也救不回，
    因为边界外是白纸、alpha 天然为 0）。窗口内还有第二条硬边。
    ⇒ 放弃「抠+缩放」，改为**让云原地变淡、墨原地保留**：没有位移 ⇒ 没有重影。

    保留权重 = 浓墨权重 × 「与主体相连」的平滑 mask：
      ① `clip((ink−L)/span)` —— 只有墨够浓才保留（淡云一律走压淡）；
      ② `gaussian(mm, 20)`   —— **孤立的云团不保留**。
         🔴 少了这一项，云团里最浓的那几坨（L<135）会被当"浓墨"留下来，
            在画面中间形成一坨黑云压住文字区（2026-10-05 实测贡狮/麒麟都有）。
      ③ 用平滑 mask（σ20）而不是硬 mask ⇒ **边界不会出现硬线**（这是本方案的关键）。
    ⚠️ 代价：主体位置＝生图原始位置，**成品里的上下取景改由 gen-evolution.py 的
       `tex_pos`（object-position）承担**（同商周 §九 的做法）。
    """
    cv = 255 - (255 - L) * k
    w = np.clip((ink - L) / span, 0, 1)
    body = ndimage.gaussian_filter(mm.astype(float), 20.0)
    body = np.clip(body * 1.6, 0, 1)
    w = w * body
    return cv * (1 - w) + L * w


def render(slug, out=None, opt=None, scale=None, ax=None, ay=None, deepen=None,
           mode=None, haze=None, patch=None):
    cfg = TEX[slug]
    opt = opt or cfg.get('opt')
    out = out or cfg['out']
    mode = mode or cfg.get('mode', '平铺')

    if mode == '原位':
        k = haze if haze is not None else cfg.get('haze', 0.28)
        ink = float(cfg.get('ink', 130))
        span = float(cfg.get('span', 50))
        L, alf, ys, xs = build_key(slug)          # 借它抠「与主体相连的墨」做保留权重
        mm = alf > 0.02
        zoom = float(os.environ.get('TEX_ZOOM', cfg.get('zoom', 1.0)))
        shift = float(os.environ.get('TEX_SHIFT', cfg.get('shift', 0.0)))
        xshift = float(os.environ.get('TEX_XSHIFT', cfg.get('xshift', 0.0)))
        flip = str(os.environ.get('TEX_FLIP', cfg.get('flip', ''))).lower() in ('1', 'true', 'yes')
        fade = float(os.environ.get('TEX_FADE', cfg.get('fade', 0.0)))
        geo = '' if (zoom == 1.0 and not shift and not xshift and not flip and not fade) else \
            f' ｜ 几何 zoom={zoom:.3f} shift=↑{shift:.0f}px xshift=→{xshift:.0f}px flip={flip} fade={fade:.0f}'
        print(f'== {slug} → {out}  原位减云 k={k:.2f} 墨阈={ink:.0f}±{span:.0f}{geo}')
        cv = compose_inplace(L, mm, k, ink, span)
        if zoom != 1.0 or shift or xshift or flip or fade:
            cv = zoom_shift(cv, zoom, shift, xshift, flip, fade)
        _report(slug, cv, None, None, W=None, H=None)
        Image.fromarray(cv.astype(np.uint8), 'L').convert('RGB').save(D / out)
        Image.fromarray(cv.astype(np.uint8)).resize((760, 507), Image.LANCZOS).save(f'/tmp/tex-{slug}.png')
        return D / out

    scale = scale if scale is not None else float(os.environ.get('TEX_S', cfg['scale']))
    ax = ax if ax is not None else float(os.environ.get('TEX_AX', cfg['ax']))
    ay = ay if ay is not None else float(os.environ.get('TEX_AY', cfg['ay']))

    L, alf, ys, xs = build_key(slug)
    H, W = L.shape

    if mode == '雾':
        k = haze if haze is not None else cfg.get('haze', 0.13)
        dp = deepen if deepen is not None else 1.0
        print(f'== {slug} → {out}  同源薄雾 haze={k:.2f}  S={scale:.2f} '
              f'质心锚定 ({100*ax:.1f}%, {100*ay:.1f}%)')
        place = make_placer(L, alf, ys, xs, scale, ax, ay)
        cv, box, mm_full = compose_haze(L, alf, k, dp, place)
    else:
        w, grid, dp0, lv = OPTS[opt]
        dp = deepen if deepen is not None else dp0
        print(f'== {slug} → {out}  S={scale:.2f} 质心锚定 ({100*ax:.1f}%, {100*ay:.1f}%) 档={opt}')
        patch_box = patch or cfg['patch']
        patch_arr, pa = build_patch(L, patch_box)
        compose = make_composer(slug, L, alf, ys, xs, patch_arr, pa, scale, ax, ay)
        cv, box, mm_full = compose(w, grid, dp, lv)
    _report(slug, cv, box, mm_full, W, H)
    Image.fromarray(cv.astype(np.uint8), 'L').convert('RGB').save(D / out)
    Image.fromarray(cv.astype(np.uint8)).resize((760, round(760 * cv.shape[0] / cv.shape[1])),
                                                Image.LANCZOS).save(f'/tmp/tex-{slug}.png')
    return D / out


def _report(slug, cv, box, mm_full, W, H):
    cloud = cv[(cv < 252) & (cv > 60)]
    if mm_full is None:
        print('   画面可见 %.1f%% | 云中位灰度 %.0f | 主体＝原位（取景交给 tex_pos）'
              % (100 * ((cv < 252) & (cv > 60)).mean(),
                 np.median(cloud) if cloud.size else 255))
        return
    ys2, xs2 = np.where(mm_full)
    print('   画面可见 %.1f%% | 云雾中位灰度 %.0f | 主体落位 %s | 占位 x[%.0f%%,%.0f%%] y[%.0f%%,%.0f%%]'
          % (100 * ((cv < 252) & (cv > 60)).mean(),
             np.median(cloud) if cloud.size else 255, box,
             100 * xs2.min() / W, 100 * xs2.max() / W,
             100 * ys2.min() / H, 100 * ys2.max() / H))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {}
    for a in sys.argv[1:]:
        if a.startswith('--'):
            k, _, v = a[2:].partition('=')
            flags[k] = v
    for s in args:
        render(s,
               out=flags.get('out'),
               opt=flags.get('opt'),
               scale=float(flags['scale']) if 'scale' in flags else None,
               ax=float(flags['ax']) if 'ax' in flags else None,
               ay=float(flags['ay']) if 'ay' in flags else None,
               deepen=float(flags['deepen']) if 'deepen' in flags else None,
               mode=flags.get('mode'),
               haze=float(flags['haze']) if 'haze' in flags else None)
