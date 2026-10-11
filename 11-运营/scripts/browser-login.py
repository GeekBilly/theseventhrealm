#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""browser-login.py —— 给某个平台开一个【干净的、持久的】浏览器会话，供人工登录。

与 mailerlite-edit.py 的关键区别：
  · **不复制** 主浏览器的 Cookies / Login Data —— 碰不到你其他站点的登录态
  · profile 是**持久**的（存在 11-运营/.browser-profiles/<site>/），登录一次以后可复用
  · **有界面**（headed）—— 需要你本人扫码/输密码

用法
    python3 11-运营/scripts/browser-login.py zhihu
    python3 11-运营/scripts/browser-login.py zhihu --port 9444

登录完成后**不要关这个窗口**，脚本会一直守着；要结束时 Ctrl-C。
"""
import argparse, pathlib, socket, subprocess, sys, time

ROOT  = pathlib.Path(__file__).resolve().parents[2]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILES = ROOT / "11-运营/.browser-profiles"

SITES = {
    "zhihu":    ("知乎",     "https://www.zhihu.com/signin"),
    "xiaohongshu": ("小红书", "https://www.xiaohongshu.com/login"),
    "douyin":   ("抖音",     "https://www.douyin.com/"),
    "bilibili": ("B站",      "https://passport.bilibili.com/login"),
    "weixin":   ("公众号",   "https://mp.weixin.qq.com/"),
}

def free_port(start):
    for p in range(start, start + 60):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", choices=sorted(SITES))
    ap.add_argument("--port", type=int, default=9444)
    a = ap.parse_args()
    name, url = SITES[a.site]
    prof = PROFILES / a.site
    prof.mkdir(parents=True, exist_ok=True)
    port = free_port(a.port)

    print(f"── 打开 {name} 登录页 ──")
    print(f"   profile : {prof}   （独立、不含你主浏览器的任何 cookie）")
    print(f"   调试端口 : {port}")
    print(f"   地址     : {url}")
    print()
    print(f"   ⚠️ 请在刚弹出的窗口里完成登录，**登录后不要关窗口**")
    print()

    # ⚠️ 2026-10-03 实测：在 DSH 的文件沙箱下，Chrome 必须加
    #    --no-sandbox --disable-gpu 才能起来；否则会
    #    "sandbox initialization failed: Operation not permitted" 后直接退出。
    #    （之前误判成"沙箱拦死 Chrome"，实际是参数不够。）
    p = subprocess.Popen([
        CHROME,
        f"--user-data-dir={prof}",
        f"--remote-debugging-port={port}",
        "--no-sandbox", "--disable-gpu", "--disable-crash-reporter",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1280,900", "--window-position=80,80",
        "--new-window", url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 记下端口，方便后续脚本接管
    (prof / ".debug-port").write_text(str(port))
    print(f"   ✅ 浏览器已启动（PID {p.pid}）")
    print(f"   ✅ 端口已记录 → {prof/'.debug-port'}")
    print()
    print("   登录完成后回到这里，按 Ctrl-C 结束（profile 会保留，登录态下次可用）")
    try:
        while p.poll() is None:
            time.sleep(3)
        print("   浏览器窗口已关闭。")
    except KeyboardInterrupt:
        print("\n   收到中断 —— 浏览器保持打开，profile 已保存。")

if __name__ == "__main__":
    main()
