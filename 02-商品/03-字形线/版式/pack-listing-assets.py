# -*- coding: utf-8 -*-
"""A 线壁纸上架素材打包（2026-10-05 正式化，口径对齐既有 唐/宋/明 那批）。

产出四样（全部本地 0 积分）：
  预览/<slug>-preview.jpg      1200×675  **带斜向平铺水印 + 右下「预览图·非交付文件」红标**
  预览/<slug>-site.jpg          860×484  **同上（按比例缩的水印）**
  藏品页配图-v3/collection-a-<slug>-v3.jpg  1400×788  **无水印**（藏品页内嵌用）
  wallpaper-<slug>-v9.zip       三档原图打包（1920×1080 / 3840×2160 / 3840×2496）

🔴 2026-10-09 用户口径：**客户下载只拿手机竖版，不拿横版** ⇒ 客户包：
  wallpaper-<slug>-phone-v9.zip      单朝 = **iOS + Android 各 1 张**（共 2 张）
  wallpaper-A线-手机竖版-16朝-v9.zip  16 朝 × 2 平台 = **32 张**（一次下载拿全部）
  ⚠️ 旧的 `wallpaper-<slug>-v9.zip`（横版三档）**保留但不再对客户发放**
     （要不要从 /collection/ 下线属「改线上内容」⇒ 需出申请单，不擅自动）。

🔴 2026-10-09 晚（用户：「zip 更新一下，32 张，iOS 和 Android 各 16 张，新版的」）：
  画幅从单一 1080×1920 改成**按机型原生比例出两套**：
    iOS      1179×2556   iPhone 15/16/17 Pro（19.5:9）
    Android  1080×2400   当代安卓主流（20:9）
  ⇒ 旧的那 16 张 `手机竖版/<slug>-1080x1920.png` **不进任何客户包**（保留在盘上仅供对照）。

水印口径（从既有 tang-preview.jpg 反推）：
  旋转 ≈ −30°，网格 ≈ 330×300（1200 宽基准），两种文本交替：
  「第七境」+「theseventhrealm.com」；灰阶 ≈ (128,128,128) alpha≈46。

用法：
  python3 pack-listing-assets.py sui qing              # 横版预览图 / 藏品配图 / 三档 zip（内部用）
  python3 pack-listing-assets.py sui --no-watermark    # 只出无水印版
  python3 pack-listing-assets.py --phone               # 16 朝单朝客户包（每包 iOS+Android 共 2 张）
  python3 pack-listing-assets.py --phone yuan juexing  # 指定朝
  python3 pack-listing-assets.py --bundle              # 16 朝合集（iOS 16 + Android 16 = 32 张）
"""
import pathlib
import sys
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
FIN = ROOT / '02-商品/03-字形线/成品-演变/01-正式成品'
OUT = ROOT / '02-商品/09-上架素材'
FONT_HEI = '/System/Library/Fonts/STHeiti Medium.ttc'

SIZES = {'preview': (1200, 675), 'site': (860, 484), 'collection': (1400, 788)}
BASE_W = 1200.0                      # 水印参数以 1200 宽为基准，其他尺寸等比缩放


def watermark_layer(size, angle=-30, gapx=330, gapy=300, alpha=46):
    """生成与画面同尺寸的水印层（RGBA）。"""
    w, h = size
    k = w / BASE_W
    f_big = ImageFont.truetype(FONT_HEI, max(10, int(62 * k)))
    f_sml = ImageFont.truetype(FONT_HEI, max(8, int(42 * k)))
    gx, gy = gapx * k, gapy * k
    bw, bh = int(w * 2.2), int(h * 2.2)          # 大画布，旋转后再裁
    lay = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    gray = (128, 128, 128, alpha)
    row = 0
    y = 0.0
    while y < bh:
        x = (0.0, gx * 0.5)[row % 2]
        col = 0
        while x < bw:
            txt, f = ('第七境', f_big) if (row + col) % 2 == 0 else ('theseventhrealm.com', f_sml)
            d.text((x, y), txt, font=f, fill=gray)
            x += gx
            col += 1
        y += gy
        row += 1
    lay = lay.rotate(angle, resample=Image.BICUBIC, expand=False)
    ox, oy = (bw - w) // 2, (bh - h) // 2
    return lay.crop((ox, oy, ox + w, oy + h))


