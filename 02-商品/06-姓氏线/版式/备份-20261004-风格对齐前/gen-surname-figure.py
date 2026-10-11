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


def prep(char, order, src=None, crop=CROP, edge=EDGE, outdir=None, density=1.0):
    """生图源 → 底纹素材（**RGBA 墨迹蒙版**）。返回素材路径。

    crop : (x0,y0,x1,y1) 或 None（不裁）。默认沿用横构图占位图的值，换构图必须显式传。
    edge : 左右渐隐宽度 px，0 = 关闭（素材自身已有留白时不需要）。
    outdir : 输出目录，默认 FIGDIR（正式素材位）；试版对比时可指向别处不覆盖正式件。
    density : 墨色浓度倍数（alpha 线性缩放），默认 1.0。
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
    if density != 1.0:                       # 素材层提浓（不改 CSS opacity，见函数 docstring）
        alpha = np.clip(alpha.astype(np.float32) * density, 0, 255).astype(np.uint8)
    rgb = np.zeros(g.shape + (3,), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 26, 26, 24
    odir = pathlib.Path(outdir) if outdir else FIGDIR
    odir.mkdir(parents=True, exist_ok=True)
    dst = odir / f'figure-{order:03d}-{char}.png'
    Image.fromarray(np.dstack([rgb, alpha]), 'RGBA').save(dst)
    print(f'素材 {dst}  {out.size[0]}×{out.size[1]}  底色底 {base:.0f}→255\n'
          f'    墨量(g<200) {100 * (g < 200).mean():.1f}%  |  全透明像素 '
          f'{100 * (alpha == 0).mean():.1f}%（偏置清除前 {100 * (raw <= BIAS).mean():.1f}%）\n'
          f'    crop={crop or "不裁"}  edge={edge}（左右渐隐）  density={density}×  源图 {im.size[0]}×{im.size[1]}'
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
    ap.add_argument('--force-prep', action='store_true',
                    help='素材已存在时也按 --crop/--edge/--density 重做（否则这些参数不生效）')
    ap.add_argument('--sync-mac', action='store_true',
                    help='由 std 模板同步生成 mac 模板（改完 std 版式后必跑）')
    a = ap.parse_args()

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
        prep(a.prep, item['order'], a.src, crop, edge, a.prep_out, a.density)
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
            fig = prep(ch, item['order'], a.src, crop, edge, a.prep_out, a.density)
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
