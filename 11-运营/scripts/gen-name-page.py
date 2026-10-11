# -*- coding: utf-8 -*-
"""生成「首批 100 姓 · 底纹人物逐个确认页」（静态 HTML，本地零依赖）。
数据源：
  research/姓氏代表人物名单-首批100-2026-10-03.md  （主表 + §A 生图描述 + §B 疑难）
  02-商品/06-姓氏线/底纹-人物/生图进度台账.csv      （生图状态）
"""
import csv
import html
import pathlib
import re

R = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
MD = R / 'research/姓氏代表人物名单-首批100-2026-10-03.md'
LEDGER = R / '02-商品/06-姓氏线/底纹-人物/生图进度台账.csv'
OUT = R / '02-商品/06-姓氏线/底纹-人物/名单-确认页.html'

text = MD.read_text(encoding='utf-8')
lines = text.split('\n')

# ── ① 主表 ──────────────────────────────────────────────
rows = []
in_tbl = False
for ln in lines:
    if ln.startswith('| 序 | 姓 |'):
        in_tbl = True
        continue
    if in_tbl:
        if not ln.startswith('|'):
            break
        if set(ln) <= set('|- '):
            continue
        c = [x.strip() for x in ln.strip('|').split('|')]
        if len(c) >= 8:
            rows.append(dict(no=c[0], xing=c[1], who=c[2], main=c[3],
                             dyn=c[4], ident=c[5], src=c[6], conf=c[7]))
assert len(rows) == 100, len(rows)

# ── ② §A 生图描述 ───────────────────────────────────────
a_map = {}
in_code = False
for ln in lines:
    if ln.strip() == '```':
        in_code = not in_code
        continue
    if in_code and ' · ' in ln and '——' in ln:
        k, v = ln.split(' · ', 1)
        person, desc = v.split('——', 1)
        a_map[k.strip()] = (person.strip(), desc.strip())

# ── ③ §B 疑难点名 ──────────────────────────────────────
warn = {}
for ln in lines:
    if not ln.startswith('|'):
        continue
    for ch in ['**水**', '**昌**', '**凤**', '**酆**', '**邬**', '**喻**', '**柏**',
               '**云**', '**时**', '**郎**', '**平**', '**和**', '**卞**',
               '**皮**', '**康**', '**穆**', '**尹**']:
        if ln.startswith('| ' + ch + ' |'):
            c = [x.strip() for x in ln.strip('|').split('|')]
            if len(c) >= 3:
                warn[c[0].strip('*')] = '候选偏少／证据偏弱：' + c[2][:110]
b3 = {}
for ln in lines:
    if ln.startswith('|') and '|' in ln:
        c = [x.strip() for x in ln.strip('|').split('|')]
        if len(c) >= 3 and c[0] in ('云敞', '水乡漠', '昌豨', '邬彤', '韦孝宽', '齐己',
                                    '毕昇', '傅说', '尹吉甫', '卜商（子夏）', '穆崇'):
            b3[c[0].strip('*')] = c[1][:90]

# ── ④ 台账状态 ─────────────────────────────────────────
led = {}
if LEDGER.exists():
    with LEDGER.open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            led[(r.get('姓') or '').strip()] = (r.get('生图状态') or '').strip()

FIGDIR = R / '02-商品/06-姓氏线/底纹-人物'
figs = {f.name.split('-')[-1].replace('.png', ''): f.name
        for f in FIGDIR.glob('figure-*.png')}

CONF_COLOR = {'high': '#2f6b47', 'medium': '#a8721c', 'low': '#b03826'}

