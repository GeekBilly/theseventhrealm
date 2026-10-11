#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""姓氏线 v2A · 逐格光学归一化 —— 测量 / 求解 / 复核

原理（不改版面，只调字号与位移）：
  .cell .ch 的 height 被钉死在 232px，四格行盒顶边恒为 y=352。
  于是在字号 s 下，某格墨迹底 = 352 + c·(s/232)，其中 c = 232px 时的「行盒顶→墨迹底」距离。
  据此可精确解出：
    字号 s = 232 · T / H          （T = 目标墨迹高度，H = 232px 时实测墨迹高度）
    位移 dy = Y* − (352 + c·s/232)（Y* = 统一基线，即四格墨迹底对齐到的那条线）
  只用 PIL/PNG 量像素，不做任何横向拉伸。

用法：
  python3 measure-v2a.py --emit _build-v2a/norm.json      # 测量轮：解出参数
  python3 measure-v2a.py --check _build-v2a/norm.json     # 复核轮：量成品是否真的对齐
"""
import argparse
import importlib.util
import json
import pathlib
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).parent
ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/06-姓氏线/成品-桌面-v2A'

TARGET_H = 200        # 目标墨迹高度（统一像素值）
BASE_Y = 588          # 四格墨迹底对齐线（标签首行墨迹顶在 y=614，留 26px 净空）
CH_TOP = 352          # .quat top
REF_SIZE = 232        # 参考字号


def _load_verify():
    spec = importlib.util.spec_from_file_location('v2v', HERE / 'verify-v2a-fonts.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


V = _load_verify()


def measure(png):
    """返回 {书体: (墨迹高, 墨迹底, 墨迹顶)}"""
    im = Image.open(png).convert('L')
    a = np.asarray(im)
    boxes = V.cells_from_png(im)
    out = {}
    for k, b in zip(V.ORDER4, boxes):
        win = a[:, b[0]:b[2]] < 128
        rows = np.nonzero(win.sum(axis=1))[0]
        # 只在四体色带内取墨：上不过 y=300（否则吃到左上「姓氏源流」小字），
        # 下不过 y=600（否则吃到书体标注）
        rows = rows[(rows >= 300) & (rows < 600)]
        if not len(rows):
            out[k] = None
            continue
        out[k] = (int(rows.max() - rows.min() + 1), int(rows.max()), int(rows.min()))
    return out


def collect(pngs):
    data = {}
    for p in pngs:
        w = p.stem.split('-')[1]
        data[w] = measure(p)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--emit', type=pathlib.Path)
    ap.add_argument('--check', type=pathlib.Path)
    ap.add_argument('--target', type=float, default=TARGET_H)
    ap.add_argument('--base', type=float, default=BASE_Y)
    ap.add_argument('--dir', type=pathlib.Path, default=OUT, help='待测 PNG 目录')
    a = ap.parse_args()

    pngs = [p for p in sorted(a.dir.glob('surname-*.png')) if '-4k' not in p.name]
    if not pngs:
        sys.exit('没有 1x 成品可测')
    data = collect(pngs)

    if a.emit:
        norm, rows = {}, []
        for w, cells in data.items():
            norm[w] = {}
            for k, v in cells.items():
                if v is None:
                    continue
                h, bot, _top = v
                c = bot - CH_TOP
                s = REF_SIZE * a.target / h
                s = max(150, min(400, s))
                dy = a.base - (CH_TOP + c * s / REF_SIZE)
                norm[w][k] = {'size': int(round(s)), 'dy': int(round(dy))}
                rows.append((w, k, h, bot, s, dy))
        a.emit.write_text(json.dumps(norm, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'测量 {len(norm)} 个姓 · 目标墨迹高 {a.target:.0f}px · 基线 y={a.base:.0f}')
        print(f"{'序':<5}{'体':<7}{'原高':>5}{'原底':>6}{'新字号':>8}{'位移':>7}")
        for w, k, h, bot, s, dy in rows:
            print(f'{w:<5}{k:<7}{h:>5}{bot:>6}{s:>8.0f}{dy:>7.0f}')
        print(f'\n→ {a.emit}')

    if a.check:
        norm = json.loads(a.check.read_text(encoding='utf-8'))
        print(f"{'序':<5}{'体':<7}{'字号':>5}{'位移':>6}{'墨高':>6}{'墨底':>6}  判定")
        hs, bots, offs = [], [], []
        for w, cells in data.items():
            for k in V.ORDER4:
                v = cells.get(k)
                if v is None:
                    print(f'{w:<5}{k:<7}  ——  未测到墨迹')
                    continue
                h, bot, _top = v
                n = (norm.get(w) or {}).get(k, {})
                hs.append(h)
                bots.append(bot)
                offs.append(abs(bot - a.base))
                ok = '✓' if abs(h - a.target) <= 5 and abs(bot - a.base) <= 5 else \
                     ('~' if abs(h - a.target) <= 10 and abs(bot - a.base) <= 10 else '✗')
                print(f"{w:<5}{k:<7}{n.get('size','-'):>5}{n.get('dy','-'):>6}{h:>6}{bot:>6}  {ok}")
        print(f'\n墨迹高：min={min(hs)} max={max(hs)} 极差={max(hs)-min(hs)}  '
              f'|墨底−{a.base:.0f}|：max={max(offs)} 均值={sum(offs)/len(offs):.1f}')


if __name__ == '__main__':
    main()
