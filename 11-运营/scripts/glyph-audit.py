#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""glyph-audit.py —— 汉字字形结构审计（罕用字「AI 写错」的验收工具）

背景：AI 生图对罕用字（如「赜」的部件「臣」）的结构认知会退化，
      把「臣」画成「框＋中」；靠肉眼在小图上核验会漏。
      本工具把字形的墨迹转成 ASCII 结构图，逐行看骨架，用事实判断对错。

三种用法：
  1) map     —— 输出某图的 ASCII 结构图（默认取整幅；--char-height 可指定取第几个字）
  2) split   —— 把左右结构字按墨量谷底切成左/右部件，分别出图
  3) overlay —— 把候选字形与基准字形（字库）归一化后叠合，差异染色

示例：
  # 看一张字稿里「赜」的骨架（1=取第二个字，即下半）
  python3 glyph-audit.py map 字稿.png --char-height 2 -o 结构图.txt
  # 切开 赜 的左右部件
  python3 glyph-audit.py split 字稿.png --char-height 2 -o 部件
  # 与宋体「臣」叠合，红色=基准有而没有、蓝色=多出来
  python3 glyph-audit.py overlay 字稿.png --ref 臣 --char-height 2 --left 0.48 -o 叠合.png
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SONG = "/System/Library/Fonts/Supplemental/Songti.ttc"
DEFAULT_OUT = os.path.dirname(os.path.abspath(__file__)) + "/../reports"

BLOCKS = " .:-=+*#%@"


def load_ink(path, thr=150):
    im = Image.open(path).convert("L")
    a = np.asarray(im)
    return a < thr


def tight(mask):
    ys, xs = np.where(mask)
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def font_mask(ch, font_path=SONG, size=760, index=0):
    im = Image.new("L", (size * 2, size * 2), 255)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(font_path, size, index=index)
    bb = d.textbbox((0, 0), ch, font=f)
    d.text(((size * 2 - (bb[2] - bb[0])) // 2 - bb[0],
            (size * 2 - (bb[3] - bb[1])) // 2 - bb[1]), ch, font=f, fill=0)
    return np.asarray(im) < 128


def char_region(mask, which):
    """整幅字稿里按下刀走：1=第一个字，2=第二个字（默认下半）。"""
    if which <= 1:
        return tight(mask)
    ys, _ = np.where(mask)
    y0, y1 = ys.min(), ys.max()
    # 找最大空白带作为分界
    rows = mask.sum(1)
    blanks = [y for y in range(y0, y1) if rows[y] == 0]
    if not blanks:
        cut = y0 + int((y1 - y0) * 0.5)
    else:
        runs, s = [], blanks[0]
        for i in range(1, len(blanks)):
            if blanks[i] != blanks[i - 1] + 1:
                runs.append((s, blanks[i - 1]))
                s = blanks[i]
        runs.append((s, blanks[-1]))
        runs.sort(key=lambda r: r[1] - r[0], reverse=True)
        cut = (runs[0][0] + runs[0][1]) // 2
    return tight(mask[cut:, :])


def ascii_map(mask, cols=44, title=""):
    m = tight(mask)
    rows = max(2, int(round(cols * m.shape[0] / m.shape[1])))
    g = Image.fromarray(np.where(m, 0, 255).astype(np.uint8)).resize((cols, rows), Image.BOX)
    arr = np.asarray(g)
    lines = []
    if title:
        lines.append(f"### {title}  墨迹 {m.shape[1]}×{m.shape[0]}  "
                     f"高宽比 {m.shape[0] / m.shape[1]:.2f}")
    for r in arr:
        lines.append("".join(BLOCKS[min(9, int((255 - v) / 25.6))] for v in r))
    return "\n".join(lines)


def split_lr(mask, lo=0.28, hi=0.62):
    """按列墨量谷底切左右部件（左右结构字）。"""
    m = tight(mask)
    cs = m.sum(0)
    a, b = int(m.shape[1] * lo), int(m.shape[1] * hi)
    k = a + int(np.argmin(cs[a:b]))
    return m[:, :k + 1], m[:, k:], k / m.shape[1]


def overlay(ref_mask, test_mask, height=520):
    a = Image.fromarray(np.where(tight(ref_mask), 0, 255).astype(np.uint8))
    b = Image.fromarray(np.where(tight(test_mask), 0, 255).astype(np.uint8))
    ra, rb = height / a.height, height / b.height
    a = a.resize((max(1, int(a.width * ra)), height), Image.LANCZOS)
    b = b.resize((max(1, int(b.width * rb)), height), Image.LANCZOS)
    W = max(a.width, b.width)
    A = np.zeros((height, W), bool)
    B = np.zeros((height, W), bool)
    A[:, (W - a.width) // 2:(W - a.width) // 2 + a.width] = np.asarray(a) < 150
    B[:, (W - b.width) // 2:(W - b.width) // 2 + b.width] = np.asarray(b) < 150
    out = np.full((height, W, 3), 255, np.uint8)
    out[A & B] = (40, 40, 40)       # 重合
    out[A & ~B] = (205, 60, 50)     # 基准有、候选没有
    out[B & ~A] = (45, 110, 190)    # 候选多出来
    return Image.fromarray(out)


def main():
    ap = argparse.ArgumentParser(description="汉字字形结构审计")
    ap.add_argument("cmd", choices=["map", "split", "overlay"])
    ap.add_argument("src", help="待查图片路径")
    ap.add_argument("--char-height", type=int, default=1,
                    help="取第几个字（1=整幅/第一个，2=第二个；默认 1）")
    ap.add_argument("--ref", default="臣", help="overlay 用基准字（默认「臣」）")
    ap.add_argument("--left", type=float, default=0.5,
                    help="overlay/split 时左部件截取比例")
    ap.add_argument("--cols", type=int, default=44, help="ASCII 列数")
    ap.add_argument("-o", "--out", default=None, help="输出文件（不含扩展名的前缀亦可）")
    args = ap.parse_args()

    mask = load_ink(args.src)
    region = char_region(mask, args.char_height)

    if args.cmd == "map":
        txt = ascii_map(region, args.cols, os.path.basename(args.src))
        print(txt)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(txt + "\n")
            print(f"\n→ 已写入 {args.out}", file=sys.stderr)

    elif args.cmd == "split":
        L, R, k = split_lr(region)
        print(f"分界列 {k:.0%}；左 {L.shape[1]}×{L.shape[0]}，右 {R.shape[1]}×{R.shape[0]}")
        prefix = args.out or os.path.splitext(args.src)[0] + "-部件"
        for tag, part in (("左", L), ("右", R)):
            p = tight(part)
            Image.fromarray(np.where(p, 0, 255).astype(np.uint8)).save(f"{prefix}-{tag}.png")
            print(f"→ {prefix}-{tag}.png")

    else:
        w = int(region.shape[0] * args.left)
        cand = tight(region[:, :w])
        img = overlay(font_mask(args.ref), cand)
        out = args.out or os.path.splitext(args.src)[0] + f"-叠合-{args.ref}.png"
        img.save(out)
        print(f"→ {out}（黑=重合，红=基准有候选无，蓝=候选多出）")


if __name__ == "__main__":
    main()
