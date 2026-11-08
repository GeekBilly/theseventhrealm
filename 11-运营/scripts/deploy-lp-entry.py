#!/usr/bin/env python3
"""给首页（页面 13）正文末尾插入一条 /memory-token/ 站内入口。

REQ-2026-11-08-02。只做最小增量插入：线上原文取回 → 插一行 → POST 回去。

用法：
    python3 deploy-lp-entry.py --dry        # 只生成待发布正文，不碰线上
    python3 deploy-lp-entry.py              # 发布 + 清 CDN + 复核
    python3 deploy-lp-entry.py --rollback   # 用备份原文回滚 + 清 CDN

铁律：
  - 既有正文的空行一个都不动（整篇压空行会改变 178KB 长页的既有渲染）
  - 新增块单行、内部无空行（wpautop 会往空行插 <p>）
  - 所有 curl 带浏览器 UA + --noproxy '*'
  - 发完必清 CDN，且必须在前端复核之前清
  - 失败一次即降级：不重试、不排障
"""
import json
import os
import re
import subprocess
import sys

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
BACKUP_DIR = os.path.join(BASE, "11-运营", "上线备份")
BACKUP = os.path.join(BACKUP_DIR, "page13-raw-before-lp-entry-20261108.html")
AFTER = os.path.join(BACKUP_DIR, "page13-raw-after-lp-entry-20261108.html")
PAYLOAD = "/tmp/qj_page13_lp_entry_payload.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
API = "https://theseventhrealm.com/wp-json/wp/v2/pages/13"
SITE = "https://theseventhrealm.com/"
CF_PURGE = os.path.join(BASE, "11-运营", "scripts", "cf-cache-rules.py")

ANCHOR = '<style id="qj-rhythm">'
LINK = 'href="/memory-token/"'

# 单行、无空行、不用 .reveal（避免滚动观察器未初始化导致隐藏）、不引入新 CSS 类
BLOCK = (
    '<section><p style="max-width:580px;margin:0 auto;line-height:2.1;'
    'color:#8c8578;letter-spacing:.06em;font-size:14px;text-align:center">'
    '另作 · 做这套长卷时，顺手把一个不相干的问题查明白了：'
    'AI 长项目为什么越用越贵、越用越笨。方法全文免费，工具在你自己机器上只读不写。'
    '<a ' + LINK + ' style="color:#b03826;text-decoration:none;'
    'border-bottom:1px solid #ded7c8;padding-bottom:3px">'
    '谁动了我的Token →</a></p></section>\n'
)