cards = []
for r in rows:
    x = r['xing'].strip('*')
    person, desc = a_map.get(x, ('', ''))
    st = led.get(x, '')
    fig = figs.get(x)
    if fig:
        badge, bcolor = '底纹已出', '#2f6b47'
        if '占位' in st:
            badge, bcolor = '底纹为占位图（待重画）', '#b03826'
    else:
        badge, bcolor = '底纹待出', '#8a8580'
    w = warn.get(x)
    b3hit = b3.get(r['main'].strip('*'))
    warns = []
    if w:
        warns.append(w)
    if b3hit:
        warns.append('形象难点：' + b3hit)
    whtml = ''
    if warns:
        items = ''.join(f'<li>{html.escape(t)}</li>' for t in warns)
        whtml = f'<div class="warn"><b>⚠️ 注意</b><ul>{items}</ul></div>'
    cc = CONF_COLOR.get(r['conf'], '#54504a')
    cards.append(f'''<div class="card" data-xing="{x}">
  <div class="hd">
    <label class="pick"><input type="checkbox" data-k="{x}"><span class="bx"></span></label>
    <div class="no">{r['no']}</div>
    <div class="xing">{x}</div>
    <div class="main">{html.escape(r['main'].strip('*'))}</div>
    <div class="badge" style="color:{bcolor};border-color:{bcolor}">{badge}</div>
  </div>
  <div class="meta"><span class="k">朝代</span>{html.escape(r['dyn'])}　<span class="k">身份</span>{html.escape(r['ident'])}</div>
  <div class="meta2"><span class="k">出处</span>{html.escape(r['src'])}　<span class="k">置信度</span><b style="color:{cc}">{html.escape(r['conf'])}</b></div>
  <div class="cands"><span class="k">候选人物</span>{html.escape(r['who'].replace('**',''))}</div>
  <div class="desc"><span class="k">生图描述</span>{html.escape(desc) if desc else '（缺）'}</div>
  {whtml}
</div>''')

warn_n = len([r for r in rows if r['xing'].strip('*') in warn or r['main'].strip('*') in b3])

