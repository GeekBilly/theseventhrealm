#!/usr/bin/env python3
"""统计朝代稿字数并做字符体检。

用法：
    python3 count.py            # 统计全部 <slug>.md
    python3 count.py zhou       # 只统计指定稿件

输出：每份稿件的「中文字符数（全文）」「中文字符数（正文，即引用出处之前）」
     以及是否达标（默认目标见 TARGETS）。同时检查是否混入非中日韩字符、繁体字。

把这个脚本的单位"中文字符"当作全书字数的统计口径：
  —— 标点、空白、拉丁字母不计入。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HAN = re.compile(r"[\u4e00-\u9fff]")
# 常见混入：西里尔 / 拉丁扩展 / 越南语附加符号 / 日文假名 / 韩文
FOREIGN = re.compile(r"[\u0400-\u04FF\u0100-\u017F\u1E00-\u1EFF\u3040-\u30FF\uAC00-\uD7AF]+")
# 高频繁体误入（够用即可，不必穷举）
TRAD = re.compile(r"[給祇裡麼會員學國來時的後邊點實現]")

ALLOWED = {"11-运营", "eras", "pages", "dict", "build", "publish", "py", "the", "ID"}

TARGETS = {
    "sanhuang": 4000, "xia": 4000, "shang": 5000, "zhou": 6000,
    "qin": 5000, "han": 6000, "sanguo": 5000, "jin": 5000,
    "sui": 4000, "tang": 6000, "wudai": 4000, "song": 6000,
    "yuan": 5000, "ming": 5000, "qing": 6000, "juexing": 5000,
}


def report(path):
    slug = os.path.splitext(os.path.basename(path))[0]
    text = open(path, encoding="utf-8-sig").read()
    body = text.split("## 引用出处")[0]
    total = len(HAN.findall(text))
    main = len(HAN.findall(body))
    target = TARGETS.get(slug, 0)
    flag = "达标" if main >= target else "缺 %d" % (target - main)
    print("%-10s 全文 %6d  正文 %6d / 目标 %5d  %s" % (slug, total, main, target, flag))

    bad = FOREIGN.findall(text)
    if bad:
        print("    ⚠ 混入非目标语种字符：%s" % " ".join(sorted(set(bad))))
    # 正文里不该出现的拉丁词（写作时的串语种残留，实测已多次发生）
    words = [w for w in re.findall(r"[A-Za-z]{3,}", text) if w not in ALLOWED]
    if words:
        # 只报出现在「引用出处」之前的，附录里允许写文件名
        body_words = [w for w in re.findall(r"[A-Za-z]{3,}", text.split("## 附")[0])
                      if w not in ALLOWED]
        if body_words:
            print("    ⚠ 正文疑似残留外来词：%s" % " ".join(sorted(set(body_words))))
    return total, main


def main():
    args = sys.argv[1:]
    if args:
        files = [os.path.join(HERE, a + ".md") for a in args]
    else:
        files = sorted(__import__("glob").glob(os.path.join(HERE, "*.md")))
        files = [f for f in files if TARGETS.get(os.path.splitext(os.path.basename(f))[0])]
    if not files:
        print("未找到稿件。用法：python3 count.py [slug ...]")
        return
    sum_main = 0
    for f in files:
        if not os.path.exists(f):
            print("不存在：" + f)
            continue
        _, m = report(f)
        sum_main += m
    print("-" * 52)
    print("正文合计：%d 字（全书目标 80,000）" % sum_main)


if __name__ == "__main__":
    main()
