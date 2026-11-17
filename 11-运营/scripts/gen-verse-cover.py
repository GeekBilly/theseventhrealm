# -*- coding: utf-8 -*-
"""每日一句金句 · 当日封面生成器（本地零积分）

严格套用百家姓封面母版 `02-商品/06-姓氏线/版式/gen-cover-v2.py` 的版式骨架，
只换文字内容：字体、朱砂红线、清单、灰细线、朱砂钩子、规格行、方框印全部原样。
每天一张封面，内容＝当天要发的那一句（按 --day 从金句库 CSV 取）。

  kicker  第七境 · 上下五千年              （不动）
  H1      30 句古籍金句手机壁纸            （不动）
  H2      <当日关键词> · 上下五千年        ← 赵钱孙李 → 百家姓（每日变化）
  list    当日壁纸句 + 出处                ← 4 姓 · 人名（每日变化，只留当天一句）
  hook    想要原图 · 后台滴滴我            （不动，已验证文案，不自创）
  spec    iPhone 1179×2556 · Android 1080×2400（不动）
  seal    第七境                           （不动）

用法：
  python3 gen-verse-cover.py --day=D01        # 出当日封面 PNG（默认 D01）
  python3 gen-verse-cover.py --day=D01 --no-shot  # 只出 HTML
产出：04-市场/03-推广获客/金句日更-202611/封面-3x4/金句-Dxx-<关键词>-封面-1179x1572.png
"""
import argparse
import csv
import html
import pathlib
import subprocess

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
BASE = ROOT / '04-市场/03-推广获客/金句日更-202611'
OUT = BASE / '封面-3x4'
BUILD = OUT / '_build'
CSV = BASE / '金句库-30条.csv'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

W, H = 1179, 1572                 # 小红书 3:4（与百家姓封面同）
HOOK = '想要原图 · 后台滴滴我'     # 基准图原文照抄，已验证，不要自创
H1 = '30 句古籍金句手机壁纸'


def load_day(day):
    """按 Dxx 从 CSV 取当日金句；返回 (关键词, 壁纸句, 朝代, 作者, 出处)。"""
    n = int(day[1:])
    with CSV.open(encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if int(r['序号']) == n:
                return (r['关键词'], r['壁纸句'], r['朝代'], r['作者'], r['出处'])
    raise SystemExit(f'CSV 找不到 {day}')


TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@font-face{{font-family:'Noto Serif SC Black Local';
  src:url('file://{ROOT}/02-商品/02-素材/字体/nssc-black.woff2') format('woff2');
  font-weight:900}}
:root{{--ink:#1a1a18;--cinnabar:#b03826;
  --f-body:'Noto Serif SC','Songti SC',Georgia,serif}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#fff}}
.stage{{width:{W}px;height:{H}px;background:#fff;display:flex;flex-direction:column;
  align-items:center;text-align:center;font-family:var(--f-body);color:var(--ink)}}

.kicker{{margin-top:148px;font-size:27px;letter-spacing:11px;text-indent:11px;color:#6b675f}}
.rule-red{{margin-top:38px;width:840px;height:3px;background:var(--cinnabar)}}
.h1{{margin-top:100px;font-family:'Noto Serif SC Black Local','Songti SC',serif;font-weight:900;
  font-size:96px;line-height:1.15;letter-spacing:4px;text-indent:4px;color:var(--ink)}}
.h2{{margin-top:42px;font-weight:700;font-size:44px;letter-spacing:9px;text-indent:9px;color:#3d3931}}

.list{{margin-top:88px;font-size:32px;letter-spacing:7px;text-indent:7px;color:#3d3931;line-height:2.05}}
.list .nm{{font-weight:700}}
.list .src{{font-size:28px;color:#6b675f;letter-spacing:5px;text-indent:5px}}

.rule-gray{{margin-top:74px;width:840px;height:1px;background:#ded7c9}}

.hook{{margin-top:82px;font-weight:900;font-size:64px;letter-spacing:5px;text-indent:5px;color:var(--cinnabar)}}
.spec{{margin-top:52px;font-size:25px;letter-spacing:3px;color:#78736a}}
.spec2{{margin-top:22px;font-size:25px;letter-spacing:3px;color:#78736a}}

.seal{{margin-top:60px;width:152px;height:94px;border:4px solid var(--cinnabar);
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:34px;letter-spacing:7px;text-indent:7px;color:var(--cinnabar)}}
</style>
</head>
<body>
<div class="stage">
  <div class="kicker">第七境 · 上下五千年</div>
  <div class="rule-red"></div>

  <div class="h1">{H1}</div>
  <div class="h2">{H2}</div>

  <div class="list">
    <div><span class="nm">{verse}</span></div>
    <div class="src">{dynasty}·{author}《{book}》</div>
  </div>

  <div class="rule-gray"></div>

  <div class="hook">{HOOK}</div>
  <div class="spec">iPhone 1179×2556 · Android 1080×2400</div>
  <div class="spec2">无水印 · 可直接设为手机壁纸</div>

  <div class="seal">第七境</div>
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--day', default='D01', help='D01..D30，默认 D01')
    ap.add_argument('--no-shot', action='store_true')
    a = ap.parse_args()
    day = a.day.upper()

    kw, verse, dynasty, author, book = load_day(day)
    h2 = f'{kw} · 上下五千年'
    html_s = TPL.format(
        ROOT=ROOT, W=W, H=H, H1=H1, H2=html.escape(h2), HOOK=HOOK,
        verse=html.escape(verse), dynasty=html.escape(dynasty),
        author=html.escape(author), book=html.escape(book),
    )

    OUT.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    stem = f'金句-{day}-{kw}-封面'
    hpath = BUILD / f'{stem}.html'
    hpath.write_text(html_s, encoding='utf-8')
    print(f'✓ HTML {hpath.name} | {day} {verse} | {h2}')

    if a.no_shot:
        return

    png = OUT / f'{stem}-{W}x{H}.png'
    if png.exists():
        png.unlink()
    subprocess.run([CHROME, '--headless=new', '--no-sandbox', '--disable-setuid-sandbox',
                    '--disable-gpu', '--hide-scrollbars', '--allow-file-access-from-files',
                    f'--user-data-dir=/tmp/cp-verse-cover-{day}', '--force-device-scale-factor=1',
                    f'--window-size={W},{H}', '--virtual-time-budget=8000',
                    f'--screenshot={png}', f'file://{hpath}'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    ok = png.exists() and png.stat().st_size > 0
    print(f'  {"✓" if ok else "✗"} {png.name if ok else "截图失败"}')


if __name__ == '__main__':
    main()
