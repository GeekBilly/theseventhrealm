#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 Cloudflare 面板数据（复用你 Chrome 的登录态，不碰你正在用的浏览器）。

用法：
  python3 11-运营/scripts/read-cloudflare-analytics.py            # 概览
  python3 11-运营/scripts/read-cloudflare-analytics.py traffic    # 流量页
  python3 11-运营/scripts/read-cloudflare-analytics.py dump       # 把当前页正文全 dump 出来

原理：复制一份 Chrome profile（含 cookie）起独立无头实例 → 打开 dash.cloudflare.com → 读 DOM。
⚠️ 只用来看数，不点任何按钮、不改任何配置。
"""
import importlib.util, pathlib, re, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]

def load_ml():
    spec = importlib.util.spec_from_file_location("ml", ROOT/"11-运营/scripts/mailerlite-edit.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

ZONE = "theseventhrealm.com"

def text(ml):
    return str(ml.js("document.body.innerText"))

def clean(s):
    return re.sub(r'\n{2,}', '\n', re.sub(r'[ \t]+', ' ', s)).strip()

def setup_headed(ml, port):
    """自己起一个【有界面】的 Chrome —— Cloudflare 会拦无头浏览器。

    仍旧只用 profile 副本，不碰用户正在用的浏览器。
    """
    import shutil, subprocess as sp
    prof = ml.TMP_PROF
    chrome_prof = ml.CHROME_PROF
    shutil.rmtree(prof, ignore_errors=True)
    (prof/"Default").mkdir(parents=True, exist_ok=True)
    for src, dst in [(chrome_prof/"Local State", prof/"Local State")]:
        if src.exists(): shutil.copy2(src, dst)
    for name in ["Cookies", "Login Data", "Preferences", "Secure Preferences"]:
        src = chrome_prof/"Default"/name
        if src.exists(): shutil.copy2(src, prof/"Default"/name)
    net = chrome_prof/"Default/Network/Cookies"
    if net.exists():
        (prof/"Default/Network").mkdir(parents=True, exist_ok=True)
        shutil.copy2(net, prof/"Default/Network/Cookies")
    sp.Popen([ml.CHROME, f"--user-data-dir={prof}", f"--remote-debugging-port={port}",
              "--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu",
              "--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check",
              "--window-size=1440,960", "about:blank"],
             stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        if ml.port_alive(port): return
    raise RuntimeError(f"调试端口 {port} 没起来")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "overview"
    ml = load_ml()
    port = ml.free_port(9344)
    setup_headed(ml, port)          # ⚠️ 有界面，绕过 Cloudflare 的机器人验证
    ml.ab("connect", str(port), check=False)
    try:
        print("── 打开 Cloudflare 面板 ──")
        ml.goto("https://dash.cloudflare.com/", wait=14)
        t = clean(text(ml))
        print(f"  当前 URL: {ml.js('location.href')}")
        if "log in" in t.lower() or "登录" in t[:200]:
            print("  🔐 未登录 —— 需要你在浏览器里登录一次 Cloudflare")
            print("  页面开头:", t[:300])
            return

        # 找 zone 链接
        hrefs = ml.js("JSON.stringify([...document.querySelectorAll('a')].map(a=>a.href).filter(h=>h.includes('theseventhrealm')||h.includes('analytics')).slice(0,20))")
        print(f"  站点/分析相关链接: {str(hrefs)[:400]}")

        urls = {
            "overview": f"https://dash.cloudflare.com/?to=/:account/{ZONE}/analytics",
            "traffic":  f"https://dash.cloudflare.com/?to=/:account/{ZONE}/analytics/traffic",
        }
        if mode in urls:
            ml.goto(urls[mode], wait=16)
            t2 = clean(text(ml))
            print(f"\n  URL: {ml.js('location.href')}")
            print("── 面板正文（前 3000 字）──")
            print(t2[:3000])
        else:
            print("── 面板正文（前 3000 字）──")
            print(t[:3000])
    finally:
        ml.teardown(keep_open=False)

if __name__ == "__main__":
    main()