def stamp_badge(img, k=1.0):
    """右下角「预览图 · 非交付文件」红标"""
    d = ImageDraw.Draw(img, 'RGBA')
    fs = max(11, int(27 * k))
    f = ImageFont.truetype(FONT_HEI, fs)
    txt = '预览图 · 非交付文件'
    tw = d.textlength(txt, font=f)
    pad_x, pad_y = int(14 * k), int(8 * k)
    bw, bh = int(tw + pad_x * 2), int(fs + pad_y * 2)
    m = int(26 * k)
    x1, y1 = img.width - m, img.height - m
    x0, y0 = x1 - bw, y1 - bh
    d.rectangle([x0, y0, x1, y1], fill=(255, 255, 255, 216), outline=(198, 40, 40, 235), width=max(1, int(k)))
    d.text((x0 + pad_x, y0 + pad_y - int(2 * k)), txt, font=f, fill=(190, 28, 28, 255))
    return img


def make(slug, watermark=True):
    src = FIN / f'{slug}-1920x1080.png'
    if not src.exists():
        print(f'  ✗ 缺成品 {src.name}')
        return
    base = Image.open(src).convert('RGB')
    res = []
    # 预览图（带水印）
    if watermark:
        for kind, size in (('preview', SIZES['preview']), ('site', SIZES['site'])):
            img = base.resize(size, Image.LANCZOS)
            wl = watermark_layer(size, alpha=46)
            img = Image.alpha_composite(img.convert('RGBA'), wl).convert('RGB')
            img = stamp_badge(img, k=size[0] / BASE_W)
            p = OUT / '预览' / f'{slug}-{kind}.jpg'
            p.parent.mkdir(parents=True, exist_ok=True)
            img.save(p, 'JPEG', quality=88, optimize=True)
            res.append(p)
    # 藏品页配图（无水印）
    p = OUT / '藏品页配图-v3' / f'collection-a-{slug}-v3.jpg'
    p.parent.mkdir(parents=True, exist_ok=True)
    base.resize(SIZES['collection'], Image.LANCZOS).save(p, 'JPEG', quality=90, optimize=True)
    res.append(p)
    # zip（三档原图）
    zp = OUT / f'wallpaper-{slug}-v9.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for wh in ('1920x1080', '3840x2160', '3840x2496'):
            f = FIN / f'{slug}-{wh}.png'
            if f.exists():
                z.write(f, f.name)
    res.append(zp)
    for p in res:
        print(f'  ✓ {p.relative_to(ROOT)}  {p.stat().st_size/1024:.0f}KB')


# ── 客户交付包：iOS + Android 双画幅手机竖版（2026-10-09 用户口径）──────
PHONE = FIN / '手机竖版'
# 两个平台（zip 内目录名, 盘上子目录名, 分辨率后缀）
PLATFORMS = [('iOS', 'iOS', '1179x2556'), ('Android', 'Android', '1080x2400')]
# 16 朝顺序（与 gen-evolution.py 的 ERAS 顺序一致：商→觉醒年代）
ORDER = ['shang', 'zhou', 'sanhuang', 'xia', 'qin', 'han', 'sanguo', 'jin',
         'sui', 'tang', 'wudai', 'song', 'yuan', 'ming', 'qing', 'juexing']

# ── 客户交付包专用命名（对齐金句线既有交付包 `wallpaper-jinju-32-v2.zip` 的习惯）──
#   ① 目录名自解释：iPhone-1179x2556 / Android-1080x2400（客户一眼认出自己的机型）
#   ② 文件名用**中文朝代名**（不是英文 slug）
#   ③ 按**历史时序**编号（三皇五帝 01 → 觉醒年代 16），不是 ERAS 的商周打头顺序
#   ④ 附 `使用说明.txt`
DELIVERY_ORDER = [('sanhuang', '三皇五帝'), ('xia', '夏'), ('shang', '商'), ('zhou', '周'),
                  ('qin', '秦'), ('han', '汉'), ('sanguo', '三国'), ('jin', '两晋南北朝'),
                  ('sui', '隋'), ('tang', '唐'), ('wudai', '五代十国'), ('song', '宋'),
                  ('yuan', '元'), ('ming', '明'), ('qing', '清'), ('juexing', '觉醒年代')]
DELIVERY_DIR = {'iOS': 'iPhone-1179x2556', 'Android': 'Android-1080x2400'}
README_TXT = '''第七境 · 五千年字形演变壁纸
十六朝 · 全套 32 张

【里面有什么】
iPhone-1179x2556/   16 张，1179 × 2556 —— 适配 iPhone 15 / 16 / 17 Pro 及多数全面屏机型
Android-1080x2400/  16 张，1080 × 2400 —— 适配多数安卓 20:9 机型
每朝取一个字：自上而下为该字的碑刻宋体与毛笔字，商、周两朝另附甲骨文 / 金文原字。
右上角竖排的是这一朝的典籍原句。顶部为锁屏时间留白，字落在屏幕中段。

【怎么设成壁纸】
iPhone   长按图片 → 存储到照片 → 设置 → 墙纸 → 选取新墙纸
Android  长按图片 → 设为壁纸（若被自动裁切，选「原始比例」）

【关于版权】
· 壁纸可自由用于个人设备的桌面与锁屏，也欢迎转发给朋友。
· 古籍原文与古文字字形属公有领域；本套壁纸的价值在于选字、编排与版式设计。
· 字体遵循 SIL Open Font License 1.1 —— 衍生作品可随产品分发，字体文件本身不单独出售。
· 请勿将本套文件用于转售或商业再分发。

【第七境】
THE SEVENTH REALM ™ · 商标申请中
theseventhrealm.com
'''


