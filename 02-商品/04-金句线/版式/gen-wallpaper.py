# -*- coding: utf-8 -*-
"""第七境 · 朝代金句壁纸生成器（A 档 SR-D-001）
数据源：11-运营/朝代页流水线/eras.py（与线上朝代页同一份金句，站内外一致）
用法：
  python3 02-商品/04-金句线/版式/gen-wallpaper.py shang        # 只出商
  python3 02-商品/04-金句线/版式/gen-wallpaper.py --all        # 16 朝全出
输出 HTML 到 02-商品/05-承接站/样张/，再截图成 PNG。
设计铁律（ink-wash）：宣纸白底、毛笔字、居中留白、朱砂点睛、远山铺底、角上一枚淡墨印。
本地零 AI 成本：排版与渲染全在本地，不调用图像生成。
"""
import re, sys, pathlib

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/05-承接站/样张'
FONT_MSZ = ROOT / '02-商品/02-素材/字体/MaShanZheng.ttf'
FONT_SERIF = ROOT / '02-商品/02-素材/字体/fonts/NotoSerifSC-Black.ttf'
SEAL = ROOT / '02-商品/02-素材/底纹/seal-hi.png'

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
        e = dict(slug=g('slug'), h1=g('h1'), ghost=g('ghost'), verse=g('verse'),
                 src=g('src'), years=g('years'), sub=g('sub'))
        if e['slug']:
            e['en'], e['enyears'] = EN.get(e['slug'], (e['slug'].upper(), ''))
            out.append(e)
    return out


def two_cols(verse):
    """按古籍读序拆两列（右起）：惟殷先人，<br>有册有典"""
    parts = [p for p in re.split(r'[，、；]', verse) if p]
    if len(parts) < 2:
        return verse
    half = (len(parts) + 1) // 2
    c1 = '，'.join(parts[:half]) + '，'
    c2 = '，'.join(parts[half:])
    return c1 + '<br>' + c2


HEAD = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
@font-face{font-family:'MSZ';src:url('file://__MSZ__')}
@font-face{font-family:'NSSC';src:url('file://__SERIF__')}
@import url('https://fonts.loli.net/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@400;600&display=swap');
:root{--white:#fdfcf9;--ink:#1a1a18;--ink2:#6b675f;--cinnabar:#b03826;
 --f-brush:'MSZ','Ma Shan Zheng','Xingkai SC','STXingkai',serif;
 --f-body:'NSSC','Noto Serif SC',Georgia,serif}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:__W__px;height:__H__px;overflow:hidden;background:var(--white)}
.stage{position:relative;width:__W__px;height:__H__px;background:
 radial-gradient(ellipse __GLOW__ at 50% 40%, rgba(26,26,24,.022), transparent 70%),var(--white)}
/* 角上一枚淡墨印（不压主字） */
.ghost{position:absolute;left:__GLEFT__;top:__GTOP__;transform:translate(-50%,-50%);
 font-family:var(--f-brush);font-size:__GFS__;line-height:1;
 color:rgba(26,26,24,__GO__);user-select:none}
.hero-char{position:absolute;left:50%;top:__HTOP__;transform:translate(-50%,-50%);
 font-family:var(--f-brush);font-size:__HFS__;line-height:1;color:var(--ink)}
/* 竖排金句：两列右起 */
.quote{position:absolute;right:__QR__;top:__QTOP__;transform:translateY(-50%);
 writing-mode:vertical-rl;font-family:var(--f-brush);font-size:__QFS__;
 letter-spacing:__QLS__;line-height:2.0;color:var(--ink)}
/* 出处竖排，独立一列在最右 */
.src{position:absolute;right:__SRCR__;top:__QTOP__;transform:translateY(-50%);
 writing-mode:vertical-rl;font-family:var(--f-body);font-size:__SFS__;
 letter-spacing:6px;color:var(--ink2)}
.seal{position:absolute;right:__SR__;top:__ST__;width:__SS__;height:__SS__}
.sub{position:absolute;left:50%;top:__SUBT__;transform:translateX(-50%);
 font-family:var(--f-body);font-size:__SUBFS__;letter-spacing:__SUBLS__;color:var(--ink2);z-index:3}
.era{position:absolute;left:50%;bottom:__EB__;transform:translateX(-50%);z-index:3;
 text-align:center;font-family:Georgia,'Times New Roman',serif}
.era .en{font-size:__ENFS__;letter-spacing:__ENLS__;color:var(--ink);text-transform:uppercase}
.era .years{margin-top:__YMT__;font-size:__YFS__;letter-spacing:5px;color:var(--ink2)}
.mountains{position:absolute;left:0;bottom:0;width:100%;height:__MH__;z-index:2}
.mist{position:absolute;left:0;bottom:0;width:100%;height:__MH2__;z-index:1}
.brand{position:absolute;left:__BL__;bottom:__BB__;z-index:3;font-family:var(--f-body);
 font-size:__BFS__;letter-spacing:__BLS__;color:var(--ink2)}
