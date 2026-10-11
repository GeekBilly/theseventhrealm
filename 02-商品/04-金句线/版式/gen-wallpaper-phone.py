# -*- coding: utf-8 -*-
"""第七境 · 金句线 · 手机竖版壁纸生成器（A 档 SR-D-001）
设计语言 = v9 桌面版（纯白底 / 马善政楷 / Noto Serif 宋 / 朱砂点 / 钤印 / Georgia 落款）
版式 = 竖幅居中构图 + 锁屏安全区（避让顶部时间与底部手电/相机按钮）

安全区分带（自上而下）：
  0–20%   留白（锁屏大时间占位）
  21%     系列小标
  31%     朝代主字（毛笔楷）+ 朱砂点睛
  39%     英文朝代名 + 年代
  44–69%  金句双列（右起，画面主角）+ 出处列（末尾，最左）
  72–80%  「第七境」+ 朱砂点 + 钤印（底部锚定 19%）
  84–88%  TANTSE™ + 网址（底部锚定 12%）
  87–100% 远山铺底

用法：
  python3 gen-wallpaper-phone.py shang          # 出商（iPhone + Android）
  python3 gen-wallpaper-phone.py --all          # 16 朝全出
  python3 gen-wallpaper-phone.py shang --ios    # 只出 iPhone 尺寸
"""
import math, re, sys, pathlib

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/05-承接站/样张'
F_BRUSH = ROOT / '02-商品/02-素材/字体/MaShanZheng.ttf'
F_SONG = ROOT / '02-商品/02-素材/字体/nssc-black.woff2'
SEAL = ROOT / '02-商品/02-素材/底纹/seal-hi.png'

SPECS = {
    'ios':     dict(w=1179, h=2556, tag='iphone'),
    'android': dict(w=1080, h=2400, tag='android'),
}

EN = {'sanhuang': ('LEGENDARY ERA', 'c. 2700 BC and earlier'), 'xia': ('XIA DYNASTY', 'c. 2070 – 1600 BC'),
      'shang': ('SHANG DYNASTY', 'c. 1600 – 1046 BC'), 'zhou': ('ZHOU DYNASTY', '1046 – 256 BC'),
      'qin': ('QIN DYNASTY', '221 – 206 BC'), 'han': ('HAN DYNASTY', '202 BC – AD 220'),
      'sanguo': ('THREE KINGDOMS', 'AD 220 – 280'), 'jin': ('JIN DYNASTY', 'AD 265 – 589'),
      'sui': ('SUI DYNASTY', 'AD 581 – 618'), 'tang': ('TANG DYNASTY', 'AD 618 – 907'),
      'wudai': ('FIVE DYNASTIES', 'AD 907 – 960'), 'song': ('SONG DYNASTY', 'AD 960 – 1279'),
      'yuan': ('YUAN DYNASTY', 'AD 1271 – 1368'), 'ming': ('MING DYNASTY', 'AD 1368 – 1644'),
      'qing': ('QING DYNASTY', 'AD 1644 – 1912'), 'juexing': ('THE AWAKENING', 'AD 1840 – 1949')}


def load_eras():
    src = (ROOT / '11-运营/朝代页流水线/eras.py').read_text(encoding='utf-8')
    out = []
    for blk in src.split('dict(')[1:]:
        g = lambda k: (re.search(rf"{k}='([^']*)'", blk) or [None, ''])[1]
        # 宋/元的 verse 是列表（横渠四句、窦娥冤），合并成一句再拆列
        ml = re.search(r"verse=\[([^\]]*)\]", blk)
        verse = '，'.join(re.findall(r"'([^']*)'", ml.group(1))) if ml else g('verse')
        e = dict(slug=g('slug'), h1=g('h1'), ghost=g('ghost'), verse=verse,
                 src=g('src'), years=g('years'), sub=g('sub'))
        if e['slug']:
            e['en'], e['enyears'] = EN.get(e['slug'], (e['slug'].upper(), ''))
            out.append(e)
    return out


