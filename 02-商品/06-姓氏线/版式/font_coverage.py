#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏线 v2A · 字体字形覆盖审计

两条独立判据（互为交叉验证）：
  1. 直接解析 TTF 的 cmap 表，取字体真实覆盖的码点集合（权威）
  2. 用 PIL 渲染该字，与「必然缺字」的私用区码点 U+E000 的渲染结果比对；
     若位图完全一致 或 完全空白 → 判为缺字（模拟 Chrome 的回退触发条件）

用法：
  python3 font_coverage.py            # 审计首批 100 姓
  python3 font_coverage.py --all      # 审计全部 504 姓
"""
import json
import pathlib
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
DATA = ROOT / '百家姓-交叉验证.json'
FDIR = ROOT / '02-商品/02-素材/字体'

FONTS = {
    'serif': FDIR / 'fonts/NotoSerifSC-Black.ttf',
    'lishu': FDIR / '隶书/aoyagireisyosimo_ttf_2_01.ttf',
    'xing':  FDIR / 'fonts/挚芒行.ttf',
    'cao':   FDIR / 'fonts/柳建毛草.ttf',
}


# ── 判据 1：手写 cmap 解析（不依赖 fontTools）──────────────────────
def cmap_codepoints(path):
    raw = pathlib.Path(path).read_bytes()
    num_tables = struct.unpack('>H', raw[4:6])[0]
    tables = {}
    for i in range(num_tables):
        off = 12 + i * 16
        tag = raw[off:off + 4].decode('latin1')
        toff, tlen = struct.unpack('>II', raw[off + 8:off + 16])
        tables[tag] = (toff, tlen)
    if 'cmap' not in tables:
        return set()
    coff = tables['cmap'][0]
    n = struct.unpack('>H', raw[coff + 2:coff + 4])[0]
    best = None
    subs = []
    for i in range(n):
        p = coff + 4 + i * 8
        pid, eid, soff = struct.unpack('>HHI', raw[p:p + 8])
        fmt = struct.unpack('>H', raw[coff + soff:coff + soff + 2])[0]
        subs.append((pid, eid, coff + soff, fmt))
    # 优先 3/10 (UCS-4) → 3/1 (BMP) → 0/x
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
            if s == 0xFFFF:
                continue
            for c in range(s, min(e, 0xFFFF) + 1):
                cps.add(c)
    elif fmt == 12:
        ngroups = struct.unpack('>I', raw[soff + 12:soff + 16])[0]
        for i in range(ngroups):
            p = soff + 16 + i * 12
            sc, ec, _gi = struct.unpack('>III', raw[p:p + 12])
            for c in range(sc, min(ec, 0x10FFFF) + 1):
                cps.add(c)
    return cps


# ── 判据 2：PIL 渲染比对 ─────────────────────────────────────────
NOTDEF = '\ue000'


def pil_blank_or_notdef(font, ch, size=180):
    def rend(c):
        im = Image.new('L', (size * 3, size * 3), 0)
        ImageDraw.Draw(im).text((size // 2, size // 2), c, font=font, fill=255)
        return im
    a = rend(ch)
    if a.getbbox() is None:
        return 'blank'
    if a.tobytes() == rend(NOTDEF).tobytes():
        return 'notdef'
    return None


def load_seq():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    return d, d['sequence']


def audit(seq, limit=None):
    cps = {k: cmap_codepoints(v) for k, v in FONTS.items()}
    pil = {k: ImageFont.truetype(str(v), 180) for k, v in FONTS.items()}
    rows = []
    for item in (seq[:limit] if limit else seq):
        if item['type'] != 'single':
            continue
        ch = item['simplified']
        miss = []
        detail = {}
        for k in ('serif', 'lishu', 'xing', 'cao'):
            # ⚠️ 两条判据都要跑：青柳隷書 这类字体会把「吴」映射到一个空白字形，
            #    cmap 里有、渲出来却是空的 —— 只查 cmap 会漏判。
            in_cmap = ord(ch) in cps[k]
            pil_bad = pil_blank_or_notdef(pil[k], ch)
            if not in_cmap:
                bad = pil_bad or 'notdef'
            else:
                bad = pil_bad            # 'blank' / 'notdef' / None
            detail[k] = 'ok' if bad is None else bad
            if bad is not None:
                miss.append(k)
        rows.append(dict(order=item['order'], char=ch, miss=miss, detail=detail))
    return rows, cps


if __name__ == '__main__':
    d, seq = load_seq()
    limit = None if '--all' in sys.argv else 100
    rows, cps = audit(seq, limit)
    for k, v in cps.items():
        print(f'  cmap {k:<6} {len(v):>6} 码点')
    print()
    bad = [r for r in rows if r['miss']]
    print(f'审计 {len(rows)} 个单姓，其中 {len(bad)} 个存在缺字：')
    for r in bad:
        print(f"  第{r['order']:>3}位 {r['char']}  缺: {','.join(r['miss'])}  "
              + ' '.join(f"{k}={v}" for k, v in r['detail'].items() if v != 'ok'))
    if not bad:
        print('  （无）')
