#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测量页面真实垂直间距（Chrome headless --dump-dom + 注入脚本）。

为什么不靠读 CSS 推算：三件事只有浏览器知道 ——
  1) section 的上下 padding 会**相邻叠加**（两节各 60px ⇒ 中间 120px）；
  2) WordPress 主题还给相邻块留了 margin-block-start:1.2rem(=19px)；
  3) line-height 决定文字行框比字本身高多少（42px 的金句行框 82px）。
所以这里量的是「上一节内容底 → 下一节内容顶」的**视觉空白**，不是 CSS 值。

用法：
  python3 11-运营/scripts/measure-rhythm.py <url>
  python3 11-运营/scripts/measure-rhythm.py <url> --css 待测.css   # 预演：不发布先看效果
  python3 11-运营/scripts/measure-rhythm.py <url> --width 390
"""
import pathlib
import re
import subprocess
import sys

CH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

INJECT = r"""
<script>
window.addEventListener('load', function () {
  function rect(e) { return e.getBoundingClientRect(); }
  function pad(e, k) { return parseFloat(getComputedStyle(e)[k]) || 0; }
  var out = [];
  var secs = Array.prototype.slice.call(document.querySelectorAll('section'));
  out.push('SEC_COUNT=' + secs.length);
  secs.forEach(function (s, i) {
    var r = rect(s), cs = getComputedStyle(s);
    out.push('SEC' + i + '\t' + (s.className || '-') + '\th=' + r.height.toFixed(0) +
             '\tpadT=' + pad(s, 'paddingTop').toFixed(0) +
             '\tpadB=' + pad(s, 'paddingBottom').toFixed(0) +
             '\tmT=' + pad(s, 'marginTop').toFixed(0));
    if (i > 0) {
      // 视觉空白 = 上一节底 padding + 节间 margin + 本节顶 padding
      var raw = rect(s).top - rect(secs[i - 1]).bottom;
      var visual = pad(secs[i - 1], 'paddingBottom') + raw + pad(s, 'paddingTop');
      out.push('GAP' + (i - 1) + '-' + i + '\t' +
               (visual - pad(secs[i - 1], 'paddingBottom') - pad(s, 'paddingTop')).toFixed(0) +
               '\tvisual=' + visual.toFixed(0));
    }
  });
  var ps = document.querySelectorAll('.prose > p');
  if (ps.length > 3) {
    out.push('PARA_GAP\t' + (rect(ps[1]).top - rect(ps[0]).bottom).toFixed(0));
    out.push('PARA_GAP2\t' + (rect(ps[2]).top - rect(ps[1]).bottom).toFixed(0));
  }
  var fl = document.querySelector('.final-line');
  if (fl) {
    var cs2 = getComputedStyle(fl);
    out.push('FINAL_LINE\th=' + rect(fl).height.toFixed(0) +
             '\tlh=' + cs2.lineHeight + '\tfs=' + cs2.fontSize);
  }
  out.push('DOC_H=' + document.documentElement.scrollHeight);
  var d = document.createElement('div');
  d.id = 'rhythm-out';
  d.textContent = 'RHYTHM#' + out.join('\n') + '#END';
  document.body.appendChild(d);
});
</script>
</body>"""

HEAD_CSS = '<style id="qj-probe">{}</style>\n</head>'


def run(url, width=1440, css_file=None):
    html = subprocess.run(
        ["curl", "-sL", "--max-time", "60",
         "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
         "-H", "Accept: text/html", "--compressed", url],
        capture_output=True, text=True).stdout
    if len(html) < 2000:
        sys.exit(f"抓取失败：{url} 只拿到 {len(html)} 字节")

    # 关键：待测 CSS 必须注入到 </body> 之前（= 页面自己内联 style 之后），
    # 否则同特异性下会被页面内联的 section{padding} 压住，测出来还是旧值。
    style_tag = ""
    if css_file:
        css = pathlib.Path(css_file).read_text(encoding="utf-8")
        css = re.sub(r"\s+", " ", css)
        style_tag = f'<style id="qj-probe">{css}</style>\n'

    tmp = pathlib.Path("/tmp/qj-rhythm-measure.html")
    tmp.write_text(html.replace("</body>", style_tag + INJECT, 1), encoding="utf-8")

    r = subprocess.run(
        [CH, "--headless=new", "--disable-gpu", "--no-sandbox",
         f"--window-size={width},1200", "--virtual-time-budget=8000",
         "--dump-dom", f"file://{tmp}"],
        capture_output=True, text=True, timeout=120)
    # 只取结果 div 的内容：脚本源码里也有 "RHYTHM#" 字面量，直接匹配会抓到源码
    m = re.search(r'id="rhythm-out"[^>]*>RHYTHM#(.*?)#END', r.stdout, re.S)
    if not m:
        sys.exit("测量失败：页面里没有 RHYTHM 输出（Chrome 可能没跑起来）")
    return m.group(1).strip().split("\n")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    url = sys.argv[1]
    width = 1440
    css = None
    if "--width" in sys.argv:
        width = int(sys.argv[sys.argv.index("--width") + 1])
    if "--css" in sys.argv:
        css = sys.argv[sys.argv.index("--css") + 1]

    print(f"测量 {url}   视口 {width}   预演CSS={css or '无'}")
    for line in run(url, width, css):
        parts = line.split("\t")
        print("  " + "  ".join(f"{p:>22s}" if i == 0 else f"{p:<22s}"
                               for i, p in enumerate(parts)))


if __name__ == "__main__":
    main()