.brand b{font-family:var(--f-brush);font-weight:400;font-size:__BFS2__;letter-spacing:7px;color:var(--ink)}
.brand .dot{display:inline-block;width:__BD__;height:__BD__;border-radius:50%;
 background:var(--cinnabar);margin:0 __BDM__ 1px;vertical-align:middle}
.brand sup{font-size:.62em;letter-spacing:1px}
.cinnabar-dot{position:absolute;left:calc(50% + __CDX__);top:calc(__HTOP__ - __CDY__);
 width:__CD__;height:__CD__;border-radius:50%;background:var(--cinnabar);
 box-shadow:20px 24px 0 -7px rgba(176,56,38,.32)}
</style></head><body><div class="stage">
  <div class="ghost">__GHOST__</div>
  <div class="hero-char">__CHAR__</div>
  <div class="cinnabar-dot"></div>
  <div class="quote">__QUOTE__</div>
  <div class="src">__SRC__</div>
  <div class="sub">__SUB__</div>
  <img class="seal" src="file://__SEAL__">
  <div class="era"><div class="en">__EN__</div><div class="years">__YEARS__</div></div>
  <svg class="mountains" viewBox="0 0 1200 340" preserveAspectRatio="none">
    <path d="M0,340 L0,238 Q160,180 320,214 Q420,232 520,196 Q650,150 760,196
             Q880,244 1010,208 Q1150,168 1200,206 L1200,340 Z" fill="rgba(26,26,24,.05)"/>
    <path d="M0,340 L0,282 Q220,246 380,268 Q540,290 700,262 Q860,236 1040,266
             Q1150,296 1200,264 L1200,340 Z" fill="rgba(26,26,24,.10)"/>
  </svg>
  <svg class="mist" viewBox="0 0 1200 260" preserveAspectRatio="none">
    <path d="M0,260 L0,150 Q240,96 470,140 Q700,184 930,132 Q1160,80 1200,128 L1200,260 Z"
          fill="rgba(26,26,24,.028)"/>
  </svg>
  <!-- 2026-10-02 方案①：去掉英文品牌 TANTSE，补上网址（桌面版原本没有网址） -->
  <div class="brand"><b>第七境</b><sup class="tm">TM</sup><span class="dot"></span>www.theseventhrealm.com</div>
</div></body></html>"""

VARS = {
    'desktop': dict(w=1920, h=1080, glow='1400px 700px', gleft='14%', gtop='74%',
                    gfs='300px', go='.06', htop='43%', hfs='430px', qr='168px', qtop='46%',
                    qfs='54px', qls='22px', sfs='22px', srcr='108px', sr='88px', st='70%',
                    ss='104px', subt='67%', subfs='24px', subls='14px', eb='150px',
                    # 印章放在金句下方、英文上方（避让 quote 与 src）
                    enfs='24px', enls='12px', ymt='13px', yfs='19px', mh='330px', mh2='250px',
                    bl='64px', bb='46px', bfs='17px', bls='6px', bfs2='22px', bd='9px',
                    bdm='12px', cdx='168px', cdy='172px', cd='17px'),
    'mobile': dict(w=1170, h=2532, glow='900px 900px', gleft='17%', gtop='72%', gfs='360px',
                   go='.06', htop='37%', hfs='500px', qr='150px', qtop='34%', qfs='60px',
                   qls='30px', sfs='28px', srcr='96px', sr='96px', st='60%', ss='140px',
                   subt='60%', subfs='36px', subls='18px', eb='270px', enfs='34px',
                   enls='12px', ymt='20px', yfs='27px', mh='500px', mh2='400px', bl='88px',
                   bb='126px', bfs='29px', bls='9px', bfs2='38px', bd='13px', bdm='16px',
                   cdx='228px', cdy='238px', cd='23px'),
}


def build(era, kind):
    html = HEAD
    for k, val in VARS[kind].items():
        html = html.replace(f'__{k.upper()}__', str(val))
    html = (html.replace('__MSZ__', str(FONT_MSZ)).replace('__SERIF__', str(FONT_SERIF))
                .replace('__SEAL__', str(SEAL))
                .replace('__GHOST__', era['ghost']).replace('__CHAR__', era['h1'])
                .replace('__QUOTE__', two_cols(era['verse'])).replace('__SRC__', era['src'])
                .replace('__EN__', era['en']).replace('__YEARS__', era['enyears'])
                .replace('__SUB__', era['sub']))
    return html


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    OUT.mkdir(parents=True, exist_ok=True)
    eras = load_eras()
    todo = eras if '--all' in sys.argv else [e for e in eras if e['slug'] in (args or ['shang'])]
    for e in todo:
        for kind in ('desktop', 'mobile'):
            p = OUT / f"{e['slug']}-{kind}.html"
            p.write_text(build(e, kind), encoding='utf-8')
            print('生成', p)