def split_verse(verse):
    """拆成上下两句（右起读序：返回值 [0] 在右）。"""
    parts = [p for p in re.split(r'[，、；。]', verse) if p]
    if len(parts) >= 2:
        half = (len(parts) + 1) // 2
        return ['，'.join(parts[:half]), '，'.join(parts[half:])]
    n = len(verse)
    half = (n + 1) // 2
    return [verse[:half], verse[half:]]


def split_cols(verse, max_per=7):
    """按标点切小句；超过 max_per 字的句子再均分。
    返回列表 [0] 在最右（古籍读序）。列数随句长自适应，避免长句把字号压到看不清。"""
    parts = [p for p in re.split(r'[，、；。]', verse) if p]
    cols = []
    for p in parts:
        if len(p) <= max_per:
            cols.append(p)
        else:
            n = math.ceil(len(p) / max_per)
            k = math.ceil(len(p) / n)
            cols += [p[i:i + k] for i in range(0, len(p), k)]
    return cols or [verse]


def vcol(text, cls=''):
    spans = ''.join(f'<span>{ch}</span>' for ch in text)
    return f'<div class="vc {cls}">{spans}</div>'


def vsrc(text):
    spans = []
    for ch in text:
        if ch in ' ·':
            continue
        spans.append(f'<span class="rot">{ch}</span>' if ch in '《》' else f'<span>{ch}</span>')
    return f'<div class="vc src">{"".join(spans)}</div>'


TPL = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
@font-face{font-family:'MSZ';src:url('file://__BRUSH__')}
@font-face{font-family:'NSSC';src:url('file://__SONG__') format('woff2');font-weight:900}
:root{--white:#ffffff;--ink:#1a1a18;--ink2:#54504a;--cinnabar:#b03826;
 --f-brush:'MSZ','Ma Shan Zheng','KaiTi',serif;
 --f-song:'NSSC','Noto Serif SC','Songti SC',serif;
 --f-georgia:Georgia,'Times New Roman',serif}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:__W__px;height:__H__px;overflow:hidden;background:var(--white)}
.stage{position:relative;width:__W__px;height:__H__px;overflow:hidden;background:var(--white)}
.paper{position:absolute;left:0;top:0;right:0;bottom:0;background:
 radial-gradient(ellipse 86% 46% at 50% 52%, rgba(26,26,24,.020), transparent 72%)}
.series{position:absolute;left:50%;top:__ST__px;transform:translateX(-50%);z-index:3;
 font-family:var(--f-song);font-size:__SFS__px;letter-spacing:__SLS__px;color:#4a463f;
 text-indent:__SLS__px;white-space:nowrap}
.hero{position:absolute;left:50%;top:__HT__px;transform:translate(-50%,-50%);z-index:3;
 font-family:var(--f-brush);font-size:__HFS__px;line-height:1;color:var(--ink);white-space:nowrap}
.cinnabar-dot{position:absolute;left:calc(50% + __CDX__px);top:calc(__HT__px - __CDY__px);
 width:__CD__px;height:__CD__px;border-radius:50%;background:var(--cinnabar);z-index:4}
.era{position:absolute;left:50%;top:__ET__px;transform:translateX(-50%);z-index:3;
 text-align:center;font-family:var(--f-georgia);white-space:nowrap}
.era .en{font-size:__ENFS__px;letter-spacing:__ENLS__px;color:#26241f;text-transform:uppercase;
 text-indent:__ENLS__px}
.era .years{margin-top:__YMT__px;font-size:__YFS__px;letter-spacing:__YLS__px;color:#45423c;
 text-indent:__YLS__px}
.quote{position:absolute;left:50%;top:__QT__px;transform:translateX(-50%);z-index:3;
 display:flex;align-items:flex-start;gap:__QG__px}
