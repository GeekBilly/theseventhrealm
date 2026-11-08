#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《谁动了我的 Token》· 上架主图生成（零积分，纯代码）
==================================================

为什么不用 ImageGen：积分只剩 115、cycleUsed 97.9%，跑道约 3.1 天，
批量出图是明令禁止的动作。这里用本机 Chrome headless 把 HTML 截成 PNG。

用法：
    python3 build-lp-assets.py            # 生成全部
    python3 build-lp-assets.py --keep     # 生成并保留中间 HTML（调试用）

产物：主图/01-封面.png … 04-价格.png（800×800，淘宝主图 1:1）
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "主图"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 配色（水墨调）
PAPER = "#f7f6f3"
INK = "#1a1a18"
INK2 = "#5a554c"
LINE = "#ded8ca"
CINNABAR = "#9e2b25"

FONT_SERIF = '"Songti SC","STSong","Kaiti SC","STKaiti","Times New Roman",serif'
FONT_BRUSH = '"Kaiti SC","STKaiti","Songti SC","STSong",serif'

HEAD = """<meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:800px;height:800px;background:%s;font-family:%s;color:%s;
 -webkit-font-smoothing:antialiased;overflow:hidden;position:relative}
.brand{position:absolute;top:46px;left:56px;font-size:17px;letter-spacing:5px;color:%s}
.brand b{color:%s;font-weight:400}
.big{position:absolute;left:56px;top:170px;font-family:%s;font-size:72px;letter-spacing:3px;
 line-height:1.22;color:%s;font-weight:400}
.sub{position:absolute;left:58px;top:352px;font-size:25px;line-height:1.75;color:%s;width:660px}
.kicker{position:absolute;left:58px;top:118px;font-size:21px;letter-spacing:3px;color:%s}
.bar{position:absolute;left:56px;right:56px;bottom:118px;border-top:1px solid %s;padding-top:26px}
.barnum{font-family:%s;font-size:52px;color:%s;letter-spacing:2px}
.barnum s{font-size:30px;color:%s;text-decoration:none;padding:0 9px}
.barp{font-size:19px;color:%s;margin-top:10px;letter-spacing:1px}
.foot{position:absolute;left:56px;right:56px;bottom:52px;font-size:16px;color:%s;
 letter-spacing:1px;display:flex;justify-content:space-between}
</style>
""" % (PAPER, FONT_SERIF, INK, INK2, CINNABAR, FONT_BRUSH, INK, INK2, CINNABAR, LINE,
       FONT_BRUSH, CINNABAR, INK2, INK2, INK2)

FOOT = """<div class="foot"><span>第七境 · 长项目工具</span><span>hello@theseventhrealm.com</span></div>"""


def page(body):
    return HEAD + body + "</html>"


def img_cover():
    return page(f"""
<div class="brand">第七境 · <b>长项目工具</b></div>
<div class="kicker">记忆文件越写越胖</div>
<div class="big">谁动了<br>我的 Token</div>
<div class="sub">你以为它在「回忆」——<br>其实每一轮，它都在把你写过的规矩、结论、历史<br><b>重新发一遍</b>。</div>
<div class="bar">
  <div class="barnum">15,682 <s>→</s> 3,398 <s style="font-size:24px">字</s></div>
  <div class="barp">实测：改成索引模式后降 <b>78%</b>　·　体验版 0 元，22 天烧掉 4,014 积分</div>
</div>
{FOOT}
""")