def phone_files(slug):
    """该朝在两个平台上各一张图（盘上路径 + zip 内名一份，带存在性检查）。"""
    got = []
    for zdir, sub, wh in PLATFORMS:
        p = PHONE / sub / f'{slug}-{wh}.png'
        if not p.exists():
            print(f'  ✗ 缺 {sub}/{p.name}')
            continue
        got.append((p, f'{zdir}/{slug}-{wh}.png', f'{zdir}/{wh}'))
    return got


def make_phone(slug):
    """单朝客户包：iOS + Android 各一张（共 2 张），一张多的没有。"""
    files = phone_files(slug)
    if not files:
        return None
    zp = OUT / f'wallpaper-{slug}-phone-v9.zip'
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for src, arc, _ in files:
            z.write(src, arc)
    tag = ' + '.join(t for _, _, t in files)
    print(f'  ✓ {zp.relative_to(ROOT)}  {zp.stat().st_size/1024:.0f}KB  （{tag}）')
    return zp


def make_bundle(slugs=None, name='wallpaper-A线-手机竖版-16朝-v9.zip'):
    """合集：16 朝 × 2 平台 = 32 张（iOS/ 与 Android/ 目录分开，内有朝代序号）。"""
    slugs = slugs or ORDER
    zp = OUT / name
    n = 0
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for i, s in enumerate(slugs, 1):
            for src, wh in ((PHONE / sub / f'{s}-{w}.png', w) for _, sub, w in PLATFORMS):
                if not src.exists():
                    print(f'  ✗ 缺 {src.name}')
                    continue
                zdir = next(zd for zd, sub, w in PLATFORMS if sub == src.parent.name)
                # 序号前缀 ⇒ 解压后两个目录内都按朝代序排列
                z.write(src, f'{zdir}/{i:02d}-{s}-{wh}.png')
                n += 1
    print(f'  ✓ {zp.relative_to(ROOT)}  {zp.stat().st_size/1024:.0f}KB  （{n} 张：iOS+Android 双画幅）')
    return zp


def make_delivery(name='wallpaper-dynasty-32-20261009.zip'):
    """**客户交付包**：命名对齐金句线旧包（中文朝代名 + 自解释目录 + 使用说明）。

    ⚠️ 与 `--bundle` 的区别：bundle 是内部件（英文 slug 命名、按 ERAS 序）；
       本函数产的是**真正发给客户**的那一个 zip。
    """
    zp = OUT / name
    n = 0
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for i, (s, cn) in enumerate(DELIVERY_ORDER, 1):
            for zdir, sub in (('iOS', 'iOS'), ('Android', 'Android')):
                wh = DELIVERY_DIR[zdir].split('-', 1)[1]
                src = PHONE / sub / f'{s}-{wh}.png'
                if not src.exists():
                    print(f'  ✗ 缺 {src.name}')
                    continue
                z.write(src, f'{DELIVERY_DIR[zdir]}/{i:02d}-{cn}.png')
                n += 1
        z.writestr('使用说明.txt', README_TXT)
    print(f'  ✓ {zp.relative_to(ROOT)}  {zp.stat().st_size/1024:.0f}KB  '
          f'（{n} 张 + 使用说明.txt）')
    return zp


if __name__ == '__main__':
    argv = sys.argv[1:]
    if '--phone' in argv:
        want = [a for a in argv if not a.startswith('-')] or ORDER
        print(f'客户包（只含手机竖版）· {len(want)} 朝：')
        for s in want:
            print(f'[{s}]')
            make_phone(s)
    elif '--bundle' in argv:
        want = [a for a in argv if not a.startswith('-')] or None
        print('16 朝手机竖版合集：')
        make_bundle(want)
    elif '--delivery' in argv:
        print('客户交付包（中文朝代名 + 使用说明）：')
        make_delivery()
    else:
        args = [a for a in argv if not a.startswith('-')]
        wm = '--no-watermark' not in argv
        for s in args or ['sui', 'qing']:
            print(f'[{s}]')
            make(s, wm)