html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>首批 100 姓 · 底纹人物逐个确认</title>
<style>
  @font-face{{font-family:'msz';src:url('file:///Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/02-素材/字体/MaShanZheng.ttf')}}
  :root{{--ink:#22201c;--ink2:#54504a;--ink3:#8a8580;--line:#e2ddd3;--bg:#faf8f4;--cinnabar:#b03826}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);
    font-family:'Noto Serif SC','Songti SC',Georgia,serif;line-height:1.7}}
  header{{position:sticky;top:0;z-index:9;background:rgba(250,248,244,.96);
    border-bottom:1px solid var(--line);padding:18px 28px 14px;backdrop-filter:blur(6px)}}
  h1{{margin:0 0 6px;font-size:21px;letter-spacing:2px;font-weight:600}}
  .sub{{color:var(--ink2);font-size:13.5px}}
  .bar{{display:flex;gap:14px;align-items:center;margin-top:10px;flex-wrap:wrap;font-size:13px}}
  .bar input[type=search]{{font:inherit;font-size:13px;padding:5px 10px;width:200px;
    border:1px solid var(--line);border-radius:3px;background:#fff}}
  .sw{{cursor:pointer;border:1px solid var(--line);background:#fff;border-radius:14px;
    padding:3px 12px;user-select:none}}
  .sw.on{{background:#26241f;color:#f6f4ef;border-color:#26241f}}
  #stat{{color:var(--cinnabar);font-weight:600}}
  main{{padding:20px 28px 60px;display:grid;grid-template-columns:repeat(auto-fill,minmax(430px,1fr));gap:14px}}
  .card{{background:#fff;border:1px solid var(--line);border-radius:5px;padding:14px 16px 12px;position:relative}}
  .card.hide{{display:none}}
  .card.sel{{border-color:var(--cinnabar);box-shadow:0 0 0 1px var(--cinnabar) inset}}
  .hd{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
  .pick{{display:inline-flex;align-items:center;cursor:pointer}}
  .pick input{{display:none}}
  .bx{{width:15px;height:15px;border:1.5px solid var(--ink3);border-radius:2px;display:inline-block;position:relative;top:2px}}
  .pick input:checked + .bx{{background:var(--cinnabar);border-color:var(--cinnabar)}}
  .pick input:checked + .bx::after{{content:'';position:absolute;left:4px;top:1px;width:4px;height:8px;
    border-right:2px solid #fff;border-bottom:2px solid #fff;transform:rotate(40deg)}}
  .no{{color:var(--ink3);font-size:12.5px;min-width:22px}}
  .xing{{font-family:'msz','Ma Shan Zheng','Kaiti SC',serif;font-size:34px;line-height:1.1}}
  .main{{font-size:16.5px;font-weight:600;letter-spacing:.5px}}
  .badge{{margin-left:auto;font-size:11.5px;border:1px solid;border-radius:11px;padding:1px 9px;white-space:nowrap}}
  .k{{color:var(--ink3);font-size:12px;margin-right:5px;letter-spacing:1px}}
  .meta,.meta2,.cands{{font-size:13px;color:var(--ink2);margin-top:5px}}
  .desc{{font-size:13px;color:var(--ink2);margin-top:7px;padding-top:7px;border-top:1px dashed var(--line)}}
  .warn{{margin-top:8px;font-size:12.5px;color:#8a4b16;background:#fdf6ea;
    border-left:3px solid #d99b3e;padding:6px 10px;border-radius:0 3px 3px 0}}
  .warn ul{{margin:4px 0 0 16px;padding:0}}
  .warn li{{margin:2px 0}}
  footer{{padding:0 28px 40px;color:var(--ink3);font-size:12.5px}}
</style>
</head>
<body>
<header>
  <h1>首批 100 姓 · 底纹人物逐个确认</h1>
  <div class="sub">《百家姓》第 1–100 姓。每位主形象一行：勾选＝认可该人物与画面；不勾＝明天再议。勾选状态自动存在本机浏览器。</div>
  <div class="bar">
    <span>已勾选 <b id="stat">0</b> / 100</span>
    <input type="search" id="q" placeholder="搜姓或人名…">
    <span class="sw" id="sw-warn">只看 ⚠️ 需注意（{warn_n}）</span>
    <span class="sw" id="sw-fig">只看底纹未出</span>
    <span class="sw on" id="sw-all">全部</span>
    <span id="reset" class="sw">清空勾选</span>
  </div>
</header>
<main>
{''.join(cards)}
</main>
<footer>
  数据源：research/姓氏代表人物名单-首批100-2026-10-03.md（主表＋§A 生图描述＋§B 疑难）·
  台账：02-商品/06-姓氏线/底纹-人物/生图进度台账.csv<br>
  生图口径：水墨剪影、单色高对比留白；成品底纹为人物全身、右对齐进画（不裁）。
</footer>
<script>
const KEY='qijing-surname-pick-v1';
const saved=JSON.parse(localStorage.getItem(KEY)||'{{}}');
const cards=[...document.querySelectorAll('.card')];
const boxes=[...document.querySelectorAll('input[type=checkbox]')];
function save(){{const o={{}};boxes.forEach(b=>{{if(b.checked)o[b.dataset.k]=1}});
  localStorage.setItem(KEY,JSON.stringify(o));}}
function stat(){{const n=boxes.filter(b=>b.checked).length;
  document.getElementById('stat').textContent=n;
  cards.forEach(c=>{{const b=c.querySelector('input');
    c.classList.toggle('sel',b.checked); b.dataset.fig=(/待出|占位/.test(c.querySelector('.badge').textContent))?'0':'1';
  }});}}
boxes.forEach(b=>{{if(saved[b.dataset.k])b.checked=true;
  b.addEventListener('change',()=>{{save();stat();}});}});
stat();
let mode='all';
function apply(){{
  const q=document.getElementById('q').value.trim();
  cards.forEach(c=>{{
    let ok=true;
    if(mode==='warn') ok=!!c.querySelector('.warn');
    if(mode==='fig')  ok=/待出|占位/.test(c.querySelector('.badge').textContent);
    if(q) ok=ok&&(c.dataset.xing.includes(q)||c.textContent.includes(q));
    c.classList.toggle('hide',!ok);
  }});
}}
document.getElementById('q').addEventListener('input',apply);
[['sw-warn','warn'],['sw-fig','fig'],['sw-all','all']].forEach(([id,m])=>{{
  document.getElementById(id).addEventListener('click',()=>{{
    mode=m;[...document.querySelectorAll('.sw')].forEach(e=>e.classList.remove('on'));
    document.getElementById(id).classList.add('on');apply();
  }});
}});
document.getElementById('reset').addEventListener('click',()=>{{
  if(confirm('清空全部勾选？')){{localStorage.removeItem(KEY);boxes.forEach(b=>b.checked=false);save();stat();}}
}});
apply();
</script>
</body>
</html>
'''
OUT.write_text(html_doc, encoding='utf-8')
print('已生成', OUT)
print('卡数', len(cards), '| 生图描述命中', len(a_map), '| 疑难点名', warn_n, '| 台账行', len(led))
