#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 · 姓氏源流壁纸生成器（B 线）

数据源：`百家姓-交叉验证.json`（7 源交叉验证，504 姓）
       单姓 444 + 复姓 60；每姓带 order / 简体 / 繁体 / 审核状态

设计：与金句线**同一套视觉语言**（宣纸白 · 毛笔主字 · 朱砂点 · 淡墨水印 · 远山 · 印章），
      保证两条线能组合成套餐而不违和。

用法：
  python3 02-商品/06-姓氏线/版式/gen-surname-wallpaper.py --first 100
  python3 02-商品/06-姓氏线/版式/gen-surname-wallpaper.py 赵 钱 孙
  python3 02-商品/06-姓氏线/版式/gen-surname-wallpaper.py --all

产出：02-商品/05-承接站/样张/surname-<序>-<字>.html
本地零 AI 成本。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
DATA = ROOT / '百家姓-交叉验证.json'
OUT = ROOT / '02-商品/05-承接站/样张'
FONT_MSZ = ROOT / '02-商品/02-素材/字体/MaShanZheng.ttf'
FONT_SERIF = ROOT / '02-商品/02-素材/字体/fonts/NotoSerifSC-Black.ttf'
SEAL = ROOT / '02-商品/02-素材/底纹/seal-hi.png'

# 版面参数：桌面 1920×1080（与金句线桌面版一致，便于混搭）
V = dict(w=1920, h=1080, glow='1400px 700px', gleft='14%', gtop='74%',
         gfs='300px', go='.055', htop='43%', qr='168px', qtop='46%',
         qfs='54px', qls='22px', sfs='22px', srcr='108px', sr='88px', st='70%',
         ss='104px', subt='67%', subfs='24px', subls='14px', eb='150px',
         # 2026-10-02 新增：左上系列标记 / 主字上方小标 / 主字下方拼音
         serl='64px', sert='52px', serfs='22px', serls='6px',
         capt='21%', capfs='23px', capls='10px',
         pyt='67%', pyfs='26px', pyls='12px',
         enfs='24px', enls='12px', ymt='13px', yfs='19px', mh='330px', mh2='250px',
         bl='64px', bb='46px', bfs='17px', bls='6px', bfs2='22px', bd='9px',
         bdm='12px', cdx='168px', cdy='172px', cd='17px')

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
/* 淡墨水印：一个「氏」字押角 */
.ghost{position:absolute;left:__GLEFT__;top:__GTOP__;transform:translate(-50%,-50%);
 font-family:var(--f-brush);font-size:__GFS__;line-height:1;
 color:rgba(26,26,24,__GO__);user-select:none}
.hero-char{position:absolute;left:50%;top:__HTOP__;transform:translate(-50%,-50%);
 font-family:var(--f-brush);font-size:__HFS__;line-height:1;color:var(--ink);white-space:nowrap}
.quote{position:absolute;right:__QR__;top:__QTOP__;transform:translateY(-50%);
 writing-mode:vertical-rl;font-family:var(--f-brush);font-size:__QFS__;
 letter-spacing:__QLS__;line-height:2.0;color:var(--ink)}
.src{position:absolute;right:__SRCR__;top:__QTOP__;transform:translateY(-50%);
 writing-mode:vertical-rl;font-family:var(--f-body);font-size:__SFS__;
 letter-spacing:6px;color:var(--ink2)}
.seal{position:absolute;right:__SR__;top:__ST__;width:__SS__;height:__SS__}
.sub{position:absolute;left:50%;top:__SUBT__;transform:translateX(-50%);
 font-family:var(--f-body);font-size:__SUBFS__;letter-spacing:__SUBLS__;color:var(--ink2);z-index:3}
/* 2026-10-02 用户定案：参考朝代字形线的版面 ——
   左上角放中文系列标记（对应朝代的「上下五千年 · 商」），
   英文拼音放在主字下边（像三联每格下方的标注）。 */
.series{position:absolute;left:__SERL__;top:__SERT__;z-index:3;
 font-family:var(--f-body);font-size:__SERFS__;letter-spacing:__SERLS__;color:var(--ink2)}
.caption{position:absolute;left:50%;top:__CAPT__;transform:translateX(-50%);z-index:3;
 font-family:var(--f-body);font-size:__CAPFS__;letter-spacing:__CAPLS__;color:var(--ink2)}
