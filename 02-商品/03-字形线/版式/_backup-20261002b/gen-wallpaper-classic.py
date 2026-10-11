# -*- coding: utf-8 -*-
"""字形线 · v9 桌面横版商品化（原样转商品，只加两处商品要素）。

只加：
  1. 品牌落款后补 ™（商标未核准的法定标识）
  2. 左上角补一枚系列小标「上 下 五 千 年 · X」（成系列商品的识别）
其余一字不动 —— 用户明确「原样拿过来」。

输出：02-商品/05-承接站/样张/{slug}-v9-{std,mac}.html
截图由 build-classic.sh 用系统 Chrome 完成（1x + 2x）。

用法：python3 gen-wallpaper-classic.py            # 商 + 周
      python3 gen-wallpaper-classic.py zhou       # 只出周
"""
import pathlib, sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
SRC = ROOT / '02-商品/03-字形线/版式'
OUT = ROOT / '02-商品/05-承接站/样张'

ERAS = {
    'shang': dict(name='商', tpl='wallpaper-商-v9{sfx}.html'),
    'zhou':  dict(name='周', tpl='wallpaper-周-v9{sfx}.html'),
}

# 规格：std = 1920×1080，mac = 1920×1248（截图时 2x 得 4K）
SPECS = {'std': ('', 1920, 1080), 'mac': ('-mac', 1920, 1248)}

CSS = """
/* ===== 商品要素：系列小标 + 商标标识 ===== */
.series-tag{position:absolute;left:210px;top:66px;z-index:2;
  font-family:var(--f-body);font-size:16px;letter-spacing:6px;color:#6b675f}
.tm{font-size:15px;vertical-align:super;letter-spacing:0;margin-left:4px;color:var(--ink)}
"""

ANCHOR = '  <!-- 展卷最先看到：右起题跋（贴顶） -->'


def build(slug, spec):
    era = ERAS[slug]
    sfx, w, h = SPECS[spec]
    src = SRC / era['tpl'].format(sfx=sfx)
    html = src.read_text(encoding='utf-8')

    a = '<div class="brand-en">THE SEVENTH REALM</div>'
    b = '<div class="brand-en">THE SEVENTH REALM<span class="tm">™</span></div>'
    if a not in html:
        print(f'  ✗ {src.name}: 未找到品牌落款锚点，跳过'); return None
    html = html.replace(a, b)

    if ANCHOR in html:
        html = html.replace(ANCHOR,
            f'  <!-- 系列小标（商品要素） -->\n'
            f'  <div class="series-tag">上 下 五 千 年 · {era["name"]}</div>\n\n' + ANCHOR)
    else:
        print(f'  ! {src.name}: 未找到题跋锚点，系列标未插入')

    html = html.replace('</style>', CSS + '</style>')

    out = OUT / f'{slug}-v9-{spec}.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    print(f'  ✓ {out.name}  ({w}×{h}，截图 2x 得 {w*2}×{h*2})')
    return out


if __name__ == '__main__':
    want = [a for a in sys.argv[1:] if not a.startswith('-')] or list(ERAS)
    for s in want:
        if s not in ERAS:
            print('未知朝代', s); continue
        print(f'[{ERAS[s]["name"]}]')
        for spec in SPECS:
            build(s, spec)
