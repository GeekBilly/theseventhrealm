#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A 线「字形演变」· 手机竖版生成器（v2 · 2026-10-09 起支持 iOS / Android 双画幅）。

板式为 `模板-朝代-v9-竖版.html`（唯一版式出处，本脚本不持任何坐标/字号以外的数值）。

🔴 2026-10-09 用户定：**客户下载 = iOS + Android 各 16 张，共 32 张**（「新版的」）。
   画幅不再是单一 1080×1920，而是按机型原生比例出两套：
     ios      1179×2556   iPhone 15/16/17 Pro 原生（19.5:9）
     android  1080×2400   当代安卓主流（20:9）
     std      1080×1920   旧版 16:9（2026-10-09 起**停发**，仅供对照／回归）
   ⇒ 旧的那 16 张 1080×1920 **不再进客户包**。

 画幅怎么缩放（⚠️ 不是等比，两套比例不同）：
   纵向锚点（title/triple/quote/colophon/era/brand 的 top|bottom）× ky = H/1920
   横向一切（left|right|width|height/字号/字距/间距）              × kx = W/1080
   ⇒ 屏更高就纵向拉长画心，字按屏宽同比放大，视觉密度不变。
   字号上限 SIZE_CAP × kx；每格 cap/sub 占位 OVERHEAD × kx；分隔线占位 DIV ≈ 49 基本不变。
   ⭐ std 变体（kx=ky=1）必须与 v1 产出**逐字相同** —— 这是缩放逻辑的回归判据。

用法：
    python3 gen-evolution-phone.py                 # 16 朝 × (ios + android) = 32 个 HTML
    python3 gen-evolution-phone.py --variant ios    # 只出 iOS
    python3 gen-evolution-phone.py shang zhou      # 指定朝（两套都出）
    python3 gen-evolution-phone.py --with-texture  # 带底纹对照样张（手机版常态是无底纹）
    python3 gen-evolution-phone.py --only-textured # 只出「已有自有底纹」的朝（横版视角）

产出：02-商品/05-承接站/样张/evolution-{slug}-phone-{ios,android,std}.html
      （PNG 由 shoot-phone.sh 用系统 Chrome 截，本地零积分）

⭐ **手机版＝无底纹**（2026-10-05 用户定：「不要底纹手机版」）。
   理由写在形式上：手机屏是竖长条，底纹被裁成窄带后既不成形又要压字；
   且 A 线「每期须有自有底纹才允许上架」约束的是**主商品（横版）**，
   手机版作为同一件商品的**另一种画幅**，不受该条约束。
   ⇒ 需要带底纹的对照样张时用 `--with-texture`（产 `*-phone-{v}-tex.html`）。

🔴 **2026-10-09 用户口径（覆盖 10-09 早前的收紧）**：手机版就是**主交付物**
   （客户下载只拿手机竖版），所以 **16 朝全部出手机版**，不再按「有无底纹」过滤。
   ⇒ 元／觉醒年代虽然没有底纹（横版也因此未出成品），但它们的手机版**照出**。
