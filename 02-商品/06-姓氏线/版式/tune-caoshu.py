#!/usr/bin/env python3
"""草书逐字缩放收敛：渲染→检测标签带墨迹→异常字再加缩→重生成，直到全部干净。
表文件 shrink-caoshu.json = {"default": 0.78, "char": {"卫": 0.66, ...}}"""
import json, os, re, glob, subprocess, sys, time
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
SP = os.path.join(ROOT, "shrink-caoshu.json")
PY = "/Users/billyhou/.workbuddy/binaries/python/envs/default/bin/python"
CH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
THRESH = 70          # 标签带墨迹阈值（干净 ≈23，即标签自身文字）
FACTOR = 0.85        # 每轮异常字系数再乘
MAX_ROUNDS = 5

def load():
    return json.load(open(SP, encoding="utf-8")) if os.path.exists(SP) else {"default": 0.78, "char": {}}

def save(t):
    json.dump(t, open(SP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def gen():
    subprocess.run([PY, "gen-surname-v2a.py", "--tpl", "phone", "--variant", "android",
                    "--first", "100"], check=True, capture_output=True)

def lab_ink_png(p):
    im = Image.open(p).convert("L")
    return sum(1 for y in range(770, 800, 2) for x in range(388, 692, 2) if im.getpixel((x, y)) < 200)

def render_detect(sv):
    fs = glob.glob(f"_build-v2a/surname-*-{sv}-phone-android.html")
    if not fs:
        return None
    out = f"/tmp/tune-{sv}.png"
    if os.path.exists(out):
        os.remove(out)
    p = subprocess.Popen([CH, "--headless=new", "--no-sandbox", "--disable-setuid-sandbox",
        "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
        "--user-data-dir=/tmp/cp-tune", "--force-device-scale-factor=1",
        "--window-size=1080,2400", "--virtual-time-budget=9000",
        f"--screenshot={out}", "file://" + os.path.abspath(fs[0])],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(150):
        if os.path.exists(out) and os.path.getsize(out) > 10000:
            break
        time.sleep(0.3)
    time.sleep(0.5)
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()
    return lab_ink_png(out) if os.path.exists(out) else None

def chars_of():
    r = {}
    for f in glob.glob("_build-v2a/surname-*-phone-android.html"):
        m = re.search(r"surname-(\d+)-(.+?)-phone-android\.html$", f)
        if m:
            r[m.group(2)] = int(m.group(1))
    return r

def main():
    t = load()
    chars = chars_of()
    # 第 1 轮：直接用现有成品 PNG 检测（当前 shrink 状态下的真实结果）
    bad = {}
    for sv in chars:
        png = f"/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/06-姓氏线/成品-手机竖版/Android/{sv}-1080x2400.png"
        if os.path.exists(png):
            v = lab_ink_png(png)
            if v > THRESH:
                bad[sv] = v
    print(f"第 1 轮（读现有成品）：异常 {len(bad)} 字：{sorted(bad, key=bad.get, reverse=True)[:8]}{'…' if len(bad)>8 else ''}")
    rnd = 1
    while bad and rnd < MAX_ROUNDS:
        rnd += 1
        for sv in bad:
            t["char"][sv] = round(t["char"].get(sv, t["default"]) * FACTOR, 3)
        save(t)
        gen()
        print(f"── 第 {rnd} 轮：缩放表更新，重渲 {len(bad)} 字 ──")
        still = {}
        for sv in sorted(bad):
            v = render_detect(sv)
            tag = ""
            if v is None:
                tag = "渲染失败"
                still[sv] = 999
            elif v > THRESH:
                still[sv] = v
                tag = f"仍压 {v}"
            else:
                tag = f"干净 ({v})"
            print(f"   {sv}: {tag}")
        bad = still
    save(t)
    print(f"== 收敛：{'仍有 ' + str(len(bad)) + ' 字未过' if bad else '全部干净 ✓'}（共 {rnd-1} 轮迭代）")
    print("最终缩放表:", json.dumps(t["char"], ensure_ascii=False))
    sys.exit(1 if bad else 0)

main()
