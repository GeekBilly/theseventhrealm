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
TPL = {'std': TPLDIR / '模板-姓氏-v11.html', 'mac': TPLDIR / '模板-姓氏-v11-mac.html'}
SLOTS = ('tag', 'title', 'verse', 'src', 'quat', 'meta')
SLOT_RE = {k: re.compile(r'<!--S:%s-->(.*?)<!--E:%s-->' % (k, k), re.S) for k in SLOTS}


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


def fill(rec, cellchars, cellsize, celldy, labelextra, cellfont, tpl='std'):
    """读模板 → 替换 6 个数据槽位 → 返回成品 HTML。

    ⭐ 四联字顺序（2026-10-03 用户定）：**右起展卷**
       屏幕自左向右 = 碑刻 | 隶书 | 行书 | 草书
       展卷自右向左读 = 草书 → 行书 → 隶书 → 碑刻（用户口径「按草书到碑刻，从右往左」）
       ⚠️ 要反过来只需把下面的 `ORDER4` 换成 `reversed(ORDER4)`，并把模板里
          `.series .h` 的「自 草 书 至 碑 刻」同步改回「自 碑 刻 至 草 书」。
    """
    html = TPL[tpl].read_text(encoding='utf-8')
    verse = ''.join(f'<span>{c}</span>' for c in rec['verse'])
    cells = []
    for k in ORDER4:
        fk = cellfont.get(k, k)
        st = f"font-family:'{fk}'"
        if k in cellsize:
            st += f";font-size:{cellsize[k]}px"
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
                  '    <div class="h">右 起 展 卷 · 自 草 书 至 碑 刻</div>'),
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


def build(d, seq, item, lishu_mode='trad', norm=None, tpl='std'):
    """返回 (html, 覆盖详情, 备注)。lishu_mode: trad=缺字时用繁体字形补；skip=缺字则拒出。

    norm: {order: {'serif': {'size': px, 'dy': px}, ...}} 逐格光学归一化参数。
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

    n = ((norm or {}).get(f"{order:03d}") or (norm or {}).get(str(order))
         or (norm or {}).get(order) or {})
    cellsize = {k: v['size'] for k, v in n.items() if 'size' in v}
    celldy = {k: v['dy'] for k, v in n.items() if v.get('dy')}
    html = fill(rec, cellchars, cellsize, celldy, labelextra, cellfont, tpl)
    return html, rec, cover, notes, cellfont


def stem_of(item):
    return f"surname-{item['order']:03d}-{item['simplified']}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('chars', nargs='*')
    ap.add_argument('--first', type=int)
    ap.add_argument('--samples', action='store_true')
    ap.add_argument('--lishu-mode', choices=('trad', 'skip'), default='trad')
    ap.add_argument('--on-missing', choices=('skip', 'keep'), default='keep',
                    help='某体彻底无字时：skip=该姓本批不出（并入待补清单）')
    ap.add_argument('--norm', type=pathlib.Path, help='逐格光学归一化参数 JSON')
    ap.add_argument('--tpl', default='std', choices=('std', 'mac'),
                    help='版式模板：std=1920×1080 / mac=1920×1248')
    a = ap.parse_args()

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
        html, rec, cover, notes, _cf = build(d, seq, item, a.lishu_mode, norm, a.tpl)
        missing = [k for k, v in cover.items() if v == 'missing']
        if missing:
            # 本批跳过：不出 HTML，也不删旧文件（由调用方决定）
            if a.on_missing == 'skip':
                pending.append(f"{rec['char']}(第{rec['order']}位)")
                continue
        p = BUILD / f"{stem_of(item)}.html"
        p.write_text(html, encoding='utf-8')
        written.append(stem_of(item))
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
