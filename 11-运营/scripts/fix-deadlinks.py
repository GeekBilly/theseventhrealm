#!/usr/bin/env python3
"""把「活跃文件」里指向已废弃目录的引用接回新位置（幂等，可反复跑）。

只做精确串替换，不碰历史叙述（申请单、备份、归档里的旧目录名保留原貌）。
配合 11-运营/scripts/path-links-check.py 使用：先体检，再修，再体检。

用法：
    python3 11-运营/scripts/fix-deadlinks.py           # 执行修正
    python3 11-运营/scripts/fix-deadlinks.py --dry     # 只看会改什么
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DRY = '--dry' in sys.argv

# (旧串, 新串) —— 只收「目标确实存在」的映射，改完必须能通过体检
RULES = [
    # commerce 目录已并入 02-商品/01-规划
    ('11-运营/commerce/build-catalog.py', '02-商品/05-承接站/build-catalog.py'),
    ('11-运营/commerce/catalog.csv', '02-商品/01-规划/catalog.csv'),
    ('11-运营/commerce/sources.csv', '02-商品/01-规划/sources.csv'),
    # wallpapers 已拆分：字体 → 02-素材/字体，归档物 → 06-归档，成品 → 05-承接站/样张
    ('wallpapers/OFL-MaShanZheng.txt', '02-商品/02-素材/字体/OFL-MaShanZheng.txt'),
    ('wallpapers/OFL-NotoSerifSC.txt', '02-商品/02-素材/字体/OFL-NotoSerifSC.txt'),
    ('wallpapers/字体体检-朝代主字.png', '02-商品/06-归档/字体体检-朝代主字.png'),
    ('wallpapers/字体对照-商字放大.png', '02-商品/06-归档/字体对照-商字放大.png'),
    ('wallpapers/font_audit.py', '02-商品/06-归档/font_audit.py'),
    # 金句线脚本迁到 04-金句线/版式 后，用法注释没跟着改
    ('02-商品/gen-wallpaper.py', '02-商品/04-金句线/版式/gen-wallpaper.py'),
    ('02-商品/shoot-wallpaper.py', '02-商品/04-金句线/版式/shoot-wallpaper.py'),
    # shop/ 已归入 03-页面/
    ('shop/live-5000-v14.html', '03-页面/live-5000-v14.html'),
    ('shop/pv-v16.html', '03-页面/pv-v16.html'),
    ('shop/nav16-', '03-页面/nav16-'),
    ('shop/dynasty/', '03-页面/朝代页/'),
]

# 只修活跃文件；历史申请单 / 备份 / 归档保留原貌
TARGETS = [
    '11-运营/朝代页流水线/nav16-check.py',
    '11-运营/朝代页流水线/nav16-shots.py',
    '02-商品/04-金句线/版式/gen-wallpaper.py',
    '02-商品/04-金句线/版式/shoot-wallpaper.py',
    '02-商品/05-承接站/build-catalog.py',
    '02-商品/05-承接站/index.html',
    '02-商品/01-规划/商品名录-v1.md',
    '11-运营/字体授权台账.md',
    '11-运营/风险管控/IP资产台账.md',
]


def main():
    total = 0
    for rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            print(f'  ⚠️  跳过（不存在）{rel}')
            continue
        text = p.read_text(encoding='utf-8')
        orig = text
        hits = []
        for old, new in RULES:
            if old in text:
                n = text.count(old)
                text = text.replace(old, new)
                hits.append(f'{old} → {new} ×{n}')
        if text != orig:
            total += sum(int(h.split('×')[1]) for h in hits)
            print(f'  ✎ {rel}')
            for h in hits:
                print(f'       {h}')
            if not DRY:
                p.write_text(text, encoding='utf-8')
    print(f'\n{"将修改" if DRY else "已修改"} {total} 处。')


if __name__ == '__main__':
    main()