.vc{display:flex;flex-direction:column;align-items:center}
.vc span{font-family:var(--f-brush);font-size:__QFS__px;line-height:__QLH__;color:var(--ink)}
.vc.src{align-self:flex-end;padding-bottom:__SRPB__px}
.vc.src span{font-family:var(--f-song);font-size:__SFS2__px;line-height:__SLH__;color:#3d3931}
.vc.src .rot{display:block;transform:rotate(90deg);line-height:1}
.colophon{position:absolute;left:50%;bottom:__CB__%;transform:translateX(-50%);z-index:3;
 display:flex;flex-direction:column;align-items:center}
.cjk{font-family:var(--f-brush);font-size:__CFS__px;letter-spacing:__CLS__px;color:var(--ink);
 text-indent:__CLS__px;line-height:1}
.vdot{width:__VD__px;height:__VD__px;border-radius:50%;background:var(--cinnabar);margin:__VDM__px 0}
.colophon-seal{height:__SH__px;opacity:.95;display:block}
.brand{position:absolute;left:50%;bottom:__BB__%;transform:translateX(-50%);z-index:3;
 text-align:center;font-family:var(--f-georgia);white-space:nowrap}
.brand-en{font-size:__BFS__px;letter-spacing:__BLS__px;color:#26241f;text-transform:uppercase;
 text-indent:__BLS__px}
.brand-url{margin-top:__BUMT__px;font-size:__BUFS__px;letter-spacing:__BULS__px;color:#45423c;
 text-indent:__BULS__px}
.brand sup{font-size:.56em;letter-spacing:1px}
.mountains{position:absolute;left:0;bottom:0;width:100%;height:__MH__px;z-index:2}
.mist{position:absolute;left:0;bottom:0;width:100%;height:__MH2__px;z-index:1}
</style></head><body><div class="stage">
  <div class="paper"></div>
  <div class="series">__SERIES__</div>
  <div class="hero">__CHAR__</div>
  <div class="cinnabar-dot"></div>
  <div class="era"><div class="en">__EN__</div><div class="years">__YEARS__</div></div>
  <div class="quote">__QUOTE__</div>
  <div class="colophon">
    <div class="cjk">第七境</div>
    <div class="vdot"></div>
    <img class="colophon-seal" src="file://__SEAL__">
  </div>
  <div class="brand">
    <!-- 2026-10-02 方案①：中文产品去掉英文品牌 TANTSE（它与域名 theseventhrealm.com 对不上，
         中英分立应为：中文线＝第七境/theseventhrealm.com，英文线＝TANTSE/tantse.com）。
         TANTSE 只在英文站与海外物料出现。 -->
    <div class="brand-url">www.theseventhrealm.com</div>
  </div>
  <svg class="mist" viewBox="0 0 1200 260" preserveAspectRatio="none">
    <path d="M0,260 L0,150 Q240,96 470,140 Q700,184 930,132 Q1160,80 1200,128 L1200,260 Z"
          fill="rgba(26,26,24,.026)"/>
  </svg>
  <svg class="mountains" viewBox="0 0 1200 340" preserveAspectRatio="none">
    <path d="M0,340 L0,238 Q160,180 320,214 Q420,232 520,196 Q650,150 760,196
             Q880,244 1010,208 Q1150,168 1200,206 L1200,340 Z" fill="rgba(26,26,24,.045)"/>
    <path d="M0,340 L0,282 Q220,246 380,268 Q540,290 700,262 Q860,236 1040,266
             Q1150,296 1200,264 L1200,340 Z" fill="rgba(26,26,24,.085)"/>
  </svg>
</div></body></html>"""


def metrics(w, h, nchars=1):
    """按比例推导尺寸。长度一律 px，行高用无单位倍数。
    nchars = h1 字数：多字朝代（4-5 字）按字数缩字号，防止折行/遮挡；
    单字/双字/三字保持与原版完全一致。"""
    p = lambda r: round(h * r)
    # 主字基准字号，按字数缩放：保证 n 个字总宽度 ≤ 屏宽 86%
    base_hfs = round(w * .237)
    max_hfs = round((w * .86) / nchars)
    hfs = min(base_hfs, max_hfs)
    # 朱砂点：3 字以内保持原版（固定偏移）；4 字以上随字号/字数动态，点在最后一字右上方
    if nchars <= 3:
        cdx = round(w * .140)
        cdy = round(w * .116)
    else:
        cdx = round(hfs * .59 + hfs * (nchars - 1) / 2)
        cdy = round(hfs * .49)
    return dict(
        w=w, h=h,
        st=p(.26), sfs=round(w * .021), sls=round(w * .0095),
        ht=p(.34), hfs=hfs,
        cdx=cdx, cdy=cdy, cd=round(w * .017),
        et=p(.41), enfs=round(w * .032), enls=round(w * .013),
        ymt=round(h * .006), yfs=round(w * .025), yls=round(w * .009),
        qt=p(.46), qfs=round(w * .072), qlh='1.8', qg=round(w * .042),
        cb=20, bb=13.5,
        sfs2=round(w * .028), slh='1.85', srpb=round(h * .012),
        cfs=round(w * .036), cls=round(w * .008),
        vd=round(w * .009), vdm=round(h * .007), sh=round(w * .080),
        bfs=round(w * .042), bls=round(w * .006),   # 2026-10-02：英文名改 TANTSE（6 字母），
                                                    # 原 .033/.011 是为 17 字母的 THE SEVENTH REALM 调的 → 放大字号、收紧字距
        bumt=round(h * .007), bufs=round(w * .023), buls=round(w * .004),
        mh=round(h * .13), mh2=round(h * .18),
    )


def build(era, spec):
    w, h = spec['w'], spec['h']
    nchars = len(era['h1'])
    m = metrics(w, h, nchars=nchars)
    cols = split_cols(era['verse'])
    ncol = len(cols)
    avail = round(h * .245)             # 金句可用高度：46% → 落款顶
    maxlen = max(len(c) for c in cols)
    # 字号自适应：长句缩字号，保底 w*.042，宁可小也不能压到落款
    qfs = max(min(round(w * .072), int(avail / (maxlen * 1.8))), round(w * .042))
    qg = round(w * .042)
    while (ncol + 1) * qfs + ncol * qg > round(w * .86):
        if qfs > round(w * .042):
            qfs -= 1
        elif qg > round(w * .018):
            qg -= 1
        else:
            break
    srclen = max(1, len([c for c in era['src'] if c not in ' ·']))
    # 题款（出处）必须明显小于正文：书法惯例，统一压到屏宽 2.0%
    sfs2 = max(min(round(w * .020), int(avail / (srclen * 1.85))), round(w * .014))
    m.update(qfs=qfs, qg=qg, sfs2=sfs2)
    html = TPL
    for k, v in m.items():
        html = html.replace(f'__{k.upper()}__', str(v))
    quote = vsrc(era['src']) + ''.join(vcol(c) for c in reversed(cols))
    html = (html.replace('__BRUSH__', str(F_BRUSH)).replace('__SONG__', str(F_SONG))
                .replace('__SEAL__', str(SEAL))
                .replace('__SERIES__', '上 下 五 千 年 · ' + era['h1'])
                .replace('__CHAR__', era['h1'])
                .replace('__QUOTE__', quote)
                .replace('__EN__', era['en']).replace('__YEARS__', era['enyears']))
    return html


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    OUT.mkdir(parents=True, exist_ok=True)

    # ⚠️ 2026-10-02 用户定案：手机竖版**只发单字朝代**。
    # 理由：方格主字要一个字撑住画面，多字（三皇五帝 / 三国 / 两晋南北朝 / 五代十国 / 觉醒年代）
    # 排版会塌，先拿下不发。这几个朝代的内容仍在（朝代页等），只是不出手机壁纸。
    MULTI_CHAR = {'sanhuang', 'sanguo', 'jin', 'wudai', 'juexing'}
    all_eras = load_eras()
    eras = [e for e in all_eras if e['slug'] not in MULTI_CHAR]
    skip = [e['slug'] for e in all_eras if e['slug'] in MULTI_CHAR]
    if skip:
        print(f'（跳过 {len(skip)} 个多字朝代：{" ".join(skip)}）')

    todo = eras if '--all' in sys.argv else [e for e in eras if e['slug'] in (args or ['shang'])]
    kinds = [k for k in SPECS if (f'--{k}' in sys.argv)] or list(SPECS)
    for e in todo:
        for k in kinds:
            p = OUT / f"{e['slug']}-phone-{SPECS[k]['tag']}.html"
            p.write_text(build(e, SPECS[k]), encoding='utf-8')
            print('生成', p)