def pw():
    r = subprocess.run(["security", "find-generic-password", "-s",
                        "theseventhrealm-wp", "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def curl(args, timeout=120):
    base = ["curl", "-s", "-A", UA, "--noproxy", "*", "--compressed", "-L",
            "--max-time", str(timeout)]
    r = subprocess.run(base + args, capture_output=True, text=True)
    return r.stdout


def fetch_raw():
    auth = ["-u", "MollyBot_No.2:" + pw(), "-H", "Accept: application/json"]
    out = curl(auth + [API + "?context=edit"], timeout=90)
    try:
        return json.loads(out)["content"]["raw"]
    except Exception:
        sys.exit("[stop] 取线上原文失败（响应非 JSON）：" + out[:300])


def post(content):
    with open(PAYLOAD, "w", encoding="utf-8") as f:
        f.write(json.dumps({"content": content}, ensure_ascii=False))
    out = curl(["-X", "POST", "-u", "MollyBot_No.2:" + pw(),
                "-H", "Content-Type: application/json",
                "-H", "Accept: application/json",
                "--data-binary", "@" + PAYLOAD, API], timeout=120)
    try:
        j = json.loads(out)
    except Exception:
        print("[fail] 响应非 JSON：" + out[:300])
        return None
    if "id" in j:
        print("[ok] POST id=%s modified=%s 线上 raw=%d 字"
              % (j["id"], j.get("modified"), len(j["content"]["raw"])))
        return j["content"]["raw"]
    print("[fail] " + json.dumps(j, ensure_ascii=False)[:300])
    return None


def purge():
    r = subprocess.run(["/usr/bin/python3", CF_PURGE, "--purge"],
                       capture_output=True, text=True, timeout=150)
    out = (r.stdout or r.stderr or "").strip().replace("\n", " | ")[:200]
    print("[purge] rc=%d %s" % (r.returncode, out))
    return r.returncode == 0


def check_raw(raw, label):
    marks = ["qjcos-hero", "mlb2-46577392", "qj-rhythm", "七境之门", "留个邮箱"]
    missing = [m for m in marks if m not in raw]
    print("[%s] raw=%d 字 / 关键标记缺失=%s / 入口链接数=%d"
          % (label, len(raw), missing or "无", raw.count(LINK)))
    return not missing


def check_front():
    html = curl(["-H", "Accept: text/html", SITE], timeout=150)
    n = html.count(LINK)
    # 新增块附近有没有空段落
    i = html.find(LINK)
    near = html[max(0, i - 700):i + 400] if i >= 0 else ""
    empty_p = len(re.findall(r"<p[^>]*>\s*(?:<br\s*/?>\s*)*</p>", near))
    marks = [m for m in ["qjcos-hero", "mlb2-46577392", "qj-rhythm"] if m in html]
    print("[front] HTML=%d 字节 / 入口链接=%d / 附近空<p>=%d / 关键标记=%d"
          % (len(html), n, empty_p, len(marks)))
    return n == 1 and empty_p == 0 and len(marks) == 3


def build():
    raw = fetch_raw()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(BACKUP):
        with open(BACKUP, "w", encoding="utf-8") as f:
            f.write(raw)
        print("[backup] 原文已落盘：" + BACKUP)
    if not check_raw(raw, "线上原文"):
        sys.exit("[stop] 线上原文关键标记异常，不动线上")
    if LINK in raw:
        sys.exit("[stop] 首页已含入口链接（幂等保护），未改线上")
    if raw.count(ANCHOR) != 1:
        sys.exit("[stop] 锚点 <style id=\"qj-rhythm\"> 不唯一，未改线上")
    new = raw.replace(ANCHOR, BLOCK + ANCHOR, 1)
    print("[build] %d -> %d 字 (+%d)，新增块 %d 字节 / 内部空行=%d"
          % (len(raw), len(new), len(new) - len(raw), len(BLOCK),
             len(re.findall(r"\n\s*\n", BLOCK))))
    with open(AFTER, "w", encoding="utf-8") as f:
        f.write(new)
    return raw, new


def rollback():
    if not os.path.exists(BACKUP):
        sys.exit("[stop] 备份不存在，无法回滚")
    raw = open(BACKUP, encoding="utf-8").read()
    print("[rollback] 备份原文 %d 字" % len(raw))
    if post(raw) is None:
        sys.exit("[stop] 回滚 POST 失败，需人工处理（不重试）")
    purge()
    print("[rollback] 完成；线上入口链接数应为 0")


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        rollback()
        sys.exit(0)
    raw, new = build()
    if "--dry" in sys.argv:
        print("[dry] 未访问写接口，待发布正文已存：" + AFTER)
        sys.exit(0)
    live = post(new)
    if live is None:
        sys.exit("[stop] 发布失败，线上大概率未变；不重试、不排障，请人工核实")
    if live != new:
        print("[warn] 线上 raw 与本地待发布正文不一致 → 自动回滚（降级，不排障）")
        rollback()
        sys.exit("[stop] 已回滚，改动未保留")
    print("[ok] 线上 raw 逐字一致")
    purge()
    ok = check_front()
    print("[result] %s" % ("✅ 入口已生效" if ok else "⚠ 前端复核未通过，请用 --rollback 回滚"))