def img_numbers():
    cells = """
<div style="position:absolute;left:56px;right:56px;top:150px">
  <div style="display:flex;gap:18px">
    <div style="flex:1;background:#fff;border:1px solid %(line)s;border-radius:8px;padding:24px 22px">
      <div style="font-family:%(brush)s;font-size:52px;color:%(cin)s;line-height:1.2">4,014</div>
      <div style="font-size:18px;color:%(ink2)s;margin-top:8px">22 天真实烧掉的积分</div>
    </div>
    <div style="flex:1;background:#fff;border:1px solid %(line)s;border-radius:8px;padding:24px 22px">
      <div style="font-family:%(brush)s;font-size:52px;color:%(cin)s;line-height:1.2">78%%</div>
      <div style="font-size:18px;color:%(ink2)s;margin-top:8px">记忆文件压薄后的降幅</div>
    </div>
  </div>
  <div style="margin-top:18px;background:#fff;border:1px solid %(line)s;border-radius:8px;padding:24px 22px">
    <div style="font-family:%(brush)s;font-size:44px;color:%(cin)s;line-height:1.25">15,682 <span style="font-size:26px;color:%(ink2)s">→</span> 3,398</div>
    <div style="font-size:18px;color:%(ink2)s;margin-top:8px">改造前后的字符数　·　每一轮都在为它付钱</div>
  </div>
</div>
<div style="position:absolute;left:56px;right:56px;top:520px;font-size:23px;line-height:1.9;color:%(ink)s">
  成本 ＝ <b>轮次 × 当前高度</b><br>
  <span style="color:%(ink2)s;font-size:20px">清缓存没用、少写点字没用、加长上下文更没用——<br>只有把文件改薄有用。</span>
</div>
""" % {"line": LINE, "brush": FONT_BRUSH, "cin": CINNABAR, "ink2": INK2, "ink": INK}
    return page(f"""
<div class="brand">第七境 · <b>长项目工具</b></div>
<div class="kicker">先看三个数字</div>
{cells}
{FOOT}
""")


def img_how():
    steps = [
        ("①", "体检", "量出三个数字：总共多大、多少真用得上、剩下多少白付"),
        ("②", "改造稿", "拆成「留 / 下沉 / 归档」三堆，摘要位置留成填空题"),
        ("③", "对照", "改完再跑一次，把改前改后并排放给你看"),
    ]
    html = '<div style="position:absolute;left:56px;right:56px;top:176px">'
    for num, name, desc in steps:
        html += f"""
  <div style="display:flex;gap:20px;margin-bottom:34px;align-items:flex-start">
    <div style="flex:0 0 58px;height:58px;border-radius:50%;background:{CINNABAR};color:#fff;
     font-size:26px;text-align:center;line-height:58px;font-family:{FONT_SERIF}">{num}</div>
    <div style="flex:1">
      <div style="font-family:{FONT_BRUSH};font-size:33px;color:{INK};letter-spacing:2px">{name}</div>
      <div style="font-size:20px;color:{INK2};margin-top:6px;line-height:1.7">{desc}</div>
    </div>
  </div>"""
    html += "</div>"
    html += f"""
<div style="position:absolute;left:56px;right:56px;bottom:150px;background:#fff;
 border:1px solid {LINE};border-left:3px solid {CINNABAR};border-radius:6px;padding:18px 22px;
 font-size:19px;line-height:1.8;color:{INK2}">
  <b style="color:{CINNABAR}">它不会碰你的文件。</b>　体检只读，改造稿只新建文件。<br>
  哪条该留哪条该沉，工具只给建议，<b style="color:{INK}">最终由你拍板</b>。
</div>"""
    return page(f"""
<div class="brand">第七境 · <b>长项目工具</b></div>
<div class="kicker">这个工具做什么</div>
{html}
{FOOT}
""")


def img_price():
    tiers = [
        ("自检版", "¥9.9", "清单 ＋ 填空表 ＋<br>成本黑洞对照表", False),
        ("体检版", "¥39", "体检工具 ＋ 改造稿 ＋<br>三个模板 ＋ 对照报告", True),
        ("陪跑季", "¥79", "体检版全部 ＋<br>整季更新 ＋ 复盘建议", False),
    ]
    html = ('<div style="position:absolute;left:56px;right:56px;top:142px;'
            'display:flex;gap:14px;align-items:stretch">')
    for name, price, desc, hot in tiers:
        border = f"border:2px solid {CINNABAR};" if hot else f"border:1px solid {LINE};"
        if hot:
            tag = (f'<span style="display:inline-block;background:{CINNABAR};color:#fff;'
                   f'font-size:15px;border-radius:3px;padding:3px 11px">主推</span>')
        else:
            tag = ""
        html += f"""
  <div style="flex:1;background:#fff;{border}border-radius:8px;padding:18px 18px 16px;
   height:296px;box-sizing:border-box;display:flex;flex-direction:column">
    <div style="height:30px;flex:0 0 30px">{tag}</div>
    <div style="font-family:{FONT_BRUSH};font-size:27px;color:{INK};letter-spacing:2px;
     flex:0 0 auto">{name}</div>
    <div style="font-family:{FONT_BRUSH};font-size:42px;color:{CINNABAR};margin:2px 0 12px;
     flex:0 0 auto">{price}</div>
    <div style="font-size:16.5px;color:{INK2};line-height:1.8;flex:0 0 auto">{desc}</div>
  </div>"""
    html += "</div>"
    html += f"""
<div style="position:absolute;left:56px;right:56px;top:500px;font-size:21px;line-height:1.9;color:{INK}">
  一次买断，长期可用。装成技能后，<b>说一句「体检一下我的记忆」它自己会跑</b>。
</div>
<div style="position:absolute;left:56px;right:56px;top:600px;font-size:19px;color:{INK2};letter-spacing:1px">
  淘宝搜店铺「第七境」　·　或 WorkBuddy 技能市场
</div>"""
    return page(f"""
<div class="brand">第七境 · <b>长项目工具</b></div>
<div class="kicker">三档，按需要选</div>
{html}
{FOOT}
""")


