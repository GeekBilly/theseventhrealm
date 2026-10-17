#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「视口 + 纵向偏移」截取指定区间，供改前改后对比。

两个坑，都试过才定下这个做法：
  1) `--window-size=1440,11500` 一次截全页：页面里 `.hero{min-height:54vh}` 等依赖 vh，
     视口高拉到 11500 会让 54vh 变成 6210px —— 布局与真实访客看到的不是同一个页面。
  2) `window.scrollTo(y)` + `--screenshot`：headless 截图固定从文档顶部开始，滚动无效。
所以：视口固定 900，用 `body{position:relative;top:-Ypx}` 把目标区间顶到首屏，
布局不动、vh 不变，截到的就是访客滚到那里的样子。
"""
import pathlib
import re
import subprocess
import sys

CH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def shot(html: pathlib.Path, y: int, out: pathlib.Path, vh=900, width=1440):
    s = html.read_text(encoding="utf-8")
    s = re.sub(r'<style id="qj-shift">.*?</style>', "", s, flags=re.S)
    shift = f'<style id="qj-shift">body{{position:relative;top:-{y}px}}</style>'
    tmp = html.with_suffix(".shift.html")
    tmp.write_text(s.replace("</head>", shift + "</head>", 1), encoding="utf-8")
    r = subprocess.run(
        [CH, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         f"--window-size={width},{vh}", "--virtual-time-budget=6000",
         f"--screenshot={out}", f"file://{tmp}"],
        capture_output=True, text=True, timeout=120)
    ok = out.exists() and out.stat().st_size > 20000
    print(f"  {out.name}  y={y}  {out.stat().st_size if out.exists() else 0} 字节  {'OK' if ok else 'FAIL'}")
    if not ok:
        print((r.stderr or "")[-400:])
    return ok


if __name__ == "__main__":
    y = int(sys.argv[1]) if len(sys.argv) > 1 else 9350
    for name in ("shot-base", "shot-new"):
        shot(pathlib.Path(f"/tmp/qjsp/{name}.html"), y,
             pathlib.Path(f"/tmp/qjsp/{name}-crop.png"))
