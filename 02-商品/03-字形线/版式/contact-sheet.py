# -*- coding: utf-8 -*-
"""A 线朝代总览 contact sheet（2026-10-05 正式化，2026-10-09 增 --phone 双画幅）。

用法：
    python3 contact-sheet.py                      # 十六朝横版 1920×1080
    python3 contact-sheet.py --cols 4 --tw 640
    python3 contact-sheet.py --phone              # 十六朝手机竖版 iOS 1179×2556（客户主形态）
    python3 contact-sheet.py --phone --variant android   # 安卓 1080×2400 总览
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
FIN = ROOT / '02-商品/03-字形线/成品-演变/01-正式成品'
OUT = ROOT / '02-商品/03-字形线/成品-演变/02-校样-20261005'
FONT = '/System/Library/Fonts/STHeiti Medium.ttc'
FONT_SONG = '/System/Library/Fonts/Supplemental/Songti.ttc'

# 排布沿用「十二朝总览」的既有顺序，只在其后追加新版（避免打乱用户已看过的版面）
ROWS = [
    [('sanhuang', '三皇五帝'), ('xia', '夏'), ('shang', '商'), ('zhou', '周')],
    [('qin', '秦'), ('han', '汉'), ('sanguo', '三国'), ('jin', '两晋南北朝')],
    [('wudai', '五代十国'), ('tang', '唐★'), ('song', '宋★'), ('ming', '明★')],
    [('sui', '隋★'), ('qing', '清★'), ('yuan', '元★'), ('juexing', '觉醒年代★')],
]
# ⭐ 手机竖版＝16 朝全出（2026-10-09 用户：手机版就是主交付物，不受底纹铁律约束）
ROWS_PHONE = [
    [('sanhuang', '三皇五帝'), ('xia', '夏'), ('shang', '商'), ('zhou', '周')],
    [('qin', '秦'), ('han', '汉'), ('sanguo', '三国'), ('jin', '两晋南北朝')],
    [('sui', '隋'), ('tang', '唐'), ('wudai', '五代十国'), ('song', '宋')],
    [('yuan', '元'), ('ming', '明'), ('qing', '清'), ('juexing', '觉醒年代')],
]
GAP, LABEL_H, TITLE_H, PAD = 16, 30, 104, 18

# 手机竖版画幅（与 gen-evolution-phone.py 的 VARIANTS 一致）
#   变体 → (盘上子目录, 后缀, 宽, 高)
PHONE_V = {'ios': ('iOS', '1179x2556', 1179, 2556),
           'android': ('Android', '1080x2400', 1080, 2400),
           'std': ('_旧版-1080x1920', '1080x1920', 1080, 1920)}


def main(cols, tw, phone=False, variant='ios'):
    """phone=True ⇒ 读 `01-正式成品/手机竖版/<变体目录>/{slug}-<W>x<H>.png`。"""
    sub, suf_w, PW, PH = PHONE_V[variant]
    th = round(tw * (PH / PW)) if phone else round(tw * (1080 / 1920))
    rows = ROWS_PHONE if phone else ROWS
    src = (FIN / '手机竖版' / sub) if phone else FIN
    suf = f'-{suf_w}.png' if phone else '-1920x1080.png'
    W = PAD * 2 + cols * tw + (cols - 1) * GAP
    H = TITLE_H + PAD * 2 + len(rows) * (th + LABEL_H) + (len(rows) - 1) * GAP
    sheet = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    f_title = ImageFont.truetype(FONT, 30)
    f_sub = ImageFont.truetype(FONT, 20)
    f_lab = ImageFont.truetype(FONT, 21)
    if phone:
        d.text((PAD, 16), f'A 线 · 字体演变 手机竖版 {suf_w}（{variant}）· 十六朝 · '
                          f'客户交付主形态（2026-10-09）',
               font=f_title, fill=(20, 20, 20))
        d.text((PAD, 58), '⭐ 客户包 = iOS 1179×2556 + Android 1080×2400 各 16 张（共 32 张）；无底纹；'
                          '版式唯一出处 模板-朝代-v9-竖版.html（kx=W/1080 与 ky=H/1920 双因子缩放）',
               font=f_sub, fill=(90, 90, 90))
        d.text((PAD, 82), '⭐ 手机版＝客户交付主形态；横版 48 张（三档）亦已于 2026-10-09 全部补齐（含元／觉醒年代）。',
               font=f_sub, fill=(40, 130, 60))
    else:
        d.text((PAD, 16), 'A 线 · 字体演变 十六朝（前三行＝九朝已上线 + 唐/宋/明；第四行＝隋/清/元/觉醒年代 '
                          '—— 2026-10-09 补齐全部 16 朝底纹）',
               font=f_title, fill=(20, 20, 20))
        d.text((PAD, 58), '底纹 16 朝全齐（2026-10-09 收口）：隋＝龙舸｜唐＝贡狮｜宋＝瑞鹤｜明＝麒麟｜'
                          '清＝甪端（《宋书·符瑞志》“晓四夷之语…奉书而至”）｜元＝六月飞雪｜觉醒年代＝铅字',
               font=f_sub, fill=(90, 90, 90))
        d.text((PAD, 82), '✅ 16 朝横版三档 48 张全部可上架。清原「风雷行龙」因龙朝向反了改用甪端（旧图留档）；'
                          '元·窦娥金句反祥瑞 ⇒ 取同篇「六月飞雪」。',
               font=f_sub, fill=(40, 130, 60))
    for r, row in enumerate(rows):
        y = TITLE_H + PAD + r * (th + LABEL_H + GAP)
        for c, (slug, label) in enumerate(row):
            x = PAD + c * (tw + GAP)
            d.text((x + 2, y), label, font=f_lab, fill=(20, 20, 20) if slug else (170, 170, 170))
            if slug:
                f = src / f'{slug}{suf}'
                if f.exists():
                    sheet.paste(Image.open(f).convert('RGB').resize((tw, th), Image.LANCZOS),
                                (x, y + LABEL_H))
                else:
                    d.rectangle([x, y + LABEL_H, x + tw, y + LABEL_H + th], outline=(220, 220, 220))
                    d.text((x + 12, y + LABEL_H + 12), f'缺 {f.name}', font=f_sub, fill=(200, 60, 60))
            else:
                d.rectangle([x, y + LABEL_H, x + tw, y + LABEL_H + th], outline=(226, 226, 226))
                d.text((x + tw // 2 - (62 if phone else 62), y + LABEL_H + th // 2 - 10), '待补底纹',
                       font=f_sub, fill=(180, 180, 180))
    p = OUT / (f'十六朝手机竖版-{variant}-总览-20261009.png' if phone
               else '十六朝总览-20261009.png')
    sheet.save(p)
    print(f'  ✓ {p}  {sheet.size[0]}x{sheet.size[1]}  {p.stat().st_size/1024:.0f}KB')


if __name__ == '__main__':
    a = sys.argv[1:]
    phone = '--phone' in a
    variant = a[a.index('--variant') + 1] if '--variant' in a else 'ios'
    if variant not in PHONE_V:
        raise SystemExit(f'未知 --variant {variant}（可选：{"/".join(PHONE_V)}）')
    cols = int(a[a.index('--cols') + 1]) if '--cols' in a else 4
    tw = int(a[a.index('--tw') + 1]) if '--tw' in a else (300 if phone else 640)
    main(cols, tw, phone, variant)
