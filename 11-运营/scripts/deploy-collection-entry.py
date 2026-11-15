#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REQ-2026-11-15-02 · 给藏品页（页面 134 /collection/）补第二条 /memory-token/ 入口。

照抄 deploy-lp-entry.py（首页第一条入口）已验证的写法：
在正文末尾 <style id="qj-rhythm"> 之前插一个单行 <section> 文字链，全内联样式。

🔴 本页本地稿比线上少 323 字 ⇒ 绝不能拿本地稿发。以线上 content.raw 为底稿，
   改完后用线上正文覆盖回本地（覆盖前先落盘 .bak），顺带修掉这处倒退。

用法：
    python3 deploy-collection-entry.py --dry       # 只生成待发布正文，不写线上
    python3 deploy-collection-entry.py             # 发布 + 清 CDN + 复核 + 同步本地
    python3 deploy-collection-entry.py --rollback  # 原文回滚 + 恢复本地稿 + 清 CDN

铁律：最小增量插入、新块单行且内部无空行、不整篇跑 wp_safe；
      qj-rhythm 必须保持正文最后一块；POST 只传 content；
      所有 curl 带浏览器 UA + --noproxy '*'；清 CDN 在复核之前；失败即回滚，不重试、不排障。
"""
import json
import os
import re
import subprocess
import sys

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
BACKUP_DIR = os.path.join(BASE, "11-运营", "上线备份")
BACKUP = os.path.join(BACKUP_DIR, "page134-raw-before-entry-20261115.html")
AFTER = os.path.join(BACKUP_DIR, "page134-raw-after-entry-20261115.html")
PUB_BAK = os.path.join(BACKUP_DIR, "page134-collection-before-20261115.html")
PUB = os.path.join(BASE, "03-页面", "collection.html")
PAYLOAD = "/tmp/qj_page134_entry_payload.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
API = "https://theseventhrealm.com/wp-json/wp/v2/pages/134"
PAGE = "https://theseventhrealm.com/collection/"
CF_PURGE = os.path.join(BASE, "11-运营", "scripts", "cf-cache-rules.py")

ANCHOR = '<style id="qj-rhythm">'
LINK = 'href="/memory-token/"'
# 单行、内部无空行；全内联样式（块在 .sr-collection 之外，不能依赖容器继承）
BLOCK = (
    '<section><p style="max-width:580px;margin:0 auto;line-height:2.1;'
    'color:#8c8578;letter-spacing:.06em;font-size:14px;text-align:center">'
    '另作 · 做这套藏品时，顺手把一个不相干的问题查明白了：'
    'AI 长项目为什么越用越贵、越用越笨。方法全文免费，数字与出处逐条可查，'
    '工具在你自己机器上只读不写。'
    '<a ' + LINK + ' style="color:#b03826;text-decoration:none;'
    'border-bottom:1px solid #ded7c8;padding-bottom:3px">'
    '谁动了我的Token →</a></p></section>\n'
)


def pw():
    return subprocess.run(["security", "find-generic-password", "-s",
                           "theseventhrealm-wp", "-w"],
                          capture_output=True, text=True).stdout.strip()


def curl(args, timeout=120):
    base = ["curl", "-s", "-A", UA, "--noproxy", "*", "--compressed", "-L",
            "--max-time", str(timeout)]
    return subprocess.run(base + args, capture_output=True, text=True).stdout


def fetch_raw():
    out = curl(["-u", "MollyBot_No.2:" + pw(), "-H", "Accept: application/json",
                API + "?context=edit"], timeout=90)
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


def transform(s, label):
    if s.count(ANCHOR) != 1:
        sys.exit("[stop] [%s] 锚点 <style id=qj-rhythm> 出现 %d 次（应为 1）"
                 % (label, s.count(ANCHOR)))
    if LINK in s:
        sys.exit("[stop] [%s] 已有 /memory-token/ 链接（幂等保护）" % label)
    return s.replace(ANCHOR, BLOCK + ANCHOR, 1)


def check_block():
    body = BLOCK.rstrip("\n")
    blanks = len(re.findall(r"\n\s*\n", BLOCK))
    sec_o, sec_c = body.count("<section"), body.count("</section>")
    div_o, div_c = len(re.findall(r"<div\b", body)), body.count("</div>")
    ok = ("\n" not in body and blanks == 0 and sec_o == sec_c == 1
          and div_o == div_c and "class=\"reveal\"" not in body
          and LINK in body and ANCHOR not in body)
    print("[block] 新块 %d 字节 / 单行=%s / 内部空行=%d / section=%d:%d / div=%d:%d"
          % (len(BLOCK), "\n" not in body, blanks, sec_o, sec_c, div_o, div_c))
    if not ok:
        sys.exit("[stop] 新块结构体检未过，不动线上")
    return True


def check_front():
    html = curl(["-H", "Accept: text/html", PAGE], timeout=150)
    good = ["另作 · 做这套藏品时", "谁动了我的Token →", LINK,
            "单朝 ¥12", "232 张", "怎么拿到", "webforms.min.js",
            "ml-subscribe-form", "SIL Open Font License"]
    miss = [x for x in good if x not in html]
    i = html.find("另作 · 做这套藏品时")
    near = html[max(0, i - 300):i + 1200] if i >= 0 else ""
    empty_p = len(re.findall(r"<p[^>]*>\s*(?:<br\s*/?>\s*)*</p>", near))
    links = html.count(LINK)
    print("[front] HTML=%d 字节 / 应有缺失=%s / 入口链接=%d（应为 1）/ 新增段空<p>=%d"
          % (len(html), miss or "无", links, empty_p))
    return not miss and links == 1 and empty_p == 0


def rollback():
    raw = open(BACKUP, encoding="utf-8").read()
    print("[rollback] 备份原文 %d 字" % len(raw))
    if post(raw) is None:
        sys.exit("[stop] 回滚 POST 失败，需人工处理（不重试）")
    if os.path.exists(PUB_BAK):
        open(PUB, "w", encoding="utf-8").write(open(PUB_BAK, encoding="utf-8").read())
        print("[rollback] 本地稿已恢复：" + os.path.basename(PUB))
    purge()
    print("[rollback] 完成；线上应恢复无入口的原文")


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        rollback()
        sys.exit(0)

    check_block()
    raw = fetch_raw()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if LINK in raw:
        sys.exit("[stop] 线上已有该入口（幂等保护），未改线上")

    pub_now = open(PUB, encoding="utf-8").read()
    print("[local] 本地稿 %d 字 / 线上 %d 字 / 差 %+d（本地少＝倒退，以线上为准）"
          % (len(pub_now), len(raw), len(pub_now) - len(raw)))

    new = transform(raw, "线上 raw")
    # qj-rhythm 必须仍在正文最后一块
    if new.rfind(ANCHOR) < new.rfind("</section>"):
        sys.exit("[stop] qj-rhythm 不再是正文最后一块，不动线上")
    print("[build] %d -> %d 字 (%+d)" % (len(raw), len(new), len(new) - len(raw)))

    if not os.path.exists(BACKUP):
        open(BACKUP, "w", encoding="utf-8").write(raw)
        print("[backup] 线上原文已落盘：" + BACKUP)
    if not os.path.exists(PUB_BAK):
        open(PUB_BAK, "w", encoding="utf-8").write(pub_now)
        print("[backup] 本地原稿已落盘：" + PUB_BAK)
    open(AFTER, "w", encoding="utf-8").write(new)
    if "--dry" in sys.argv:
        print("[dry] 未访问写接口；待发布正文：" + AFTER)
        sys.exit(0)

    live = post(new)
    if live is None:
        sys.exit("[stop] 发布失败，线上大概率未变；不重试、不排障")
    if live != new:
        print("[warn] 线上 raw 与本地待发布正文不一致 → 自动回滚（降级）")
        rollback()
        sys.exit("[stop] 已回滚，改动未保留")
    print("[ok] 线上 raw 逐字一致")

    # 用线上正文覆盖本地稿：修掉「本地少 323 字」的倒退（原稿已备份）
    open(PUB, "w", encoding="utf-8").write(new)
    print("[sync] 本地稿已用线上正文覆盖（%d -> %d 字）" % (len(pub_now), len(new)))

    purge()   # 必须在前端复核之前
    ok = check_front()
    lp = curl(["-H", "Accept: text/html",
               "https://theseventhrealm.com/memory-token/"], timeout=150)
    lp_ok = "顺带问一句" in lp and "fields[price_intent]" in lp
    print("[lp] /memory-token/ %d 字节 / 意向单选仍在=%s" % (len(lp), lp_ok))
    print("[result] %s" % ("✅ 第二条入口已生效" if ok and lp_ok
                           else "⚠ 复核未通过，可用 --rollback 回滚"))
