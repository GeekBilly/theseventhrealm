# -*- coding: utf-8 -*-
"""量页面元素实际矩形（注入脚本 + Chrome --dump-dom），用于校验三联字/竖排文字的对齐。

用法：python3 11-运营/scripts/dom-rect.py shang-v9-std.html zhou-v9-std.html   # 样张目录下的文件名
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
CH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
OUT = ROOT / '11-运营' / 'tmp-measure.html'

INJECT = """
<script>
window.addEventListener('load', function () {
  var sels = ['.triple', '.triple .cell:nth-child(1) .song-char',
              '.triple .cell:nth-child(2) .brush-char',
              '.triple .cell:nth-child(3) .oracle-box',
              '.triple .cell:nth-child(3) .oracle-glyph',
              '.triple .cell:nth-child(1)', '.triple .cell:nth-child(2)', '.triple .cell:nth-child(3)',
              '.triple .cell:nth-child(1) .cap', '.triple .cell:nth-child(3) .sub',
              '.triple-hint', '.vc', '.series-tag', '.colophon'];
  var out = [];
  sels.forEach(function (s) {
    var e = document.querySelector(s);
    if (!e) { out.push(s + '=NONE'); return; }
    var r = e.getBoundingClientRect();
    out.push(s + '=top' + r.top.toFixed(1) + ',bot' + r.bottom.toFixed(1) +
             ',h' + r.height.toFixed(1) + ',l' + r.left.toFixed(1));
  });
  document.title = 'RECTS|' + out.join('|');
  var d = document.createElement('div');
  d.id = 'measure-out';
  d.textContent = 'RECTS|' + out.join('|');
  document.body.appendChild(d);
});
</script>
</body>"""

for name in sys.argv[1:]:
    src = (ROOT / '02-商品' / '05-承接站' / '样张' / name).read_text(encoding='utf-8')
    OUT.write_text(src.replace('</body>', INJECT), encoding='utf-8')
    p = subprocess.run([CH, '--headless=new', '--disable-gpu', '--allow-file-access-from-files',
                        '--virtual-time-budget=5000', '--dump-dom', f'file://{OUT}'],
                       capture_output=True, text=True)
    m = re.search(r'RECTS\|([^<]*)', p.stdout)
    print('=========', name)
    if not m:
        print('   未取到测量结果')
        continue
    for item in m.group(1).split('|'):
        print('  ', item)
    print()
