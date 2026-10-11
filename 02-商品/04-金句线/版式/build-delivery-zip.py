# -*- coding: utf-8 -*-
"""金句线 · 交付包打包：从样张目录取 32 张 PNG，按「序号-中文名」重打成对外 zip。
用法：python3 build-delivery-zip.py
源：../../05-承接站/样张/{slug}-phone-{iphone,android}.png
出：../交付包/第七境-五千年金句壁纸-全套32张.zip
"""
import zipfile, pathlib

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
SAMPLE = ROOT / '02-商品/05-承接站/样张'
OUT = ROOT / '02-商品/04-金句线/交付包/第七境-五千年金句壁纸-全套32张.zip'
# 线上直链用英文文件名（与藏品页 CTA 一致），打包时一并生成副本，避免手动复制
OUT_EN = ROOT / '02-商品/04-金句线/交付包/wallpaper-jinju-32-v2.zip'

# 16 朝历史序：slug -> (序号, 中文名)
ERAS = [
    ('sanhuang', '三皇五帝'), ('xia', '夏'), ('shang', '商'), ('zhou', '周'),
    ('qin', '秦'), ('han', '汉'), ('sanguo', '三国'), ('jin', '两晋南北朝'),
    ('sui', '隋'), ('tang', '唐'), ('wudai', '五代十国'), ('song', '宋'),
    ('yuan', '元'), ('ming', '明'), ('qing', '清'), ('juexing', '觉醒年代'),
]

USAGE = """第七境 · 五千年金句壁纸
十六朝 · 全套 32 张

【里面有什么】
iPhone/    16 张，1179 × 2556 —— 适配 iPhone 15 / 15 Pro 及多数全面屏机型
Android/   16 张，1080 × 2400 —— 适配多数安卓 2K 屏机型
每朝两句话，竖排右起。顶部为锁屏时间留白，字落在屏幕中段。

【怎么设成壁纸】
iPhone   长按图片 → 存储到照片 → 设置 → 墙纸 → 选取新墙纸
Android  长按图片 → 设为壁纸（若被自动裁切，选「原始比例」）

【关于版权】
· 壁纸可自由用于个人设备的桌面与锁屏，也欢迎转发给朋友。
· 古籍原文属公有领域；本套壁纸的价值在于选句、编排与版式设计。
· 字体遵循 SIL Open Font License 1.1 —— 衍生作品可随产品分发，字体文件本身不单独出售。
· 请勿将本套文件用于转售或商业再分发。

【第七境】
THE SEVENTH REALM ™ · 商标申请中
theseventhrealm.com
"""


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    missing = []
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for i, (slug, cn) in enumerate(ERAS, 1):
            for tag, folder in [('iphone', 'iPhone-1179x2556'), ('android', 'Android-1080x2400')]:
                src = SAMPLE / f'{slug}-phone-{tag}.png'
                if not src.exists():
                    missing.append(str(src))
                    continue
                z.write(src, f'{folder}/{i:02d}-{cn}.png')
        z.writestr('使用说明.txt', USAGE)
    if missing:
        print('缺少源图（未打包）：')
        for m in missing:
            print('  ', m)
        return 1
    import shutil
    shutil.copyfile(OUT, OUT_EN)   # 线上直链用英文名副本
    print('已打包', OUT)
    print('英文副本', OUT_EN.name)
    print('大小', round(OUT.stat().st_size / 1024 / 1024, 2), 'MB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
