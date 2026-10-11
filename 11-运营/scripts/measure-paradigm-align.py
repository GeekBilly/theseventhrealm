# -*- coding: utf-8 -*-
"""范式对齐量测：量「落款两区」的元素矩形与字号，验是否与商/周母版逐像素一致。

背景（2026-10-03 用户定）：**商/周 v9 是母版** —— 其余产品线（姓氏线、后续朝代线）
只换「字 + 底纹」，落款区（⑤ 左下竖排名+朱砂点+印、⑥ 正下中品牌行+网址）
的位置/字号/字距/颜色必须逐像素照抄，不许自己发挥。

用法：
  python3 11-运营/scripts/measure-paradigm-align.py <html1> <html2> ...
  # 参数为绝对路径（file:// 可省略）；每个文件各量一遍，横向比对

量什么：
  .colophon / .vstack.cjk / .vstack.cjk span / .vdot / .colophon-seal
  .brand-block / .brand-en / .brand-url
  .figure（底纹是否整幅进画：left/right/top/bottom 是否越界 1920×1080）
并输出 font-size / letter-spacing，用于验字号一致。
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
CH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
OUT = ROOT / '11-运营' / 'tmp-measure-align.html'

# ⚠️ 金句/出处两线的 DOM 结构不同：A 线（商/周）字在 .vc span 里（flex 竖排），
#    B 线（姓氏）整块是 writing-mode 竖排、字直接是 .quote / .src —— 所以两组都量，
#    比对时只比 **字号与视觉高度**，不比容器矩形。
SELS = ['.colophon', '.vstack.cjk', '.vdot', '.colophon-seal',
        '.brand-block', '.brand-en', '.brand-url', '.figure',
        # ⚠️ A 线 DOM 里 `.vc.src`（出处列）排在金句列**前面**，
        #    所以金句必须写 `.vc:not(.src) span`，写 `.vc span` 量到的是出处（20px）。
        '.quote', '.src', '.vc:not(.src) span', '.vc.src span',
        # 中部主体与左下落款的**防重叠**核查（2026-10-03：落款下移后要确认没压到字）
        '.quat', '.quat .cell', '.meta', '.series',
        # 字下「英文 + 年代」行：A 线是 .era（.en 26px + .years 19px 两行），B 线是 .meta（单行）
        '.era', '.era .en', '.era .years', '.meta .num',
        # 画心正上方标题：A 线 .title-box（.triple-title 20px + .triple-hint 14px），
        # B 线 .series（.t 20px + .h 14px）；左上角系列标 A 线是商品化补丁 .series-tag
        '.title-box', '.triple-title', '.triple-hint',
        '.series .t', '.series .h', '.series-tag', '.brand-en .tm',
        # 画心字格与其间的竖断线（A 线 .triple/.cell/.divider；B 线 .quat/.cell/.divider）
        '.triple', '.triple .cell', '.divider']

# ⚠️ 标记串必须**拆开拼**（['REC','TS|'].join('')）：--dump-dom 会把 <script> 源码一起吐出来，
#    若字面写 'RECTS|'，正则会先命中脚本源码本身，量测结果永远取不到（已踩过一次）。
INJECT = """
<script>
window.addEventListener('load', function () {
  var TAG = ['REC', 'TS|'].join('');
  var sels = %s;
  var out = [];
  sels.forEach(function (s) {
    var e = document.querySelector(s);
    if (!e) { out.push(s + '=NONE'); return; }
    var r = e.getBoundingClientRect(), c = getComputedStyle(e);
    out.push(s + '=l' + r.left.toFixed(1) + ',r' + r.right.toFixed(1) +
             ',t' + r.top.toFixed(1) + ',b' + r.bottom.toFixed(1) +
             ',w' + r.width.toFixed(1) + ',h' + r.height.toFixed(1) +
             ',fs' + c.fontSize + ',ls' + c.letterSpacing + ',ff' +
             (c.fontFamily.split(',')[0] || '').replace(/['"]/g, ''));
  });
  // 竖排名的三个字逐个量（字距与行高是"竖排"的关键）
  var vs = document.querySelectorAll('.vstack.cjk span');
  var vsr = [];
  vs.forEach(function (e) { var r = e.getBoundingClientRect();
    vsr.push(r.left.toFixed(1) + '/' + r.top.toFixed(1) + '/' + r.height.toFixed(1)); });
  if (vsr.length) out.push('vstack.spans=' + vsr.join(' '));
  document.title = TAG + out.join('|');
  var d = document.createElement('div');
  d.id = 'measure-out';
  d.textContent = TAG + out.join('|');
  document.body.appendChild(d);
});
</script>
</body>""" % (str(SELS).replace("'", '"'))


def measure(path):
    src = pathlib.Path(path).read_text(encoding='utf-8')
    OUT.write_text(src.replace('</body>', INJECT), encoding='utf-8')
    p = subprocess.run([CH, '--headless=new', '--disable-gpu',
                        '--allow-file-access-from-files', '--window-size=1920,1080',
                        '--virtual-time-budget=6000', '--dump-dom', f'file://{OUT}'],
                       capture_output=True, text=True)
    m = re.search(r'<title>RECTS\|([^<]*)</title>', p.stdout)
    return m.group(1).split('|') if m else ['未取到测量结果']


def main():
    files = sys.argv[1:]
    if not files:
        raise SystemExit(__doc__)
    res = {}
    for f in files:
        res[f] = measure(f)
        print('=========', pathlib.Path(f).name)
        for it in res[f]:
            print('  ', it)
        print()
    # 逐项比对（第一份为基准）
    if len(files) > 1:
        base = dict(x.split('=', 1) for x in res[files[0]])
        print('========= 与基准「%s」的差异' % pathlib.Path(files[0]).name)
        for f in files[1:]:
            cur = dict(x.split('=', 1) for x in res[f])
            diff = 0
            for k in base:
                b, c = base[k], cur.get(k, 'NONE')
                if b != c:
                    diff += 1
                    print(f'   ✗ {k}\n       基准 {b}\n       当前 {c}')
            print(f'   —— {pathlib.Path(f).name}：{diff} 处不一致'
                  + ('（完全一致 ✅）' if diff == 0 else ''))


if __name__ == '__main__':
    main()
