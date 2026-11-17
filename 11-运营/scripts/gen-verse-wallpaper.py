# -*- coding: utf-8 -*-
"""每日一句金句 · 手机竖版壁纸生成器（本地零积分）

v4（2026-11-17 · 用户定案）：**100% 照搬百家姓竖版母版**，只改画心内容。
  · 母版：02-商品/06-姓氏线/版式/模板-姓氏-v11-竖版.html（不修改该文件）
  · 缩放：复用 gen-surname-v2a.py 的 scale_html / geometry（逐字复制其口径）
  · 字体、位置、配色、左侧竖排第七境+印章、右侧竖排、底部三段式、远山：全部原样
  · v4 变更（用户 2026-11-17 看图定）：画心由「四格四体」改为
    **整句两列竖排、单一手写楷（龙藏体）**，与用户样图同款：
      右列先读、左列后读；简体字；白底黑字；无书体标签、无分隔线。
    v3 的「自上而下·草书至碑刻 / 四格标签 / 分隔线」全部去掉。

画心分列（split_two_cols）：按标点把整句切成 ≤2 列，右列先读、字数尽量均衡。
龙藏缺字（脩/慆/濛）：单字回退 wts43（已验证覆盖），逐字 span 注入。

字号：按「较长列字数 + 画心可用高」自适应，目标撑满画心但留上下呼吸：
  基准画心高 1280px（top340 / bottom300）；字号 = min(可用高*0.86/列字数, 190)，
  下限 96px，保证 9 字长列也一眼能读。两列等高（字号统一）。

槽位映射（金句 → 百家姓结构）：
  tag/verse/src/meta  与 v3 相同，不动
  title  画心上方两行    「一 句 一 典 · 五 千 年」+「手 写 楷 · 右 起 竖 读」
  quat   画心           整句两列竖排（龙藏体），取代四格四体

用法：
  python3 gen-verse-wallpaper.py              # 30 条 × 2 尺寸 HTML
  python3 gen-verse-wallpaper.py --only=1     # 只出第 1 条
产出：04-市场/03-推广获客/金句日更-202611/壁纸HTML/
"""
import csv
import pathlib
import re
import struct
import sys
import unicodedata

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
SRC = ROOT / '04-市场/03-推广获客/金句日更-202611/金句库-30条.csv'
OUT = ROOT / '04-市场/03-推广获客/金句日更-202611/壁纸HTML'
TPL = ROOT / '02-商品/06-姓氏线/版式/模板-姓氏-v11-竖版.html'

SPECS = {'ios': (1179, 2556, 'iphone'), 'android': (1080, 2400, 'android')}

# 关键词 → 带声调全拼（仅用于生成 meta 的大写无声调拼音行）
PINYIN = {
    '知彼知己': 'Zhi Bi Zhi Ji', '兵者诡道': 'Bing Zhe Gui Dao',
    '民不畏死': 'Min Bu Wei Si', '文质彬彬': 'Wen Zhi Bin Bin',
    '好学乐学': 'Hao Xue Le Xue', '孔子收徒': 'Kong Zi Shou Tu',
    '述而不作': 'Shu Er Bu Zuo', '孔子论生死': 'Kong Zi Lun Sheng Si',
    '天视民视': 'Tian Shi Min Shi', '周虽旧邦': 'Zhou Sui Jiu Bang',
    '诗经东山': 'Shi Jing Dong Shan', '横渠四句': 'Heng Qu Si Ju',
    '文章合为时': 'Wen Zhang He Wei Shi', '仰观宇宙': 'Yang Guan Yu Zhou',
    '阿房宫赋': 'E Pang Gong Fu', '滚滚长江': 'Gun Gun Chang Jiang',
    '春花秋月': 'Chun Hua Qiu Yue', '不拘一格': 'Bu Ju Yi Ge',
    '长亭送别': 'Chang Ting Song Bie', '满纸荒唐': 'Man Zhi Huang Tang',
    '分久必合': 'Fen Jiu Bi He', '三不足': 'San Bu Zu',
    '但行好事': 'Dan Xing Hao Shi', '以铜为镜': 'Yi Tong Wei Jing',
    '垓下歌': 'Gai Xia Ge', '究天人之际': 'Jiu Tian Ren Zhi Ji',
    '宁有种乎': 'Ning You Zhong Hu', '六经皆史': 'Liu Jing Jie Shi',
    '境界说': 'Jing Jie Shuo', '上穷碧落': 'Shang Qiong Bi Luo',
}

