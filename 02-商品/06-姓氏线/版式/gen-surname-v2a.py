#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏线 v2「方向 A · 一姓四体」· 批量出图生成器

版式 100% 来自模板 HTML（模板-姓氏-v11{,-mac}.html），本脚本不持有任何版式数值。
只做三件事：
  1. 数据从 `百家姓-交叉验证.json` 取（拼音 / 简繁 / 源流朝代 / 年份 / 原句）
  2. 出图前逐字做**字形覆盖闸门**（缺字即拦截，绝不让 Chrome 静默回退）
  3. 可选 std / mac 两档模板

用法：
  python3 gen-surname-v2a.py --samples           # 赵 钱 孙 + 李（对照组）
  python3 gen-surname-v2a.py --first 100
  python3 gen-surname-v2a.py 赵 钱 孙

产出：
  _build-v2a/<stem>.html         中间 HTML
  _build-v2a/覆盖审计.log        逐字覆盖报告
"""
import argparse
import json
import pathlib
import re
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
DATA = ROOT / '百家姓-交叉验证.json'
F = ROOT / '02-商品/02-素材/字体'
SEAL = ROOT / '02-商品/02-素材/底纹/seal-hi.png'
BUILD = ROOT / '02-商品/06-姓氏线/版式/_build-v2a'
LOG = BUILD / '覆盖审计.log'

FONTS = {
    'serif': F / 'fonts/NotoSerifSC-Black.ttf',        # 碑刻 / Noto Serif SC Black
    'lishu': F / '隶书/aoyagireisyosimo_ttf_2_01.ttf',  # 隶书 / 青柳隷書（日文，简体覆盖不全）
    'xing':  F / 'fonts/挚芒行.ttf',                    # 行书 / 挚芒行
    'cao':   F / 'fonts/柳建毛草.ttf',                  # 草书 / 柳建毛草
    'msz':   F / 'MaShanZheng.ttf',                     # 落款毛笔
    # 2026-10-03 决策 B：青柳隷書 简繁皆缺的姓，隶书格改用阿里妈妈刀隶体（简体 100/100 覆盖）
    # ⚠️ 官方授权免费商用，但**禁止修改/子集化** —— 本项目只渲染成图，不碰字体文件本身
    'lishu2': F / '隶书/AlimamaDaoLiTi-Regular-简体.ttf',
}
FONT_LABEL = {'serif': ('碑刻', 'Noto Serif'), 'lishu': ('隶书', '青柳隷書'),
              'xing': ('行书', '挚芒行'), 'cao': ('草书', '柳建毛草'),
              'lishu2': ('隶书', '阿里妈妈刀隶体')}
ORDER4 = ('serif', 'lishu', 'xing', 'cao')

# ── 版式：全部写在模板 HTML 里，本脚本不持有任何版式数值 ────────────
# ⚠️⚠️ 唯一的版式权威文件（位置 / 字号 / 字距 / 颜色 都在那里，改版式改那里）：
#     02-商品/06-姓氏线/版式/模板-姓氏-v11.html        （std 1920×1080）
#     02-商品/06-姓氏线/版式/模板-姓氏-v11-mac.html    （Mac 1920×1248）
#   本脚本只剩两件事：① 字形覆盖闸门  ② 把数据填进模板的槽位。
#
# 槽位用注释对标记：<!--S:tag--> … <!--E:tag-->
#   tag 系列标 / title 画心标题 / verse 金句 / src 出处 / quat 四联字 / meta 字下两行
TPLDIR = BUILD.parent
TPL = {'std': TPLDIR / '模板-姓氏-v11.html', 'mac': TPLDIR / '模板-姓氏-v11-mac.html',
       'phone': TPLDIR / '模板-姓氏-v11-竖版.html',
       'square': TPLDIR / '模板-姓氏-v11-方版.html'}
SLOTS = ('tag', 'title', 'verse', 'src', 'quat', 'meta')
SLOT_RE = {k: re.compile(r'<!--S:%s-->(.*?)<!--E:%s-->' % (k, k), re.S) for k in SLOTS}

# ── 竖版（phone）/ 方版（square）：画幅变体与缩放 ────────────────
# phone  模板写基准 1080×1920，出图前按 A 线同一口径缩放到目标画幅：
#        纵向锚点（top/bottom）× ky = H/1920；横向一切 × kx = W/1080
# square 模板**以成品画幅 1179×1572 为基准写死**，出图时不做任何缩放
#        （3:4 的 ky/kx≈0.75，纵向紧 25%，套用上面的缩放公式会把四格撑破）
BASE_W, BASE_H = 1080, 1920
VARIANTS = {
    'ios':     (1179, 2556),   # iPhone 15/16/17 Pro 原生 · 19.5:9
    'android': (1080, 2400),   # 当代安卓主流 · 20:9
    'std':     (1080, 1920),   # 基准，仅供对照／回归
    'xhs':     (1179, 1572),   # 小红书 3:4（与 A 线朝代线同一口径：宽取 1179）
}
# 纵向版式预算：{每格标签两行高, 一道分隔线占位, 字号上限}（单位＝该模板基准的 px）
# ⚠️ 必须与模板里的实际值一致，改模板就得改这里
PH_BUDGET = {
    # 模板-姓氏-v11-竖版.html：quat top340/bottom300，divider 1+20*2，标签 9+17*1.4+5+12*1.4
    'phone':  {'top': 340, 'bottom': 300, 'div': 41, 'overhead': 55},
    # 模板-姓氏-v11-方版.html：quat top236/bottom228，divider 1+18*2，标签 8+17*1.4+5+12*1.4
    'square': {'top': 236, 'bottom': 228, 'div': 37, 'overhead': 54},
}
PH_LH = 1.06                         # 行高（相对值，不随画幅变）
PH_SIZE_CAP = 420                    # 字号绝对上限（防止极端画幅算出离谱值）
PH_N = 4                             # 四联字：4 格

# 缩放属性表：纵向锚点走 ky，其余走 kx（与 A 线 gen-evolution-phone.py 完全一致）
V_PROPS = ('top', 'bottom')
H_PROPS = ('left', 'right', 'width', 'height', 'font-size', 'letter-spacing',
           'text-indent', 'gap',
           'margin-top', 'margin-bottom', 'margin-left', 'margin-right')
_RE_V = re.compile(r'\b(%s):(-?\d+(?:\.\d+)?)px' % '|'.join(V_PROPS))
_RE_H = re.compile(r'\b(%s):(-?\d+(?:\.\d+)?)px' % '|'.join(H_PROPS))
_RE_M = re.compile(r'\bmargin:(-?\d+(?:\.\d+)?)px')   # shorthand 只缩第一个值


def phone_geometry(variant='ios'):
    """画幅变体 → 几何（两个缩放因子 + 画幅）。square 的模板基准就是成品画幅。"""
    if variant not in VARIANTS:
        raise SystemExit(f'未知画幅变体 {variant}（可选：{"/".join(VARIANTS)}）')
    W, H = VARIANTS[variant]
    if variant == 'xhs':                 # 方版模板以 1179×1572 为基准 ⇒ 不缩放
        return {'v': variant, 'W': W, 'H': H, 'kx': 1.0, 'ky': 1.0}
    kx, ky = W / BASE_W, H / BASE_H
    return {'v': variant, 'W': W, 'H': H, 'kx': kx, 'ky': ky}


def phone_cell_size(g, tpl='phone'):
    """四联字字号 → **目标画幅下的实际像素值**。

    ⚠️ 必须在目标画幅下反算，不能在 1080×1920 基准下算完再乘 kx：
       字号（走 kx）与锚点（走 ky）的缩放比不一致，9:19.5 时 ky/kx≈1.22（纵向富余），
       3:4 时 ky/kx≈0.75（纵向紧 25%）—— 基准算法到 3:4 会把四格撑破。
    """
    b = PH_BUDGET[tpl]
    kx, ky = g['kx'], g['ky']
    avail = g['H'] - (b['top'] + b['bottom']) * ky
    size = ((avail - b['div'] * kx * (PH_N - 1)) / PH_N - b['overhead'] * kx) / PH_LH
    return max(60.0, min(PH_SIZE_CAP, size))


def scale_html(html, g):
    """把整份 HTML（含内联 style）从 1080×1920 基准缩到目标画幅。

    ⚠️ 画幅那两处（html,body 与 .stage）先换占位符，否则会被通用正则二次缩放。
    """
    kx, ky = g['kx'], g['ky']
    t = html.replace('width:1080px;height:1920px', 'width:__W__px;height:__H__px')

    def rep(m, k):
        return '%s:%dpx' % (m.group(1), round(float(m.group(2)) * k))

    t = _RE_V.sub(lambda m: rep(m, ky), t)
    t = _RE_H.sub(lambda m: rep(m, kx), t)
    t = _RE_M.sub(lambda m: 'margin:%dpx' % round(float(m.group(1)) * kx), t)
    return t.replace('__W__', str(g['W'])).replace('__H__', str(g['H']))


def cnnum(n):
    """阿拉伯数字 → 中文数字（覆盖 1–99，够《百家姓》句序用）。
    出处写「第一句」不写「第 1 句」—— 竖排小字里阿拉伯数字破坏书卷气（用户 2026-10-03）。"""
    d = '零一二三四五六七八九'
    n = int(n)
    if n < 10:
        return d[n]
    if n < 20:
        return '十' + (d[n % 10] if n % 10 else '')
    return d[n // 10] + '十' + (d[n % 10] if n % 10 else '')


# 四联字顺序（按模板分叉）：
#   std / mac（横版，2026-10-03 用户定「右起展卷」）
#       屏幕自左向右 = 碑刻 | 隶书 | 行书 | 草书
#       展卷自右向左读 = 草书 → 行书 → 隶书 → 碑刻
#   phone / square（竖版、方版，2026-10-21 用户定「自上而下」）
#       ⭐ 竖版没有左右之分，横版那套「右起展卷」的说法不成立；
#          若照搬横版顺序，读演变顺序就变成「自下而上」，反了。
#          ⇒ 整序反转：自上而下 = 草书 | 行书 | 隶书 | 碑刻
#          副标题也随之由「右 起 展 卷」改为「自 上 而 下」（后半截「自草书至碑刻」通用）
TITLE_SUB = {'std': '右 起 展 卷 · 自 草 书 至 碑 刻',
             'mac': '右 起 展 卷 · 自 草 书 至 碑 刻',
             'phone': '自 上 而 下 · 自 草 书 至 碑 刻',
             'square': '自 上 而 下 · 自 草 书 至 碑 刻'}
ORDER4_BY_TPL = {'std': ORDER4, 'mac': ORDER4,
                 'phone': tuple(reversed(ORDER4)), 'square': tuple(reversed(ORDER4))}


def fill(rec, cellchars, cellsize, celldy, labelextra, cellfont, tpl='std', cellh=None):
    """读模板 → 替换 6 个数据槽位 → 返回成品 HTML。

    四格顺序与副标题文案都按 tpl 分叉，见上面的 ORDER4_BY_TPL / TITLE_SUB。
    """
    html = TPL[tpl].read_text(encoding='utf-8')
    verse = ''.join(f'<span>{c}</span>' for c in rec['verse'])
    cells = []
    for k in ORDER4_BY_TPL[tpl]:
        fk = cellfont.get(k, k)
        st = f"font-family:'{fk}'"
        if k in cellsize:
            st += f";font-size:{cellsize[k]}px"
            # 🔴 行盒高度必须 = 字号 × line-height(1.06)，不能与字号同值：
            #    字的下伸笔画（草书尤甚，「李」实测溢出 1.3em）会穿进下一行的标签。
            #    只对手机两版加，std/mac 横版是已定版口径，不动。
            if tpl in ('phone', 'square'):
                hh = (cellh or cellsize)[k]          # 行盒按**未缩**字号撑 ⇒ 缩小的字形居中其内
                st += f";height:{round(hh)}px"
                lh = hh / cellsize[k]
                if abs(lh - 1.06) > 0.02:
                    st += f";line-height:{lh:.2f}"   # 字号缩了 ⇒ 行高跟着放大保持垂直居中
        if celldy.get(k):
            st += f";transform:translateY({celldy[k]}px)"
        # 隶书格若换了字形/字体，标注写明实际字形：「隶书 · 趙 / 青柳隷書」
        lb = FONT_LABEL[fk][0] + (f" · {labelextra[k]}" if k in labelextra else '')
        cells.append(f'<div class="cell"><div class="ch" style="{st}">{cellchars[k]}</div>'
                     f'<div class="lb">{lb}<b>{FONT_LABEL[fk][1]}</b></div></div>')
    quat = '<div class="divider"></div>'.join(cells)
    vals = {
        'tag': f"姓 氏 源 流 · {rec['char']}",
        'title': ('<div class="t">一 姓 四 体 · 三 千 年</div>\n'
                  f'    <div class="h">{TITLE_SUB[tpl]}</div>'),
        'verse': verse,
        'src': f"《百家姓》北宋·第{cnnum(rec['line_no'])}句",
        'quat': quat,
        'meta': (f'<div class="en">{rec["pinyin"]}</div>\n'
                 f'    <div class="sub">{rec["char"]} / {rec["trad"]} · '
                 f'源流 {rec["era"]} · {rec["year"]}</div>'),
    }
    for k, v in vals.items():
        html, n = SLOT_RE[k].subn(v.replace('\\', '\\\\'), html, count=1)
        if n != 1:
            raise SystemExit(f'模板槽位 {k} 替换失败（命中 {n} 次）—— 模板可能被改坏')
    return html


# ── 字形覆盖闸门 ────────────────────────────────────────────────
NOTDEF = '\ue000'
_pil = {}
_cps = {}


def cmap_codepoints(path):
    """手写 cmap 解析（无 fontTools 依赖）：返回字体真实覆盖的码点集合。"""
    import struct
    raw = pathlib.Path(path).read_bytes()
    n = struct.unpack('>H', raw[4:6])[0]
    tables, subs = {}, []
    for i in range(n):
        o = 12 + i * 16
        tag = raw[o:o + 4].decode('latin1')
        toff, _tlen = struct.unpack('>II', raw[o + 8:o + 16])
        tables[tag] = toff
    coff = tables['cmap']
    cnt = struct.unpack('>H', raw[coff + 2:coff + 4])[0]
    for i in range(cnt):
        p = coff + 4 + i * 8
        pid, eid, soff = struct.unpack('>HHI', raw[p:p + 8])
        fmt = struct.unpack('>H', raw[coff + soff:coff + soff + 2])[0]
        subs.append((pid, eid, coff + soff, fmt))
    best = None
    for want in ((3, 10), (3, 1), (0, 4), (0, 3), (0, 6), (0, 0)):
        for pid, eid, soff, fmt in subs:
            if (pid, eid) == want and fmt in (4, 12):
                best = (soff, fmt)
                break
        if best:
            break
    if not best:
        return set()
    soff, fmt = best
    cps = set()
    if fmt == 4:
        segx2 = struct.unpack('>H', raw[soff + 6:soff + 8])[0]
        seg = segx2 // 2
        ends = struct.unpack('>%dH' % seg, raw[soff + 14:soff + 14 + segx2])
        sp = soff + 14 + segx2 + 2
        starts = struct.unpack('>%dH' % seg, raw[sp:sp + segx2])
        for s, e in zip(starts, ends):
            if s != 0xFFFF:
                cps.update(range(s, min(e, 0xFFFF) + 1))
    else:
        ng = struct.unpack('>I', raw[soff + 12:soff + 16])[0]
        for i in range(ng):
            p = soff + 16 + i * 12
            sc, ec, _gi = struct.unpack('>III', raw[p:p + 12])
            cps.update(range(sc, min(ec, 0x10FFFF) + 1))
    return cps


def glyph_ok(key, ch):
    """True = 该字在该字体里能真出墨（既在 cmap 里、又渲染出非空非 notdef 的图形）。

    ⚠️ 必须两条判据都跑：青柳隷書 把「吴」映射到一个空白字形 —— cmap 里有、渲出来是空，
       Chrome 不会回退，而是直接留白。只查 cmap 会漏判。
    """
    if key not in _pil:
        _pil[key] = ImageFont.truetype(str(FONTS[key]), 180)
        _cps[key] = cmap_codepoints(FONTS[key])

    def rend(c):
        im = Image.new('L', (540, 540), 0)
        ImageDraw.Draw(im).text((90, 90), c, font=_pil[key], fill=255)
        return im

    if ord(ch) not in _cps[key]:
        return False
    im = rend(ch)
    if im.getbbox() is None:                      # 空白字形
        return False
    if im.tobytes() == rend(NOTDEF).tobytes():    # .notdef 豆腐块
        return False
    return True


# ── 数据 ────────────────────────────────────────────────────────
def load():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    return d, d['sequence']


def build(d, seq, item, lishu_mode='trad', norm=None, tpl='std', variant='ios'):
    """返回 (html, 覆盖详情, 备注)。lishu_mode: trad=缺字时用繁体字形补；skip=缺字则拒出。

    norm: {order: {'serif': {'size': px, 'dy': px}, ...}} 逐格光学归一化参数。
    tpl='phone' 时额外按 variant 画幅（ios/android/std）缩放，且**忽略 celldy**
    （竖向位移是横版逐格标定的产物，竖版排版不同，不能照搬）。
    """
    sv = item['simplified']
    order = item['order']
    # 原句：按「已消费字符数」四字一切，不能用 flat.index（重复字会找错）
    start = sum(len(s['simplified']) for s in seq[:order - 1])
    g = (start // 4) * 4
    flat = ''.join(s['simplified'] for s in seq)
    verse = sv if item['type'] == 'compound' else flat[g:g + 4]
    line_no = start // 4 + 1

    om = (d.get('origin_map') or {}).get(sv) or {}
    year = om.get('year_display') or (f"c. {abs(om['approx_year'])} BC"
                                      if isinstance(om.get('approx_year'), int)
                                      and om['approx_year'] < 0 else '')
    rec = dict(char=sv, trad=item['traditional'], pinyin=(d.get('pinyin_map') or {}).get(sv, ''),
               order=order, verse=verse, line_no=line_no,
               era=om.get('era_label', ''), year=year)

    # 逐字覆盖闸门。隶书槽的取字优先级：
    #   青柳隷書 简体 → 青柳隷書 繁体（33 姓走这条，保持与首批 93 张一致）
    #   → 刀隶体 简体（决策 B 的 7 姓）→ 彻底无解
    cover, cellchars, cellfont, notes, labelextra = {}, {}, {}, [], {}
    for k in ORDER4:
        if glyph_ok(k, sv):
            cellchars[k], cover[k], cellfont[k] = sv, 'ok', k
        elif k == 'lishu':
            alt = rec['trad']
            if alt != sv and glyph_ok('lishu', alt):
                cellchars[k], cover[k], cellfont[k] = alt, 'trad', 'lishu'
                labelextra[k] = alt          # 标注写明实际字形
                notes.append(f"隶书槽改用繁体字形「{alt}」（青柳隷書 无简体「{sv}」）")
            elif glyph_ok('lishu2', sv):
                cellchars[k], cover[k], cellfont[k] = sv, 'lishu2', 'lishu2'
                labelextra[k] = sv           # 决策 B：标注写「隶书 · 吴」+ 阿里妈妈刀隶体
                notes.append(f"隶书槽改用阿里妈妈刀隶体（青柳隷書 简繁皆无「{sv}」）")
            else:
                cover[k], cellchars[k], cellfont[k] = 'missing', sv, k
                notes.append(f"缺字：青柳隷書 与 刀隶体 均无「{sv}」")
        else:
            cover[k], cellchars[k], cellfont[k] = 'missing', sv, k
            notes.append(f"缺字：{FONT_LABEL[k][1]} 无「{sv}」")

    cellh = None                               # phone/square 才有：未缩字号的行盒高度
    n = ((norm or {}).get(f"{order:03d}") or (norm or {}).get(str(order))
         or (norm or {}).get(order) or {})
    cellsize = {k: v['size'] for k, v in n.items() if 'size' in v}
    celldy = {k: v['dy'] for k, v in n.items() if v.get('dy')}

    if tpl in ('phone', 'square'):
        # 竖版/方版：字号由「画心可用高」在**目标画幅**下反算，逐格沿用横版同一套比例
        g = phone_geometry(variant)
        base = phone_cell_size(g, tpl)          # 目标画幅下的实际像素字号
        if tpl == 'phone':
            base /= g['kx']                     # scale_html 之后会再 × kx ⇒ 先换算回基准
        HB = 232.0                              # 横版 .ch 基准字号（模板里的值）
        # 🔴 草书字形纵向溢出 ≈1.28–1.3em（赵/李实测，笔画穿过本格标签），
        #    只缩草书字号，行盒高度按原字号撑（fill 里用 cellh），其余三体不动。
        #    0.78 ⇒ 314px 行盒可容 1.3em 字形（314/1.3≈242 ≥ 296×0.78≈231）。
        FONT_SHRINK = {'cao': 0.78} if tpl == 'phone' else {}
        ratio = {k: (cellsize.get(k, HB) / HB) for k in ORDER4}
        cellh = {k: round(base * ratio[k] * 1.06) for k in ORDER4}
        cellsize = {k: round(base * ratio[k] * FONT_SHRINK.get(k, 1.0)) for k in ORDER4}
        celldy = {}

    html = fill(rec, cellchars, cellsize, celldy, labelextra, cellfont, tpl,
                cellh=cellh if tpl in ('phone', 'square') else None)
    if tpl == 'phone':
        html = scale_html(html, g)
    return html, rec, cover, notes, cellfont


def stem_of(item, tpl='std', variant='ios'):
    s = f"surname-{item['order']:03d}-{item['simplified']}"
    if tpl == 'phone':
        return f"{s}-phone-{variant}"
    if tpl == 'square':
        return f"{s}-square"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chars', nargs='*')
    ap.add_argument('--first', type=int)
    ap.add_argument('--samples', action='store_true')
    ap.add_argument('--lishu-mode', choices=('trad', 'skip'), default='trad')
    ap.add_argument('--on-missing', choices=('skip', 'keep'), default='keep',
                    help='某体彻底无字时：skip=该姓本批不出（并入待补清单）')
    ap.add_argument('--norm', type=pathlib.Path, help='逐格光学归一化参数 JSON')
    ap.add_argument('--tpl', default='std', choices=('std', 'mac', 'phone', 'square'),
                    help='版式模板：std=1920×1080 / mac=1920×1248 / phone=手机竖版 / '
                         'square=手机3:4（小红书）')
    ap.add_argument('--variant', default='ios', choices=('ios', 'android', 'xhs', 'std'),
                    help='画幅（仅 --tpl phone 生效，--tpl square 固定 xhs 1179×1572）：'
                         'ios=1179×2556 / android=1080×2400 / xhs=1179×1572')
    a = ap.parse_args()
    if a.tpl == 'square':
        a.variant = 'xhs'

    d, seq = load()
    BUILD.mkdir(parents=True, exist_ok=True)
    norm = json.loads(a.norm.read_text(encoding='utf-8')) if a.norm else {}
    if a.samples:
        want = ['赵', '钱', '孙', '李']
        todo = [s for c in want for s in seq if s['simplified'] == c][:4]
    elif a.first:
        todo = seq[:a.first]
    elif a.chars:
        todo = [s for s in seq if s['simplified'] in a.chars]
    else:
        todo = seq[:3]

    lines, pending, written, skipped = [], [], [], []
    for item in todo:
        html, rec, cover, notes, _cf = build(d, seq, item, a.lishu_mode, norm,
                                             a.tpl, a.variant)
        missing = [k for k, v in cover.items() if v == 'missing']
        if missing:
            # 本批跳过：不出 HTML，也不删旧文件（由调用方决定）
            if a.on_missing == 'skip':
                pending.append(f"{rec['char']}(第{rec['order']}位)")
                continue
        p = BUILD / f"{stem_of(item, a.tpl, a.variant)}.html"
        p.write_text(html, encoding='utf-8')
        written.append(stem_of(item, a.tpl, a.variant))
        flag = '⚠' if missing else ('·' if notes else '✓')
        lines.append(f"{flag} 第{item['order']:>3}位 {item['simplified']} "
                     f"({'|'.join(f'{k}:{cover[k]}' for k in ORDER4)}) "
                     + ('  '.join(notes) if notes else '四体全部命中目标字体'))
    nrm = [k for k in lines if k.startswith('·')]
    body = [f"姓氏线 v2A 字形覆盖审计 · 共 {len(todo)} 个姓，出图 {len(written)} 个",
            f"归一化参数：{'已套用 ' + str(a.norm) if a.norm else '未套用（本轮为测量轮）'}", '']
    body += lines
    body += ['', '── 隶书槽改用繁体字形的姓（标注已写明实际字形）──']
    body += [l for l in nrm] or ['（无）']
    body += ['', f"── 待补字体的 {len(pending)} 姓（本批不出，等简体隶书字体到位后单独补）──"]
    body += (pending or ['（无）'])
    LOG.write_text('\n'.join(body) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    print(f"\n生成 {len(written)} 个 HTML → {BUILD}")
    if pending:
        print(f"本批跳过（待补字体）：{len(pending)} 个 —— {'、'.join(pending)}")


if __name__ == '__main__':
    main()
