# -*- coding: utf-8 -*-
"""把「生图进度台账」补全为 100 行（原表只填到 13 行）。
状态口径：待出 / 已出 / 占位图（待重画）；素材文件按 figure-<序号>-<姓>.png 命名。
原有行（尤其赵的占位说明）原样保留，不覆盖。
"""
import csv
import pathlib

R = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
DIR = R / '02-商品/06-姓氏线/底纹-人物'
MD = R / 'research/姓氏代表人物名单-首批100-2026-10-03.md'
LEDGER = DIR / '生图进度台账.csv'

text = MD.read_text(encoding='utf-8')
lines = text.split('\n')

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
            rows.append(dict(no=c[0], xing=c[1].strip('*'), main=c[3].strip('*'),
                             dyn=c[4], ident=c[5], src=c[6]))
assert len(rows) == 100, len(rows)

adesc = {}
in_code = False
for ln in lines:
    if ln.strip() == '```':
        in_code = not in_code
        continue
    if in_code and ' · ' in ln and '——' in ln:
        k, v = ln.split(' · ', 1)
        person, desc = v.split('——', 1)
        adesc[k.strip()] = desc.strip()

old = {}
if LEDGER.exists():
    with LEDGER.open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            x = (r.get('姓') or '').strip()
            if x:
                old[x] = r

out = []
for r in rows:
    x = r['xing']
    o = old.get(x, {})
    st = (o.get('生图状态') or '').strip() or '待出'
    fname = (o.get('素材文件') or '').strip()
    note = (o.get('说明') or '').strip()
    if not note:
        note = f'{r["main"]}｜{r["dyn"]}·{r["ident"]}｜{adesc.get(x, "")}'
    if not fname:
        fname = f'figure-{int(r["no"]):03d}-{x}.png' if st != '待出' else ''
    out.append(dict(序号=r['no'], 姓=x, 主形象=r['main'], 生图状态=st,
                    素材文件=fname, 说明=note))

with LEDGER.open('w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['序号', '姓', '主形象', '生图状态', '素材文件', '说明'])
    w.writeheader()
    w.writerows(out)

done = sum(1 for r in out if r['生图状态'] != '待出')
print(f'台账已补全：{len(out)} 行 | 非「待出」{done} 行')
