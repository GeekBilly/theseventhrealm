#!/usr/bin/env python3
"""生成 `/collection/` 藏品页：压缩并上传样张到媒体库，产出可直接发布的 HTML。

用法：
    python3 11-运营/scripts/build-collection.py            # 上传图片 + 生成 03-页面/collection.html
    python3 11-运营/scripts/build-collection.py --no-upload  # 只重建 HTML（沿用已上传的图片 URL）

幂等：图片按 title 查询，已存在则复用不重复上传；URL 记录在
`11-运营/data/collection-media.json`，重跑时直接读取。
"""

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY313 = '/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3'
VENVPY = '/Users/billyhou/.workbuddy/binaries/python/envs/default/bin/python'
SITE = 'https://theseventhrealm.com'
CACHE = ROOT / '11-运营/data/collection-media.json'
OUT = ROOT / '03-页面/collection.html'

# (媒体库 title, 源图, 页面里显示的说明, 上传宽度)
# ⚠️ 宽度是「防复制」的一部分，别乱调：展示图必须显著小于交付件。
#    桌面件交付到 4K(3840)，展示 1400 → 只覆盖 37%，安全。
#    手机件交付 1179×2556，展示必须 ≤640 → 若调到 1400 就等于白送（见 REQ-2026-09-30-04）。
IMAGES = [
    ('collection-shang', '02-商品/05-承接站/样张/shang-v9-std.png', '商 · 玄鸟底纹', 1400),
    ('collection-zhou', '02-商品/05-承接站/样张/zhou-v9-std.png', '周 · 凤凰底纹', 1400),
    ('collection-jinju-free', '02-商品/05-承接站/样张/shang-phone-iphone.png', '商 · 手机竖版（预览）', 640),
]


