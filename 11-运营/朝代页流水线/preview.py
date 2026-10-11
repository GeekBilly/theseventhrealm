#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 03-页面/朝代页/<slug>.html（发布用片段）包成可直接在浏览器里看的完整页面。

用途：发布前肉眼过一遍版式。不上传、不改线上。
用法：python3 preview.py   → 输出 03-页面/朝代页-preview/<slug>.html + index.html
"""
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = pathlib.Path(HERE).resolve().parents[1]   # HERE 是目录：parents[0]=11-运营, [1]=工作区根
CSS = ROOT / 'seventhrealm-child' / 'assets' / 'qijing.css'
SRC = ROOT / '03-页面' / '朝代页'
OUT = ROOT / '03-页面' / '朝代页-preview'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, HERE)
from eras import ERAS  # noqa: E402

OVERRIDE = """
/* 预览专用：站点用 JS 触发入场动画，静态预览里直接显示 */
.reveal{opacity:1!important;transform:none!important}
.hero{min-height:auto!important;padding:70px 24px 40px!important}
"""


def page(title, body):
    css = CSS.read_text(encoding='utf-8')
    return ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            "<title>%s</title>\n<style>%s\n%s</style>\n</head>\n<body>\n%s\n</body>\n</html>\n"
            % (title, css, OVERRIDE, body))


def main():
    links = []
    for e in ERAS:
        html = (SRC / f"{e['slug']}.html").read_text(encoding='utf-8')
        (OUT / f"{e['slug']}.html").write_text(
            page(e['seo'], html), encoding='utf-8')
        links.append((e['slug'], e['seo']))
        print("  ✓ %-9s %s" % (e['slug'], e['seo']))

    idx = ['<h1 style="font-size:22px;letter-spacing:4px;margin:40px 0 20px">'
           '朝代页样张预览（发布前）</h1>', '<p>']
    for slug, seo in links:
        idx.append('<a href="%s.html" style="display:inline-block;margin:6px 10px">%s</a>'
                   % (slug, seo))
    idx.append('</p>')
    (OUT / 'index.html').write_text(page('朝代页样张预览', '\n'.join(idx)), encoding='utf-8')
    print("\n共 %d 页 + index → %s" % (len(links), OUT))


if __name__ == '__main__':
    main()
