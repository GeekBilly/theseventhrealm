# -*- coding: utf-8 -*-
"""落款区矩形对照：商/周 v9（母版） vs 姓氏线范式版 —— 校验「逐像素一致」。

用法：
  python3 11-运营/scripts/rect-compare.py

原理：往两份 HTML 注入同样的测量脚本（Chrome --dump-dom），
      打印 .colophon / .brand-block 及其子元素的 getBoundingClientRect，
      逐项比对 top/bottom/height/left/width。
"""
import pathlib
import re
import subprocess

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
CH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TMP = ROOT / '11-运营' / 'tmp-rect.html'

SELS = ['.colophon', '.colophon .vstack.cjk', '.colophon .vstack.cjk span',
        '.colophon .vdot', '.colophon-seal', '.brand-block',
        '.brand-block .brand-en', '.brand-block .brand-url']

INJECT = """
<script>
window.addEventListener('load', function () {
  var sels = %s;
  var out = [];
  sels.forEach(function (s) {
    var e = document.querySelector(s);
    if (!e) { out.push(s + '=NONE'); return; }
    var r = e.getBoundingClientRect();
    out.push([s, r.left, r.top, r.width, r.height].map(function (v, i) {
      return i ? (+v).toFixed(1) : v; }).join(' '));
  });
  var d = document.createElement('div');
  d.textContent = 'RECTS|' + out.join('|');
  document.body.appendChild(d);
});

</script>
</body>""" % (repr(SELS).replace("'", '"'),)


def measure(path, label):
    src = pathlib.Path(path).read_text(encoding='utf-8')
    TMP.write_text(src.replace('</body>', INJECT), encoding='utf-8')
    p = subprocess.run([CH, '--headless=new', '--disable-gpu',
                        '--allow-file-access-from-files',
                        '--virtual-time-budget=5000', '--dump-dom', f'file://{TMP}'],
                       capture_output=True, text=True)
    m = re.search(r'RECTS\|([^<]*)', p.stdout)
    print('=====', label)
    rows = {}
    if not m:
        print('   未取到测量结果')
        return rows
    for item in m.group(1).split('|'):
        sel, l, t, w, h = item.split(' ')
        rows[sel] = (float(l), float(t), float(w), float(h))
        print(f'   {sel:34s} left {l:>8s}  top {t:>8s}  w {w:>8s}  h {h:>8s}')
    print()
    return rows


mater = measure(ROOT / '02-商品/03-字形线/版式/wallpaper-商-v9.html', '母版 wallpaper-商-v9')
sur = measure(ROOT / '02-商品/06-姓氏线/版式/_build-figure/surname-001-赵--paradigm.html',
              '姓氏线 surname-001-赵--paradigm')

print('===== 差异（姓氏 − 商）：>0.6px 即不一致')
bad = 0
for k in SELS:
    if k not in mater or k not in sur:
        print(f'   {k:34s} 缺项（母版 {"有" if k in mater else "无"} / 姓氏 {"有" if k in sur else "无"}）')
        continue
    d = [b - a for a, b in zip(mater[k], sur[k])]
    flag = 'OK' if max(abs(x) for x in d) <= 0.6 else '⚠️ 不一致'
    if flag != 'OK':
        bad += 1
    print(f'   {k:34s} Δleft {d[0]:+7.1f}  Δtop {d[1]:+7.1f}  '
          f'Δw {d[2]:+7.1f}  Δh {d[3]:+7.1f}   {flag}')
print('\n结论：' + ('落款区与商/周母版逐像素一致 ✅' if bad == 0 else f'有 {bad} 项不一致 ❌'))