.pinyin{position:absolute;left:50%;top:__PYT__;transform:translateX(-50%);z-index:3;
 font-family:Georgia,'Times New Roman',serif;font-size:__PYFS__;letter-spacing:__PYLS__;color:var(--ink2)}
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
  <div class="ghost">氏</div>
  <div class="series">姓氏源流 · __CHAR__</div>
  <div class="caption">__CAPTION__</div>
  <div class="hero-char">__CHAR__</div>
  <div class="cinnabar-dot"></div>
  <div class="pinyin">__PINYIN__</div>
  <div class="quote">__QUOTE__</div>
  <div class="src">__SRC__</div>
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
  <div class="brand"><b>第七境</b><sup class="tm">TM</sup><span class="dot"></span>www.theseventhrealm.com</div>
</div></body></html>"""


def load():
    d = json.loads(DATA.read_text(encoding='utf-8'))
    seq = d['sequence']
    # 原文四字一句：把全部姓氏字按序连起来再四字切（单姓段与刻本一致）
    flat = ''.join(s['simplified'] for s in seq)
    return d, seq, flat


def verse_of(flat, order):
    """order 是姓氏序号（1 起）。返回该姓所在的四字原句。

    ⚠️ 单姓与复姓的字数不同，故原句位置按「已消费的字符数」推算，而不是按姓氏序号。
    """
    return None  # 由 build 时用 char_index 计算


def build(d, seq, flat, item, idx):
    sv = item['simplified']
    order = item['order']
    is_compound = item['type'] == 'compound'
    # 原句：按「字符累计位置」四字一组（不能用 flat.index —— 重复字会找错）
    start = sum(len(s['simplified']) for s in seq[:order - 1])
    if is_compound:                      # 复姓自成一句，不参与四字韵
        verse = sv
    else:
        g = (start // 4) * 4
        verse = flat[g:g + 4]
    n = len(sv)
    hfs = '430px' if n == 1 else '300px'   # 复姓缩小，免得压到周边元素

    # ── 底部两行：时代英文名 + 年份（对标朝代的 `SHANG DYNASTY / c. 1600 – 1046 BC`）──
    om = (d.get('origin_map') or {}).get(sv) or {}
    yr = om.get('approx_year')
    en_line = om.get('era_label_en') or om.get('era_label') or ''
    years_line = om.get('year_display') or ''
    if isinstance(yr, int) and not years_line:
        years_line = (f"c. {abs(yr)} BC" if yr < 0 else f"c. AD {yr}")
    py_line = (d.get('pinyin_map') or {}).get(sv, '')

    quote_html = f'<div class="quote">{verse}</div>' if not is_compound else ''
    # ⚠️ 复姓不出竖排引文：它的"原句"就是它自己，与主字重复（实测确认）

    # ── 定位用「第几句」而不是「第几位」（2026-10-02 用户定案）──
    # 《百家姓》的姓氏顺序是宋代皇室尊卑的产物（赵＝国姓，故列第一），
    # 标「第 N 位」＝论资排辈，会被读成社会排序。
    # 标「第 N 句」是**文本定位**（像引用出处），不含褒贬。
    line_no = start // 4 + 1
    sub_line = f'《百家姓》第 {line_no} 句'

    html = HEAD
    for k, val in V.items():
        html = html.replace(f'__{k.upper()}__', str(val))
    html = html.replace('__HFS__', hfs)
    html = (html.replace('__MSZ__', str(FONT_MSZ)).replace('__SERIF__', str(FONT_SERIF))
                .replace('__SEAL__', str(SEAL))
                .replace('__CHAR__', sv)
                .replace('<div class="quote">__QUOTE__</div>', quote_html)
                .replace('__SRC__', '《百家姓》北宋')
                .replace('__CAPTION__', sub_line)
                .replace('__PINYIN__', py_line)
                .replace('__EN__', en_line)
                .replace('__YEARS__', years_line))
    return html


if __name__ == '__main__':
    d, seq, flat = load()
    OUT.mkdir(parents=True, exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--all' in sys.argv:
        todo = list(enumerate(seq))
    elif '--first' in sys.argv:
        k = int(sys.argv[sys.argv.index('--first') + 1])
        todo = list(enumerate(seq))[:k]
    elif args:
        todo = [(i, s) for i, s in enumerate(seq) if s['simplified'] in args]
    else:
        todo = list(enumerate(seq))[:3]
    for i, item in todo:
        p = OUT / f"surname-{item['order']:03d}-{item['simplified']}.html"
        p.write_text(build(d, seq, flat, item, i), encoding='utf-8')
    print(f'生成 {len(todo)} 个 → {OUT}  （例：{todo[0][1]["simplified"]} … {todo[-1][1]["simplified"]}）')