"""
import importlib.util
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parents[2]
OUT = ROOT / '02-商品/05-承接站/样张'
TPL = HERE / '模板-朝代-v9-竖版.html'
SEAL = ROOT / '02-商品/02-素材/底纹/seal.png'

# ── 载入竖版/横版共用数据源 ────────────────────────────────
_spec = importlib.util.spec_from_file_location('ge_src', HERE / 'gen-evolution.py')
ge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ge)
ERAS, A = ge.ERAS, ge.A
CELL_CAP, CELL_SUB, BRUSH_CAP = ge.CELL_CAP, ge.CELL_SUB, ge.BRUSH_CAP

SLOTS = ('tag', 'title', 'triple', 'quote', 'brand', 'era')
SLOT_RE = {k: re.compile(r'<!--S:%s-->(.*?)<!--E:%s-->' % (k, k), re.S) for k in SLOTS}

# ── 画幅变体（基准＝模板写死的 1080×1920）──────────────────
BASE_W, BASE_H = 1080, 1920
VARIANTS = {
    'ios':     (1179, 2556),   # iPhone 15/16/17 Pro 原生 · 19.5:9
    'android': (1080, 2400),   # 当代安卓主流 · 20:9
    'std':     (1080, 1920),   # 旧版 16:9 · 已停发，仅供对照
}
DEFAULT_VARIANTS = ('ios', 'android')

# ── 纵向版式预算（基准值，与模板 .triple 的 top/bottom 必须一致）──
TOP_B, BOTTOM_B = 470, 330     # .triple{top:470px;bottom:330px}
DIV_B = 49                     # 一道分隔线占位：height1 + margin 24*2
OVERHEAD_B = 58                # 每格 cap(10+20*1.4) + sub(6+15*1.4)
LH = 1.06                      # 行高（相对值，不随画幅变）
SIZE_CAP_B = 300               # 字号上限（再大就顶到画面横向安全区了）

# 缩放属性表：纵向锚点走 ky，其余走 kx
V_PROPS = ('top', 'bottom')
H_PROPS = ('left', 'right', 'width', 'height', 'font-size', 'letter-spacing',
           'text-indent', 'gap',
           'margin-top', 'margin-bottom', 'margin-left', 'margin-right')
_RE_V = re.compile(r'\b(%s):(-?\d+(?:\.\d+)?)px' % '|'.join(V_PROPS))
_RE_H = re.compile(r'\b(%s):(-?\d+(?:\.\d+)?)px' % '|'.join(H_PROPS))
_RE_M = re.compile(r'\bmargin:(-?\d+(?:\.\d+)?)px')     # shorthand 只缩第一个值


def geometry(variant):
    """变体名 → 画幅几何（含两个缩放因子与派生预算）。"""
    if variant not in VARIANTS:
        raise SystemExit(f'未知画幅变体 {variant}（可选：{"/".join(VARIANTS)}）')
    W, H = VARIANTS[variant]
    kx, ky = W / BASE_W, H / BASE_H
    top, bot = round(TOP_B * ky), round(BOTTOM_B * ky)
    return {'v': variant, 'W': W, 'H': H, 'kx': kx, 'ky': ky,
            'top': top, 'bottom': bot, 'avail': H - top - bot,
            'div': round(1 * kx) + 48,
            'overhead': OVERHEAD_B * kx,
            'cap': SIZE_CAP_B * kx}


def cell_size(n, g):
    """格数 → 字号：claims 可用高均分，扣掉 cap/sub 后封顶（上限随屏宽同比放大）。"""
    return max(60, min(g['cap'], ((g['avail'] - g['div'] * (n - 1)) / n - g['overhead']) / LH))


def scale_style(style, g):
    """把模板 style 从 1080×1920 基准缩放到目标画幅。

    ⚠️ 画幅那两处（html,body 与 .stage）先换占位符，否则会被通用正则二次缩放。
    """
    kx, ky = g['kx'], g['ky']
    t = style.replace('width:1080px;height:1920px', 'width:__W__px;height:__H__px')

    def rep(m, k):
        return '%s:%dpx' % (m.group(1), round(float(m.group(2)) * k))

    t = _RE_V.sub(lambda m: rep(m, ky), t)
    t = _RE_H.sub(lambda m: rep(m, kx), t)
    t = _RE_M.sub(lambda m: 'margin:%dpx' % round(float(m.group(1)) * kx), t)
    return t.replace('__W__', str(g['W'])).replace('__H__', str(g['H']))


def vcol(text, fs=None):
    """竖排列：逐字一个 <span>（出处首末的《》要旋转，由调用方给 .rot）。"""
    st = f' style="font-size:{fs}px"' if fs else ''
    return f'<div class="vc"><span{st}>' + '</span><span>'.join(text) + '</span></div>'


def vsrc(src):
    """出处列：.$$

    《》旋转 90°，其余逐字竖排。"""
    out = []
    for ch in src:
        cls = ' class="rot"' if ch in '《》' else ''
        out.append(f'<span{cls}>{ch}</span>')
    return '<div class="vc src">' + ''.join(out) + '</div>'


def build_triple(e, size, g):
    """画心：竖排。单字＝碑刻宋｜毛笔 两格；商周多一格古文字；多字＝一字一格。"""
    cs = e['char']
    n = len(cs)
    fm = e.get('char_fonts')
    an = e.get('ancient')
    kx = g['kx']
    style = f'font-size:{size:.0f}px;line-height:{LH}'
    # 朱砂点：right 随字号/屏宽同比（母版是「点右缘≈墨迹右缘」）
    dot = ('<div class="cinnabar-dot" style="right:%dpx;top:0"></div>\n      '
           % round(-10 * kx))
    capsub = ' style="font-size:%dpx;letter-spacing:%dpx"' % (
        round(18 * kx) if n >= 4 else round(20 * kx), round(5 * kx))

    def cell(cls, char, cap, sub, with_dot=False):
        return (f'    <div class="cell">\n'
                f'      {dot if with_dot else ""}<div class="{cls}" style="{style}">{char}</div>\n'
                f'      <div class="cap"{capsub if n >= 4 else ""}>{cap}</div>'
                f'<div class="sub">{sub}</div>\n'
                f'    </div>')

    if an is not None:
        # 商周：碑刻宋 | 毛笔 | 古文字（顺序与横版一致）
        if an['kind'] == 'img':
            sz = f' style="width:{size:.0f}px;height:{size:.0f}px"'
            ancient = (f'<div class="oracle-box"><img class="oracle-glyph" '
                       f'src="file://{an["src"]}"{sz}></div>')
        else:
            fam = (f"font-family:'{an['family']}',serif;" if an.get('family') else '')
            ancient = (f'<div class="oracle-box"><div class="oracle-font" '
                       f'style="{fam}font-size:{size:.0f}px">'
                       f'{an.get("char", cs)}</div></div>')
        return '\n\n    <div class="divider"></div>\n\n'.join([
            cell('song-char', cs, CELL_CAP, CELL_SUB),
            cell('brush-char', cs, BRUSH_CAP, e['brush_sub'], with_dot=True),
            f'    <div class="cell">\n      {ancient}\n'
            f'      <div class="cap">{an["cap"]}</div>\n'
            f'      <div class="sub">{an["sub"]}</div>\n    </div>',
        ])

    if n == 1:
        return '\n\n    <div class="divider"></div>\n\n'.join([
            cell('song-char', cs, CELL_CAP, CELL_SUB),
            cell('brush-char', cs, BRUSH_CAP, e['brush_sub'], with_dot=True),
        ])

    # 多字：一字一格，逐字交替宋/毛（char_fonts，首字宋）
    if fm is not None:
        assert len(fm) == n, f'char_fonts 长度({len(fm)}) ≠ 字数({n})'
    cells = []
    mid = n // 2                       # 朱砂点落画心正中那格（与横版同规则）
    for i, c in enumerate(cs):
        isb = bool(fm) and fm[i] == 'b'
        cells.append(cell(
            'brush-char' if isb else 'song-char', c,
            BRUSH_CAP if isb else CELL_CAP,
            e['brush_sub'] if isb else CELL_SUB,
            with_dot=(i == mid)))
    return '\n\n    <div class="divider"></div>\n\n'.join(cells)


def build(slug, variant='android', with_tex=False):
    e = ERAS[slug]
    g = geometry(variant)
    cs = e['char']
    # 格数：商周＝碑刻宋｜毛笔｜古文字 3 格｜单字＝碑刻宋｜毛笔 2 格｜多字＝一字一格
    n = 3 if e.get('ancient') else (2 if len(cs) == 1 else len(cs))
    size = cell_size(n, g)

    core = e['brand'][:-1] if e['brand'].endswith('™') else e['brand']
    cls_tm = ''
    brand = (f'<div class="brand-cn">{core}<span class="tm">™</span></div>'
             if not core[:1].isascii() else
             f'<div class="brand-en">{core}<span class="tm">™</span></div>')
    del cls_tm

    vals = {
        'tag': e['tag'],
        'title': (f'<div class="triple-title">字 形 演 变 · 三 千 年</div>\n'
                  f'    <div class="triple-hint">{e["hint"]}</div>'),
        'triple': build_triple(e, size, g),
        # ⚠️ 同横版：金句**右起**，`.quote` 是 flex row 左→右排，所以 DOM 要 reversed()
        'quote': vsrc(e['quote_src']) + '\n    ' +
                 '\n    '.join(vcol(c) for c in reversed(e['quote_cols'])),
        'brand': brand + '\n    <div class="brand-url">www.theseventhrealm.com</div>',
        'era': f'<div class="en">{e["en"]}</div><div class="years">{e["years"]}</div>',
    }

    html = TPL.read_text(encoding='utf-8')
    head, sep, body = html.partition('</style>')
    if not sep:
        raise SystemExit('模板缺 </style> —— 无法定位正文')
    head = scale_style(head, g)                      # ⭐ 画幅缩放只动 style 块
    if e.get('texture') and with_tex:
        extra = f' style="object-position:{e["tex_pos"]}"' if e.get('tex_pos') else ''
        body, k = ge.TEX_RE.subn(
            lambda m: m.group(1) + 'file://' + str(e['texture']) + m.group(2) + extra,
            body, count=1)
    else:
        # 无底纹（手机版常态）：把底纹层整条删掉，别留空 src 出碎图占位
        body, k = re.subn(r'[ \t]*<img class="texture"[^>]*>\n?', '', body, count=1)
    if k != 1:
        raise SystemExit('正文未找到 .texture 底纹层 —— 模板可能被改坏')
    html = head + sep + body
    for key, v in vals.items():
        html, k = SLOT_RE[key].subn(lambda m, v=v: v, html, count=1)
        if k != 1:
            raise SystemExit(f'槽位 {key} 替换失败（命中 {k} 次）')
    # 印章/字体绝对路径在 Mac 上一致，无需改写
    out = OUT / f'evolution-{slug}-phone-{variant}{"-tex" if with_tex else ""}.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    print(f'  ✓ {out.name}   {g["W"]}×{g["H"]} · {n}格／字 {size:.0f}px'
          f'{"（带底纹）" if with_tex else "（无底纹）"}')
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    with_tex = '--with-texture' in args
    only_tex = '--only-textured' in args
    if '--variant' in args:
        variants = (args[args.index('--variant') + 1],)
    elif '--std' in args:
        variants = ('std',)
    else:
        variants = DEFAULT_VARIANTS
    want = [a for a in args if not a.startswith('-')
            and a not in VARIANTS and a != 'std']
    # 🔴 不再按「有无底纹」过滤（2026-10-09 用户：手机版＝主交付物，16 朝全出）
    todo = [s for s in (want or list(ERAS)) if (ERAS[s].get('texture') or not only_tex)]
    for v in variants:
        g = geometry(v)
        print(f'手机竖版 {g["W"]}×{g["H"]}（{v}）· 画心可用 {g["avail"]}px · '
              f'{"带底纹（对照样张）" if with_tex else "无底纹（常态）"}：')
        for s in todo:
            build(s, v, with_tex)