def auth():
    """从 11-运营/wp-auth.sh 拿到 WP_USER / WP_APP_PASS（凭据不落盘）。"""
    env = subprocess.run(['bash', '-c', f'. "{ROOT}/11-运营/wp-auth.sh" >/dev/null 2>&1; '
                          'echo "$WP_USER"; echo "$WP_APP_PASS"'],
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()
    return env[0], env[1]


def shrink(src, dst, width=1400):
    """缩到 1400 宽存 JPEG，控制页面体积。"""
    code = (
        'import sys\n'
        'from PIL import Image\n'
        'im = Image.open(sys.argv[1]).convert("RGB")\n'
        'w, h = im.size\n'
        'im = im.resize((int(sys.argv[3]), round(h * int(sys.argv[3]) / w)), Image.LANCZOS)\n'
        'im.save(sys.argv[2], "JPEG", quality=88, optimize=True)\n'
    )
    subprocess.run([VENVPY, '-c', code, str(src), str(dst), str(width)], check=True)
    return dst


def upload(title, path, user, pwd):
    """上传图片；已存在则复用。返回 (url, id)。"""
    q = subprocess.run(
        ['curl', '-s', '-u', f'{user}:{pwd}',
         f'{SITE}/wp-json/wp/v2/media?search={title}&per_page=1'],
        capture_output=True, text=True).stdout
    try:
        got = json.loads(q)
        if isinstance(got, list) and got and got[0].get('title', {}).get('rendered') == title:
            print(f'  ↺ {title} 已存在 id={got[0]["id"]}，复用')
            return got[0]['source_url'], got[0]['id']
    except Exception:
        pass
    # ⚠️ 必须用 multipart（-F）：raw binary（--data-binary）>1MB 会被源站挡 413
    out = subprocess.run(
        ['curl', '-s', '-u', f'{user}:{pwd}', '-X', 'POST',
         '-F', f'file=@{path};filename={title}.jpg;type=image/jpeg',
         f'{SITE}/wp-json/wp/v2/media'],
        capture_output=True, text=True).stdout
    d = json.loads(out)
    if not d.get('id'):
        print(f'  ✗ {title} 上传失败：{out[:300]}')
        sys.exit(1)
    print(f'  ↑ {title} 已上传 id={d["id"]}')
    return d['source_url'], d['id']


HTML = """<style>
.sr-collection{max-width:1000px;margin:0 auto;padding:8px 0 40px;color:#1f1d1a;
 font-family:Georgia,"Times New Roman","Songti SC","Noto Serif SC",serif;line-height:1.85}
.sr-collection h1{font-family:"Ma Shan Zheng","Songti SC",serif;font-size:34px;
 letter-spacing:4px;margin:0 0 8px;font-weight:400}
.sr-collection .sub{color:#5a554c;margin:0 0 6px;font-size:15px}
.sr-collection .rule{height:1px;background:#e3ddd0;margin:24px 0 30px}
.sr-collection .lead{background:#fff;border:1px solid #e3ddd0;border-left:3px solid #9e2b25;
 border-radius:6px;padding:16px 20px;margin:0 0 36px;font-size:15.5px}
.sr-collection .lead b{color:#9e2b25}
.sr-collection h2{font-family:"Ma Shan Zheng","Songti SC",serif;font-size:23px;font-weight:400;
 letter-spacing:2px;margin:40px 0 6px}
.sr-collection h2+.price{color:#9e2b25;font-size:14px;margin:0 0 14px;letter-spacing:1px}
.sr-collection p{margin:0 0 14px;font-size:15.5px}
.sr-collection .shots{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
 gap:14px;margin:18px 0 6px;list-style:none;padding:0;justify-content:center}
.sr-collection .shots li{margin:0}
.sr-collection .shots.one{grid-template-columns:minmax(0,320px);justify-content:center}
.sr-collection .shots img{width:100%;display:block;border:1px solid #e3ddd0;border-radius:4px}
.sr-collection .shots span{display:block;font-size:13.5px;color:#6b6559;margin-top:8px;text-align:center}
.sr-collection .cta{display:inline-block;background:#9e2b25;color:#fff;text-decoration:none;
 padding:13px 30px;border-radius:3px;font-size:16px;letter-spacing:2px;margin:6px 0 10px}
.sr-collection .cta:hover{background:#86241f}
.sr-collection .cta.cta-minor{background:#fff;color:#9e2b25;border:1px solid #9e2b25;padding:11px 24px;font-size:15px}
.sr-collection .cta.cta-minor:hover{background:#f6f1e6}
.sr-collection .note{font-size:14.5px;color:#6b6559;line-height:1.95}
.sr-collection .fine{margin-top:40px;padding-top:20px;border-top:1px solid #e3ddd0;
 font-size:13.5px;color:#6b6559;line-height:1.95}
@media (max-width:640px){.sr-collection h1{font-size:27px}.sr-collection h2{font-size:20px}}
</style>

<div class="sr-collection">
<h1>藏品</h1>
<p class="sub">第七境 · 五千年，做成可以放在手边的东西</p>
<div class="rule"></div>

<div class="lead">
<b>手机壁纸现在就能免费领，直接下载，不用等。</b>十六朝全套 32 张原图，打成一个 5.5 MB 的压缩包，点一下就到手。
桌面横版还在准备中 —— 想第一时间知道，可以顺便留个邮箱。
</div>

<h2>字形线 · 桌面横版</h2>
<p class="price">单朝 ¥12 · 商周套装 ¥19 · 含底纹</p>
<p>一个字的三千年：甲骨 → 金文 → 碑刻 → 毛笔 → 印刷，五个形态横向排开。宣纸底、朱砂点睛，
每朝配一只神兽作底纹——商是玄鸟，周是凤凰。带底纹的版本只做桌面横版。</p>
<ul class="shots">
__SHOTS_CLASSIC__
</ul>

<h2>金句线 · 手机竖版</h2>
<p class="price">十六朝 32 张 · 免费领取 · 无底纹</p>
<p>每朝两句，取那一朝最像是它自己说的话。竖排右起，顶部为锁屏时间留白，
字落在屏幕中段——低头看见的是一句话，不是一张图。</p>
<p><b>这套免费送。</b>十六朝全套，iPhone 与 Android 各 16 张，共 32 张原图，无水印，下载即得。
你天天看着它觉得好，才会想买桌面版。</p>
<ul class="shots one">
__SHOTS_PHONE__
</ul>

<h2>直接下载</h2>
<p>不用留邮箱，点下面的按钮就存到你的设备。</p>
<p><a class="cta" href="https://theseventhrealm.com/wp-content/uploads/2026/09/wallpaper-jinju-32-v2.zip">下载全套 32 张（5.5 MB）</a></p>
<p class="note">包里 32 张 PNG（iPhone / Android 各 16 张），解压即可设为壁纸。遇到问题写信到 hello@theseventhrealm.com。</p>

<h2>顺便留个邮箱</h2>
<p>桌面横版（字形线）开售时，第一时间告诉你；顺手也把 32 张手机壁纸发你一份。只发这两类消息，不做群发广告，随时可退订。</p>
<!-- MailerLite Universal · 订阅表单（账号 2674672 / 表单 ky57RZ）
     ⚠️ script 必须保持单行：wpautop 不在其保护名单里，多行会在行间插 <br> 打断脚本 -->
<script>(function(w,d,e,u,f,l,n){w[f]=w[f]||function(){(w[f].q=w[f].q||[]).push(arguments);},l=d.createElement(e),l.async=1,l.src=u,n=d.getElementsByTagName(e)[0],n.parentNode.insertBefore(l,n);})(window,document,'script','https://assets.mailerlite.com/js/universal.js','ml');ml('account', '2674672');</script>
<div class="ml-embedded" data-form="ky57RZ"></div>

<div class="fine">
第七境™ · 商标申请中，核准前一律使用 ™ 标记。<br>
手机壁纸免费提供；桌面横版付款后即时交付下载链接，因数字内容可复制，除文件损坏或未交付外不支持无理由退款。<br>
字体遵循 SIL Open Font License 1.1：衍生作品可随产品分发，字体文件本身不单独出售。<br>
古籍原文属公有领域；本产品价值在于选、编、注与版式设计。
</div>
</div>
"""


def main():
    no_upload = '--no-upload' in sys.argv
    media = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if not no_upload and len(media) < len(IMAGES):
        user, pwd = auth()
        tmp = ROOT / '11-运营/data/tmp-collection'
        tmp.mkdir(parents=True, exist_ok=True)
        for title, src, _cap, w in IMAGES:
            if title in media:
                continue
            jpg = tmp / f'{title}.jpg'
            shrink(ROOT / src, jpg, w)
            url, mid = upload(title, jpg, user, pwd)
            media[title] = {'url': url, 'id': mid, 'size': jpg.stat().st_size}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(media, ensure_ascii=False, indent=2), encoding='utf-8')

    def li(title, cap):
        u = media.get(title, {}).get('url')
        if not u:
            print(f'  ✗ 缺 {title} 的图片 URL（先跑一次不带 --no-upload）')
            sys.exit(1)
        return f'<li><img src="{u}" alt="{cap}"><span>{cap}</span></li>'

    html = (HTML
            .replace('__SHOTS_CLASSIC__',
                     '\n'.join([li('collection-shang', '商 · 玄鸟底纹'),
                                li('collection-zhou', '周 · 凤凰底纹')]))
            .replace('__SHOTS_PHONE__', li('collection-jinju-free', '商 · 手机竖版（预览）')))
    OUT.write_text(html, encoding='utf-8')
    print(f'✓ 已生成 {OUT.relative_to(ROOT)}  ({len(html)} 字节)')


if __name__ == '__main__':
    main()
