#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 网页设计 token（水墨国风）

被两个生成器共用，解决「看板与门户页风格不一致」的问题：
  - 11-运营/scripts/build-workbench.py       门户（多 tab 单页）
  - 11-运营/scripts/build-morning-board.py   晨检看板（独立页 + 内嵌片段）

用法差异（关键）：
  - 门户页把 TOKENS 放在 :root 上，全局生效。
  - 看板的 CSS **必须**做作用域隔离（它既要独立成页，也要内嵌进门户 tab），
    所以变量定义在 `.mb{}` 内、规则一律以 `.mb` 为前缀。
    CSS 变量定义在 `.mb` 上会覆盖宿主 :root 的同名变量 —— 两边取值相同，故视觉一致。
"""
import html

# 字体：毛笔（标题/数字）＋ 宋体（正文）
FONTS = (
    "@import url('https://fonts.loli.net/css2?family=Ma+Shan+Zheng"
    "&family=Noto+Serif+SC:wght@400;600&display=swap');"
)

# 色板与字体变量（::SCOPE:: 会被替换成 ':root' 或 '.mb'）
TOKENS = """
::SCOPE::{
  --white:#ffffff; --wash:#f7f6f3; --wash2:#fbfaf8;
  --ink:#1a1a18; --ink2:#6b675f; --ink3:#9a958c; --line:rgba(26,26,24,.10);
  --cinnabar:#b03826; --cinnabar-soft:rgba(176,56,38,.10);
  --ok:#4a7c59; --warn:#a86a1c; --na:#a5a19a;
  --f-brush:'Ma Shan Zheng','Xingkai SC','STXingkai','KaiTi','STKaiti',serif;
  --f-body:'Noto Serif SC','Songti SC','STSong','KaiTi',serif;
}
"""

# 门户页（:root）与看板（.mb）各自的底色/字体承接
PAGE_BODY = ("body{background:var(--white);color:var(--ink);"
             "font-family:var(--f-body);font-size:17px;line-height:1.9;"
             "-webkit-font-smoothing:antialiased}")


def tokens(scope=":root"):
    return TOKENS.replace("::SCOPE::", scope)


def esc(s):
    return html.escape(str(s))