# ── 以下缩放逻辑逐字复制自 gen-surname-v2a.py（不依赖 PIL 的部分）────────
VARIANTS = {'ios': (1179, 2556), 'android': (1080, 2400), 'std': (1080, 1920), 'xhs': (1179, 1572)}
BASE_W, BASE_H = 1080, 1920
PH_BUDGET = {'phone': {'top': 340, 'bottom': 300, 'div': 41, 'overhead': 55}}
PH_LH, PH_SIZE_CAP = 1.06, 420
V_PROPS = ('top', 'bottom')
H_PROPS = ('left', 'right', 'width', 'height', 'font-size', 'letter-spacing',
           'text-indent', 'gap', 'margin-top', 'margin-bottom', 'margin-left', 'margin-right')
_RE_V = re.compile(r'\b(%s):(-?\d+(?:\.\d+)?)px' % '|'.join(V_PROPS))
_RE_H = re.compile(r'\b(%s):(-?\d+(?:\.\d+)?)px' % '|'.join(H_PROPS))
_RE_M = re.compile(r'\bmargin:(-?\d+(?:\.\d+)?)px')

SLOTS = ('tag', 'title', 'verse', 'src', 'quat', 'meta')
SLOT_RE = {k: re.compile(r'<!--S:%s-->(.*?)<!--E:%s-->' % (k, k), re.S) for k in SLOTS}


def cmap_codepoints(path):
    """手写 cmap 解析（复制自 gen-surname-v2a.py，无 fontTools 依赖）。"""
    raw = pathlib.Path(path).read_bytes()
    n = struct.unpack('>H', raw[4:6])[0]
    tables = {}
    for i in range(n):
        o = 12 + i * 16
        tag = raw[o:o + 4].decode('latin1')
        toff = struct.unpack('>II', raw[o + 8:o + 16])[0]
        tables[tag] = toff
    coff = tables['cmap']
    cnt = struct.unpack('>H', raw[coff + 2:coff + 4])[0]
    subs = []
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
            sc, ec, _ = struct.unpack('>III', raw[p:p + 12])
            cps.update(range(sc, min(ec, 0x10FFFF) + 1))
    return cps


# 画心手写楷：马善政楷（主，＝母版 --f-brush 默认手写楷 msz，与用户样图最接近）
#   2026-11-17 用户否掉 v4 龙藏（偏细偏硬）→ 换 msz；字号同步调小
# 缺字回退 wts43（msz 缺 脩/慆/濛，已验证 wts43 覆盖）
VERSE_FONT = ROOT / '02-商品/02-素材/字体/MaShanZheng.ttf'
FALLBACK_FONT = ROOT / '02-商品/02-素材/字体/碑刻候选/wts43.ttf'
_COV = {}


def glyph_ok(font_key, ch):
    if font_key not in _COV:
        _COV[font_key] = cmap_codepoints(VERSE_FONT if font_key == 'main' else FALLBACK_FONT)
    return ord(ch) in _COV[font_key]


def glyph_span(ch, fs):
    """单字 span；msz 缺字则回退 wts43（同批次口径，保证不死字/不静默宋体）。"""
    fam = 'msz' if glyph_ok('main', ch) else ('wtsfallback' if glyph_ok('fb', ch) else 'msz')
    return f'<span style="font-family:\'{fam}\'">{ch}</span>'


def geometry(variant):
    W, H = VARIANTS[variant]
    return {'W': W, 'H': H, 'kx': W / BASE_W, 'ky': H / BASE_H}


def scale_html(html, g):
    kx, ky = g['kx'], g['ky']
    t = html.replace('width:1080px;height:1920px', 'width:__W__px;height:__H__px')

    def rep(m, k):
        return '%s:%dpx' % (m.group(1), round(float(m.group(2)) * k))

    t = _RE_V.sub(lambda m: rep(m, ky), t)
    t = _RE_H.sub(lambda m: rep(m, kx), t)
    t = _RE_M.sub(lambda m: 'margin:%dpx' % round(float(m.group(1)) * kx), t)
    return t.replace('__W__', str(g['W'])).replace('__H__', str(g['H']))


def plain_pinyin(s):
    """带声调拼音 → 大写无声调（百家姓 meta 行是 ZHAO 这种全大写）。"""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.upper()


def split_verse(verse, max_per=10, max_cols=2):
    """右侧竖排：切 ≤2 列（每列 ≤10 字），右起读。"""
    parts = [p for p in re.split(r'[，、；。？！：]', verse) if p]
    cols, cur = [], ''
    for p in parts:
        if len(cur) + len(p) <= max_per:
            cur += p
        else:
            if cur:
                cols.append(cur)
            cur = p
    if cur:
        cols.append(cur)
    return cols[:max_cols] or [verse[:max_per]]