def img_avatar():
    """开发者主页头像 512x512：极简水墨，一枚朱砂印。

    注意：字体族必须写在 <style> 块里，不能写进内联 style 属性 ——
    font-family 值本身带双引号，会把 style="..." 提前截断，导致后续属性全失效。
    """
    return f"""<meta charset="utf-8">
<style>
*{{margin:0;padding:0}}
body{{width:512px;height:512px;background:{PAPER};color:{INK};
 font-family:{FONT_SERIF};display:flex;align-items:center;justify-content:center}}
.frame{{position:relative;width:512px;height:512px}}
.glow{{position:absolute;left:0;top:0;width:512px;height:512px;
 background:radial-gradient(circle at 32% 22%, #fdfcfa 0%, {PAPER} 64%)}}
.seal{{position:absolute;left:94px;top:88px;width:324px;height:324px;
 border:3px solid {CINNABAR};border-radius:8px;display:flex;
 align-items:center;justify-content:center}}
.seal span{{font-family:{FONT_BRUSH};font-size:196px;color:{CINNABAR};line-height:1}}
.name{{position:absolute;left:0;bottom:44px;width:512px;text-align:center;
 font-size:26px;letter-spacing:16px;color:{INK2}}}
</style>
<div class="frame">
  <div class="glow"></div>
  <div class="seal"><span>境</span></div>
  <div class="name">第 七 境</div>
</div>
"""


def shoot(html_text, out_png, keep_html_dir=None, size=800):
    tmpdir = Path(tempfile.mkdtemp(prefix="mt-shot-"))
    src = tmpdir / "page.html"
    src.write_text(html_text, encoding="utf-8")
    profile = tmpdir / "profile"
    cmd = [
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-first-run", "--no-default-browser-check",
        # 本机沙箱初始化会失败（Operation not permitted），必须显式关闭
        "--no-sandbox", "--disable-dev-shm-usage",
        "--disable-software-rasterizer", "--in-process-gpu",
        f"--user-data-dir={profile}",
        "--default-background-color=FFFFFFFF",
        "--force-device-scale-factor=1",
        f"--window-size={size},{size}",
        f"--screenshot={out_png}",
        f"file://{src}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    ok = out_png.exists() and out_png.stat().st_size > 1000
    if keep_html_dir:
        shutil.copy(src, Path(keep_html_dir) / (out_png.stem + ".html"))
    shutil.rmtree(tmpdir, ignore_errors=True)
    if not ok:
        sys.stderr.write(f"截图失败：{out_png.name}\n{r.stderr[-800:]}\n")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="保留中间 HTML")
    args = ap.parse_args()

    if not Path(CHROME).exists():
        print(f"❌ 找不到 Chrome：{CHROME}")
        return 2

    if not OUT.exists():
        OUT.mkdir(parents=True, exist_ok=True)
    keep_dir = (OUT / "_html") if args.keep else None
    if keep_dir and not keep_dir.exists():
        keep_dir.mkdir(parents=True, exist_ok=True)

    items = [
        ("01-封面.png", img_cover()),
        ("02-三个数字.png", img_numbers()),
        ("03-工具做什么.png", img_how()),
        ("04-价格.png", img_price()),
        ("头像-512.png", img_avatar()),
    ]
    for name, html in items:
        out = OUT / name
        sz = 512 if "头像" in name else 800
        if shoot(html, out, keep_dir, size=sz):
            print(f"✅ {name}　{out.stat().st_size // 1024} KB")
        else:
            print(f"🔴 {name} 生成失败")
            return 1
    print(f"\n产物目录：{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
