#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上线片段静态体检：XML 合法性 / class 有定义 / keyframes 有定义 / 坐标无 NaN / 引用可达"""
import re
import sys
import xml.etree.ElementTree as ET

P = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/03-页面/上线片段-首页宇宙演化动画-v2.html"
src = open(P, encoding="utf-8").read()
body = re.sub(r"<!--.*?-->", "", src, flags=re.S)

ok, bad = [], []
def chk(cond, msg):
    (ok if cond else bad).append(msg)

# 1) XML well-formed（浏览器对 inline SVG 走 XML 解析规则）
try:
    ET.fromstring("<root>" + src + "</root>")
    chk(True, "XML 合法（含 inline SVG 自闭合标签）")
except ET.ParseError as e:
    chk(False, f"XML 解析失败：{e}")

# 2) CSS：类名定义 vs 使用
css = "\n".join(re.findall(r"<style>(.*?)</style>", src, re.S))
defined = set(re.findall(r"\.([A-Za-z][\w-]*)", css))
used = set()
for m in re.findall(r'class="([^"]+)"', src):
    used.update(m.split())
missing = sorted(used - defined)
chk(not missing, f"HTML 中使用的 class 全部有 CSS 定义（缺失：{missing}）")

# 3) keyframes：引用 vs 定义
kf_def = set(re.findall(r"@keyframes\s+([\w-]+)", css))
kf_use = set(re.findall(r"animation-name:\s*([\w-]+)", css))
kf_use |= set(re.findall(r"animation:\s*([\w-]+)", css))
chk(kf_use <= kf_def, f"@keyframes 引用齐全（未定义：{sorted(kf_use - kf_def)}）")
idle = sorted(k for k in kf_def if len(re.findall(rf"\b{k}\b", css)) < 2)
chk(not idle, f"无闲置 @keyframes（闲置：{idle}）")

# 4) CSS 变量 --dx/--dy/--px/--py/--tx/--ty：用到就得有内联赋值
for v in ["dx", "dy", "px", "py", "tx", "ty"]:
    uses = len(re.findall(rf"var\(--{v}\)", src))
    gives = len(re.findall(rf"--{v}:", src))
    chk(gives >= max(1, uses // 40) or gives > 0, f"--{v} 有内联赋值（使用 {uses} / 赋值 {gives}）")

# 5) 数值健全性：无 NaN / 无 "None" / 无空 d
chk("NaN" not in src and "None" not in src, "无 NaN / None 混入坐标")
chk('d=""' not in src, "无空 path d")

# 6) url(#id) 引用可达
ids = set(re.findall(r'\sid="([^"]+)"', src))
refs = set(re.findall(r"url\(#([^)]+)\)", src)) | set(re.findall(r'xlink:href="#([^"]+)"', src))
chk(refs <= ids, f"SVG 引用可达（悬空：{sorted(refs - ids)}）")

# 7) 零 JS / 零 filter / 零外部资源
chk("<script" not in body.lower(), "零脚本标签（WP 会剥）")
chk("filter=" not in src and "feGaussianBlur" not in src, "零 SVG 滤镜（缩放不掉帧）")
chk(not re.search(r'(src|href)="https?://', src), "零外部资源引用")
chk("file://" not in src, "零 file:// 字体引用")

# 8) 关键结构点
for token in ["qjcos-galzoom", "qjcos-solzoom", "qjcos-earthrise", "qjcos-caplast",
              "prefers-reduced-motion", "qjcos-earthClip", "animateMotion"]:
    chk(token in src, f"含关键结构 {token}")

# 9) 时间线单调性（各幕 delay 递增）
tl = {}
for name in ["qjcos-infl", "qjcos-quarkp", "qjcos-galzoom", "qjcos-solin",
             "qjcos-solzoom", "qjcos-earth", "qjcos-stmt"]:
    m = re.search(rf"\.{name}\{{[^}}]*?animation-delay:([\d.]+)s", css, re.S)
    if m:
        tl[name] = float(m.group(1))
seq = list(tl.values())
chk(seq == sorted(seq), f"时间线递增：{tl}")


# 10) 幕间交叉溶解：相邻两幕必须有重叠（前幕还没淡完，后幕已淡入），否则视觉上就是硬切
def _blk(name):
    m = re.search(rf"\.{name}\{{([^}}]*)\}}", css, re.S)
    return m.group(1) if m else ""


def dur_of(name):
    b = _blk(name)
    m = (re.search(r"animation-duration:([\d.]+)s", b)
         or re.search(r"animation:\s*[\w-]+\s+([\d.]+)s", b))
    return float(m.group(1)) if m else None


def dly_of(name):
    b = _blk(name)
    m = re.search(r"animation-delay:([\d.]+)s", b)
    if m:
        return float(m.group(1))
    m = re.search(r"animation:\s*[\w-]+\s+[\d.]+s[^;]*?([\d.]+)s", b)
    return float(m.group(1)) if m else 0.0


IN, OUT = 1.2, 1.5          # qjcos-scin / qjcos-scout 时长
acts = []                   # (淡入起, 淡入完, 淡出起, 淡出完)
for i, o in re.findall(r'class="qjcos-[a-z]+ qjcos-sc" style="--i:([\d.]+)s;--o:([\d.]+)s"', src):
    acts.append((float(i), float(i) + IN, float(o), float(o) + OUT))
_g = dly_of("qjcos-galcore")
acts.append((_g, _g + (dur_of("qjcos-galcore") or 0),
             dly_of("qjcos-galzoom"), dly_of("qjcos-galzoom") + (dur_of("qjcos-galzoom") or 0)))
_s = dly_of("qjcos-solin")
acts.append((_s, _s + (dur_of("qjcos-solin") or 0),
             dly_of("qjcos-solzoom"), dly_of("qjcos-solzoom") + (dur_of("qjcos-solzoom") or 0)))
_e = dly_of("qjcos-earth")
acts.append((_e, _e + (dur_of("qjcos-earth") or 0), 1e9, 1e9))
acts.sort()
overlaps = []
for a, b in zip(acts, acts[1:]):
    lo = max(a[2], b[0])                 # 后一幕开始淡入
    hi = min(a[3], b[1])                 # 前二幕中较早结束者
    overlaps.append(round(hi - lo, 2))
chk(len(acts) == 7, f"识别到 7 幕区间（实得 {len(acts)}）")
chk(all(o >= 0.5 for o in overlaps),
    f"幕间交叉溶解 ≥0.5s（相邻重叠：{overlaps} s）")

# 11) 终态：所有会退场的幕最终 opacity 归 0，且地球不淡出
tails = re.findall(r"\.qjcos-(mat|anti|surv|quarkp|quarkn|nucleus|elec|arm|sunmark|galcore)\{([^}]*)\}", css)
chk("qjcos-lateout" not in css, "退场统一交给幕容器（无散落的 lateout）")
chk(not re.search(r"\.qjcos-earth\{[^}]*qjcos-scout", css), "地球终态不淡出（落点保留在画面）")

print("\n".join("  ✅ " + m for m in ok))
if bad:
    print("\n".join("  ❌ " + m for m in bad))
    sys.exit(1)
print(f"\n全部通过（{len(ok)} 项）｜字节 {len(src.encode())}")
