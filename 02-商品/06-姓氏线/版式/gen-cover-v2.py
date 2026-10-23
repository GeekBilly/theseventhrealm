#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百家姓封面 v2 生成器 —— 复刻《16 张朝代手机壁纸》成功封面版式
（2026-10-23 用户提供基准截图：居中排版海报，非书画分区版式）

版式骨架（与基准图逐层同构）：
  题签「第七境 · 上下五千年」→ 朱砂红线 → 大标题 → 副标题「四姓 → 百家姓」
  → 清单（本期 4 姓 + 人物）→ 灰细线 → 朱砂钩子「想要原图 · 后台滴滴我」
  → 规格行 → 方框描边印「第七境」

数据源：04-市场/03-推广获客/姓氏日更-202610/DNN-XXXX.md
  从正文里正则提取形如「周 · 周瑜」的行（单字姓 · 人名），取前 4 条。
  ⚠️ 人物一律来自文案，脚本不编造。

用法：
  python3 gen-cover-v2.py --day D02        # 出单期
  python3 gen-cover-v2.py --all            # 出全部 25 期
  python3 gen-cover-v2.py --day D02 --no-shot   # 只生成 HTML 不截图
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
MD_DIR = f"{ROOT}/04-市场/03-推广获客/姓氏日更-202610"
BUILD = f"{ROOT}/02-商品/06-姓氏线/版式/_build-cover"
OUT = f"{ROOT}/02-商品/06-姓氏线/成品-手机竖版/封面-3x4"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

W, H = 1179, 1572          # 小红书 3:4
HOOK = "想要原图 · 后台滴滴我"   # 基准图原文照抄，已验证，不要自创
H1 = "100 张姓氏手机壁纸"

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@font-face{{font-family:'Noto Serif SC Black Local';
  src:url('file://{ROOT}/02-商品/02-素材/字体/nssc-black.woff2') format('woff2');
  font-weight:900}}
:root{{--ink:#1a1a18;--cinnabar:#b03826;
  --f-body:'Noto Serif SC','Songti SC',Georgia,serif}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#fff}}
.stage{{width:{W}px;height:{H}px;background:#fff;display:flex;flex-direction:column;
  align-items:center;text-align:center;font-family:var(--f-body);color:var(--ink)}}

.kicker{{margin-top:148px;font-size:27px;letter-spacing:11px;text-indent:11px;color:#6b675f}}
.rule-red{{margin-top:38px;width:840px;height:3px;background:var(--cinnabar)}}
.h1{{margin-top:100px;font-family:'Noto Serif SC Black Local','Songti SC',serif;font-weight:900;
  font-size:96px;line-height:1.15;letter-spacing:4px;text-indent:4px;color:var(--ink)}}
.h2{{margin-top:42px;font-weight:700;font-size:44px;letter-spacing:9px;text-indent:9px;color:#3d3931}}

.list{{margin-top:88px;font-size:32px;letter-spacing:7px;text-indent:7px;color:#3d3931;line-height:2.05}}
.list .nm{{font-weight:700}}

.rule-gray{{margin-top:74px;width:840px;height:1px;background:#ded7c9}}

.hook{{margin-top:82px;font-weight:900;font-size:64px;letter-spacing:5px;text-indent:5px;color:var(--cinnabar)}}
.spec{{margin-top:52px;font-size:25px;letter-spacing:3px;color:#78736a}}
.spec2{{margin-top:22px;font-size:25px;letter-spacing:3px;color:#78736a}}

.seal{{margin-top:60px;width:152px;height:94px;border:4px solid var(--cinnabar);
  display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:34px;letter-spacing:7px;text-indent:7px;color:var(--cinnabar)}}
</style>
</head>
<body>
<div class="stage">
  <div class="kicker">第七境 · 上下五千年</div>
  <div class="rule-red"></div>

  <div class="h1">{H1}</div>
  <div class="h2">{four} → 百家姓</div>

  <div class="list">
{rows}
  </div>

  <div class="rule-gray"></div>

  <div class="hook">{HOOK}</div>
  <div class="spec">iPhone 1179×2556 · Android 1080×2400</div>
  <div class="spec2">无水印 · 可直接设为手机壁纸</div>

  <div class="seal">第七境</div>
</div>
</body>
</html>
"""


def parse_md(path):
    """返回 (四姓连写, [(姓, 人名), ...])；提取不到返回 (None, [])"""
    txt = open(path, encoding="utf-8").read()
    # 人名允许带括号（如 D23「卜 · 卜商（子夏）」），故字符集含全角/半角括号
    pairs = re.findall(r"^([一-龥])\s*[·]\s*([一-龥（）()]{2,12})\s*$", txt, re.M)
    if len(pairs) < 4:
        return None, pairs
    pairs = pairs[:4]
    four = "".join(p[0] for p in pairs)
    return four, pairs


def build(day, no_shot=False):
    md = os.path.join(MD_DIR, [f for f in os.listdir(MD_DIR)
                               if f.startswith(day + "-")][0]) \
        if any(f.startswith(day + "-") for f in os.listdir(MD_DIR)) else None
    if not md:
        print(f"  ✗ {day} 文案不存在"); return False

    four, pairs = parse_md(md)
    if not four:
        print(f"  ✗ {day} 提取不到 4 组「姓 · 人名」（{os.path.basename(md)}）"); return False

    rows = "\n".join(
        f'    <div><span class="nm">{s}</span> · {n}</div>' for s, n in pairs)
    html = TPL.format(ROOT=ROOT, W=W, H=H, H1=H1, HOOK=HOOK, four=four, rows=rows)

    os.makedirs(BUILD, exist_ok=True)
    stem = os.path.basename(md)[:-3]
    hpath = os.path.join(BUILD, stem + "-cover.html")
    open(hpath, "w", encoding="utf-8").write(html)

    if no_shot:
        print(f"  ✓ HTML {stem}"); return True

    os.makedirs(OUT, exist_ok=True)
    png = os.path.join(OUT, f"{stem}-封面-{W}x{H}.png")
    if os.path.exists(png):
        os.remove(png)
    subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-setuid-sandbox",
                    "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                    "--user-data-dir=/tmp/cp-cover-v2", "--force-device-scale-factor=1",
                    f"--window-size={W},{H}", "--virtual-time-budget=8000",
                    f"--screenshot={png}", f"file://{hpath}"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    ok = os.path.exists(png) and os.path.getsize(png) > 0
    print(f"  {'✓' if ok else '✗'} {day} {four} → {os.path.basename(png) if ok else '截图失败'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="D01 / D02 …")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-shot", action="store_true")
    a = ap.parse_args()

    if a.day:
        days = [a.day]
    elif a.all:
        days = sorted({f.split("-")[0] for f in os.listdir(MD_DIR)
                       if re.match(r"^D\d\d-", f)})
    else:
        print("需 --day 或 --all"); sys.exit(1)

    print(f"百家姓封面 v2 · {len(days)} 期 · {W}×{H}")
    ok = sum(1 for d in days if build(d, a.no_shot))
    print(f"── 完成 {ok}/{len(days)} ──")


if __name__ == "__main__":
    main()
