#!/usr/bin/env python3
"""把「宇宙演化」动画片段插进首页（页面 13）并写入线上。

用法：
    python3 deploy-cosmos.py --dry       # 只生成待发布正文，不写线上
    python3 deploy-cosmos.py             # 生成并 POST 到线上
    python3 deploy-cosmos.py --rollback  # 用备份原文回滚
"""
import json
import re
import subprocess
import sys

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
BACKUP = BASE + "/11-运营/上线备份/page13-raw-20261017.json"
SNIPPET = BASE + "/03-页面/上线片段-首页宇宙演化动画-v2.html"
OUT = BASE + "/11-运营/上线备份/page13-new-20261017-raw.html"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

BRUSH = ('<svg class="brush" viewBox="0 0 200 14" preserveAspectRatio="none" aria-hidden="true">'
         '<path d="M3 8 C 26 5, 52 11, 84 8 C 126 4, 160 10, 197 7 '
         'C 168 12, 126 14, 92 11 C 58 9, 26 12, 3 8 Z"/></svg>')


def load_snippet():
    s = open(SNIPPET, encoding="utf-8").read()
    s = re.sub(r"^\s*<!--.*?-->\s*", "", s, count=1, flags=re.S)
    return s.strip()


def fetch_live_raw():
    pw = subprocess.run(["security", "find-generic-password", "-s",
                         "theseventhrealm-wp", "-w"],
                        capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["curl", "-s", "-A", UA, "-u", "MollyBot_No.2:" + pw,
                        "-H", "Accept: application/json", "--compressed", "-L",
                        "--max-time", "60",
                        "https://theseventhrealm.com/wp-json/wp/v2/pages/13?context=edit"],
                       capture_output=True, text=True)
    return json.loads(r.stdout)["content"]["raw"]


def build():
    # 以本地已发布的正文为底稿（与线上一致，避免大响应被截断）
    import os
    base = OUT if os.path.exists(OUT) else None
    raw = open(base, encoding="utf-8").read() if base else fetch_live_raw()
    json.load(open(BACKUP, encoding="utf-8"))  # 备份存在性校验
    block = ("\n\n<section>\n"
             "  <h2>万物从何而来</h2>\n"
             "  " + BRUSH + "\n"
             "  " + load_snippet() + "\n"
             "</section>\n")
    if "qjcos-hero" in raw:
        # 替换模式：整段换掉，避免「先回滚再插入」造成线上中间态
        head, _, rest = raw.partition('<section>\n  <h2>万物从何而来</h2>')
        _, sep, tail = rest.partition('<section class="verse reveal">')
        if not head or not sep:
            sys.exit("[stop] 找不到动画段边界，人工处理")
        return raw, head + block.lstrip("\n") + "\n\n" + sep + tail
    anchor = "</header>"
    if raw.count(anchor) != 1:
        sys.exit("[stop] </header> 出现 %d 次，锚点不唯一" % raw.count(anchor))
    return raw, raw.replace(anchor, anchor + block, 1)


def post(content):
    pw = subprocess.run(["security", "find-generic-password", "-s",
                         "theseventhrealm-wp", "-w"],
                        capture_output=True, text=True).stdout.strip()
    open("/tmp/qj_page13_payload.json", "w", encoding="utf-8").write(
        json.dumps({"content": content}, ensure_ascii=False))
    r = subprocess.run([
        "curl", "-s", "-X", "POST",
        "-A", UA, "-u", "MollyBot_No.2:" + pw,
        "-H", "Content-Type: application/json",
        "-H", "Accept: application/json",
        "--compressed", "-L", "--max-time", "90",
        "--data-binary", "@/tmp/qj_page13_payload.json",
        "https://theseventhrealm.com/wp-json/wp/v2/pages/13",
    ], capture_output=True, text=True)
    try:
        j = json.loads(r.stdout)
    except Exception:
        print("非 JSON 响应，前 800 字：\n", r.stdout[:800])
        return None
    if "id" in j:
        print("[ok] id=%s status=%s modified=%s" % (j["id"], j.get("status"), j.get("modified")))
        print("[ok] 线上正文字数 %d" % len(j["content"]["raw"]))
        return j
    print("[fail]", json.dumps(j, ensure_ascii=False)[:800])
    return None


def verify():
    """发布后抓线上 HTML 实测：wpautop 有没有再往 <style>/<svg> 里插 <p>。"""
    pw = subprocess.run(["security", "find-generic-password", "-s",
                         "theseventhrealm-wp", "-w"],
                        capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["curl", "-s", "-A", UA, "-u", "MollyBot_No.2:" + pw,
                        "-H", "Accept: text/html", "--compressed", "-L",
                        "--max-time", "150", "https://theseventhrealm.com/"],
                       capture_output=True, text=True)
    html = r.stdout
    open(OUT.replace("page13-new", "live13"), "w", encoding="utf-8").write(html)
    m = re.search(r"<style[^>]*>(\.qjcos-hero.*?)</style>", html, re.S)
    if not m:
        print("[verify] ✗ 线上找不到动画 <style>")
        return False
    css = m.group(1)
    ptag = lambda t: len(re.findall(r"</?p[ >]", t))   # 注意别把 <path> 算进来
    bad = ptag(css)
    s0 = html.find('<svg class="qjcos-scene qjcos-sc-w"')
    s1 = html.find("</svg>", s0)
    svg_p = ptag(html[s0:s1]) if s0 > 0 else -1
    ok = (bad == 0 and svg_p == 0 and css.count("@keyframes") > 10
          and "prefers-reduced-motion" in css and "qjcos-hero" in html)
    print("[verify] style 内 <p>=%d | svg 内 <p>=%d | @keyframes=%d | 字节=%d → %s"
          % (bad, svg_p, css.count("@keyframes"), len(html),
             "OK" if ok else "✗ 仍有污染，回滚并重查"))
    return ok


if __name__ == "__main__":
    if "--verify" in sys.argv:          # 只抓线上实测，不发布
        verify()
        sys.exit(0)
    raw, new = build()
    open(OUT, "w", encoding="utf-8").write(new)
    print("待发布正文：%d -> %d 字符 (+%d)" % (len(raw), len(new), len(new) - len(raw)))
    if "--rollback" in sys.argv:
        post(raw)
    elif "--dry" not in sys.argv:
        if post(new):
            import time
            time.sleep(3)
            verify()