def split_two_cols(verse):
    """画心整句：按标点切成 2 列，右列先读；字数尽量均衡（5/5、5/4 之类）。
    一列超长（>9）时再在就近标点切，最多仍 2 列（超长取前 2 段）。"""
    parts = [p for p in re.split(r'[，、；。？！：]', verse) if p]
    if not parts:
        return [verse[:12]]
    if len(parts) == 1:
        s = parts[0]
        if len(s) <= 9:
            return [s]
        # 单句超长（9 字以上）：中点附近硬切两列
        m = (len(s) + 1) // 2
        return [s[:m], s[m:]]
    # 多段：按累计字数找最接近一半的切点
    total = sum(len(p) for p in parts)
    best_i, best_d = 1, 10 ** 9
    acc = 0
    for i in range(len(parts) - 1):
        acc += len(parts[i])
        d = abs(acc - total / 2)
        if d < best_d:
            best_d, best_i = d, i + 1
    right = ''.join(parts[:best_i])
    left = ''.join(parts[best_i:])
    return [right, left]


def quat_html(verse, g):
    """画心：整句两列竖排（龙藏体），右列先读。字号自适应，撑满画心留呼吸。"""
    cols = split_two_cols(verse)
    longest = max(len(c) for c in cols)
    avail = (BASE_H - (PH_BUDGET['phone']['top'] + PH_BUDGET['phone']['bottom'])) * g['ky']
    fs_px = max(76, min(140 * g['kx'], round(avail * 0.62 / longest)))
    # 单列字数悬殊时，短列顶部与长列顶部对齐（视觉更稳），列间留 0.9em
    gap = round(fs_px * 0.9)
    out = []
    for col in cols:             # row-reverse：DOM 第一个排最右 ⇒ 右列先读 = cols[0]
        spans = ''.join(glyph_span(ch, fs_px) for ch in col)
        out.append(
            f'<div class="vcol" style="display:flex;flex-direction:column;align-items:center;'
            f'font-size:{fs_px}px;line-height:1.12;gap:0">{spans}</div>'
        )
    return ('<div class="vquat" style="display:flex;flex-direction:row-reverse;'
            f'align-items:flex-start;justify-content:center;gap:{gap}px">'
            + ''.join(out) + '</div>')


def build(row, variant):
    g = geometry(variant)
    html = TPL.read_text(encoding='utf-8')

    # msz 已在母版注册；仅注入缺字回退字体 wts（改生成 HTML 不改母版文件）
    face = "@font-face{font-family:'wtsfallback';src:url('file://" + str(FALLBACK_FONT) + "')}"
    html = html.replace('</style>', face + '\n</style>', 1)

    # 画心：整句两列竖排（取代四格四体）
    quat = quat_html(row.get('壁纸句') or row['原句'], g)

    # 右侧竖排小金句：沿用 v3（不动）
    cols = split_verse(row.get('壁纸句') or row['原句'])
    verse_html = ''.join('<div class="vc">' + ''.join(f'<span>{c}</span>' for c in col) + '</div>'
                         for col in reversed(cols))

    src = f'{row["朝代"]}·{row["作者"]}《{row["出处"]}》'
    who = row['作者'].split('·')[0]
    meta = (f'<div class="en">{plain_pinyin(PINYIN[row["关键词"]])}</div>\n'
            f'    <div class="sub">{row["朝代"]} · {who} · {row["出处"]}</div>')

    vals = {
        'tag': f'金 句 · 第 {row["序号"].zfill(2)} 句',
        'title': ('<div class="t">一 句 一 典 · 五 千 年</div>\n'
                  '    <div class="h">手 写 楷 · 右 起 竖 读</div>'),
        'verse': verse_html,
        'src': src,
        'quat': quat,
        'meta': meta,
    }
    for k, v in vals.items():
        html, n = SLOT_RE[k].subn(v.replace('\\', '\\\\'), html, count=1)
        if n != 1:
            raise SystemExit(f'模板槽位 {k} 替换失败（命中 {n} 次）—— 模板可能被改坏')
    return scale_html(html, g)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(SRC.open(encoding='utf-8')))
    only = None
    for a in sys.argv[1:]:
        if a.startswith('--only='):
            only = int(a.split('=')[1])
    todo = [rows[only - 1]] if only else rows
    n = 0
    for r in todo:
        assert r['关键词'] in PINYIN, f'缺拼音映射：{r["关键词"]}'
        idx = rows.index(r) + 1
        for variant, (w, h, tag) in SPECS.items():
            name = f'D{idx:02d}-{r["关键词"]}-phone-{tag}.html'
            (OUT / name).write_text(build(r, variant), encoding='utf-8')
            n += 1
    print(f'已生成 {n} 个 HTML -> {OUT}')


if __name__ == '__main__':
    main()
