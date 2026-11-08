#!/usr/bin/env python3
"""把 /memory-token/（页面 729）的购买路径改成「现阶段可兑现」的说法。

REQ-2026-11-08-03。顺带修复上一轮从藏品页搬来的半块 MailerLite 表单：
  ① 成功文案误写「32 张壁纸」 ② 容器缺 ml-subscribe-form-46577392 ⇒ 成功态切不出来
  ③ loading 按钮混入 </p> ＋ 末尾多 3 个孤立 </div>

用法：
    python3 deploy-lp-buy-path.py --dry       # 只生成待发布正文，不碰线上
    python3 deploy-lp-buy-path.py             # 发布 + 清 CDN + 复核
    python3 deploy-lp-buy-path.py --rollback  # 备份原文回滚 + 清 CDN

铁律：定点替换不整篇重排；新段内部无空行；POST 只传 content；
      发完必清 CDN 再复核；所有 curl 带浏览器 UA + --noproxy '*'；失败即回滚，不重试。
"""
import json
import os
import re
import subprocess
import sys

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
BACKUP_DIR = os.path.join(BASE, "11-运营", "上线备份")
BACKUP = os.path.join(BACKUP_DIR, "page729-raw-before-buy-path-20261108.html")
AFTER = os.path.join(BACKUP_DIR, "page729-raw-after-buy-path-20261108.html")
SRC_BAK = os.path.join(BACKUP_DIR, "page729-src-landing-before-20261108.html")
PUB_BAK = os.path.join(BACKUP_DIR, "page729-pub-before-20261108.html")
SRC = os.path.join(BASE, "07-课程", "记忆体改造工具包", "landing.html")
PUB = os.path.join(BASE, "03-页面", "memory-token.html")
PAYLOAD = "/tmp/qj_page729_buy_path_payload.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
API = "https://theseventhrealm.com/wp-json/wp/v2/pages/729"
PAGE = "https://theseventhrealm.com/memory-token/"
CF_PURGE = os.path.join(BASE, "11-运营", "scripts", "cf-cache-rules.py")

NEW_BUY = """<h2 id="buy">怎么拿到 · 现在到哪一步</h2>
<p><strong>目前还没开卖。</strong>两个技能都在 WorkBuddy 开放平台的审核与发布流程里，淘宝店的两档商品也还没上架。这一页现在不收钱，也不让你去搜一个暂时搜不到的名字。</p>
<p><strong>现在能做的两件事</strong>：① <a href="#free">先读免费长文</a>——三个数字和出处都摊开给你看，看完自己就能判断有没有必要买；② 在下面留个邮箱，<strong>开售或更新时我发一封邮件通知你，不发别的</strong>。</p>
<p><strong>开售后</strong>：WorkBuddy 客户端技能市场可搜「<strong>谁动了我的Token</strong>」（¥39 一次买断，装了就能用，不需要配环境），另有免费的「记忆体检（免费版）」可以先试一次体检；淘宝店「第七境」会上自检版 / 体检版两档。届时我会把实际可搜的名字和链接补到这一页。</p>
<div class="sr-mt-signup ml-subscribe-form-46577392">
<p><strong>开售通知</strong>：留下邮箱，开售或更新时我通知你一次，不发别的。</p>
<div class="ml-form-embedBody ml-form-embedBodyDefault row-form">
<form class="ml-block-form" action="https://assets.mailerlite.com/jsonp/2674672/forms/200094094575273632/subscribe" data-code="" method="post" target="_blank">
<div class="ml-form-formContent">
<div class="ml-form-fieldRow ml-last-item">
<div class="ml-field-group ml-field-email ml-validate-email ml-validate-required"><input aria-label="email" aria-required="true" type="email" class="form-control" data-inputmask="" name="fields[email]" placeholder="你的邮箱地址" autocomplete="email"></div>
</div>
</div>
<div class="ml-form-embedPermissions">
<div class="ml-form-embedPermissionsContent default privacy-policy">
<p><span><a href="https://theseventhrealm.com/privacy/">隐私政策</a></span></p>
</div>
</div>
<div class="ml-form-hidden"><input type="hidden" name="ml-submit" value="1"><input type="hidden" name="anticsrf" value="true"></div>
<div class="ml-form-embedSubmit"><button type="submit" class="primary">留邮箱</button><button disabled="disabled" style="display:none" type="button" class="loading"><div class="ml-form-embedSubmitLoad"></div><span class="sr-only">Loading&#8230;</span></button></div>
</form>
</div>
<div class="ml-form-successBody row-success" style="display:none">
<div class="ml-form-successContent">
<h4>已留邮箱</h4>
<p>开售或更新时，我会往这个邮箱发一封通知，不发别的。没需要了随时可以退订。<br />有问题写信到 <a href="mailto:hello@theseventhrealm.com" style="color:#b03826">hello@theseventhrealm.com</a>。</p>
</div>
</div>
<div class="ml-form-scripts"><script>function ml_webform_success_46577392(){var w=document.querySelector('.ml-subscribe-form-46577392');if(!w)return;var s=w.querySelector('.row-success'),f=w.querySelector('.row-form');if(s)s.style.display='';if(f)f.style.display='none';}</script><script src="https://groot.mailerlite.com/js/w/webforms.min.js?v83147fa8ce2d95cb73ece7f28b469519" type="text/javascript"></script><script>fetch("https://assets.mailerlite.com/jsonp/2674672/forms/200094094575273632/takel")</script></div>
</div>"""

REPLACES = [
    ('<p><a class="cta" href="#buy">怎么买</a><a class="cta minor" href="#free">先免费看方法</a></p>',
     '<p><a class="cta" href="#buy">现在怎么拿到</a><a class="cta minor" href="#free">先免费看方法</a></p>'),
    ('<h2>三档，按需要选</h2>', '<h2>计划中的三档（尚未开售）</h2>'),
]


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
    """对任一底稿（线上 raw 或本地源 landing.html）做同样的三处定点替换。"""
    if s.count('<h2 id="buy">') != 1 or s.count('<h2 id="free">') != 1:
        sys.exit("[stop] [%s] buy/free 锚点不唯一" % label)
    a, b = s.find('<h2 id="buy">'), s.find('<h2 id="free">')
    old = s[a:b]
    tail_nl = len(old) - len(old.rstrip("\n"))
    s = s[:a] + NEW_BUY.rstrip("\n") + "\n" * tail_nl + s[b:]
    for o, n in REPLACES:
        if s.count(o) != 1:
            sys.exit("[stop] [%s] 替换锚点出现 %d 次：%s" % (label, s.count(o), o[:60]))
        s = s.replace(o, n, 1)
    return s


def check_block():
    opens = len(re.findall(r"<div\b", NEW_BUY))
    closes = NEW_BUY.count("</div>")
    blanks = len(re.findall(r"\n\s*\n", NEW_BUY))
    print("[block] 新购买段 %d 字节 / <div>=%d </div>=%d / 内部空行=%d"
          % (len(NEW_BUY), opens, closes, blanks))
    return opens == closes and blanks == 0


def check_front():
    html = curl(["-H", "Accept: text/html", PAGE], timeout=150)
    good = ["目前还没开卖", "现在能做的两件事", "开售通知", "已留邮箱",
            "ml-subscribe-form-46577392", "webforms.min.js",
            "15,682", "3,398", "4,014", "hello@theseventhrealm.com"]
    bad = ["两档都在", "32 张壁纸", "技能市场搜", "方式一 · 淘宝"]
    miss = [x for x in good if x not in html]
    left = [x for x in bad if x in html]
    i = html.find("目前还没开卖")
    near = html[max(0, i - 200):i + 2600] if i >= 0 else ""
    empty_p = len(re.findall(r"<p[^>]*>\s*(?:<br\s*/?>\s*)*</p>", near))
    print("[front] HTML=%d 字节 / 应有缺失=%s / 旧文案残留=%s / 新增段空<p>=%d"
          % (len(html), miss or "无", left or "无", empty_p))
    return not miss and not left and empty_p == 0


def rollback():
    raw = open(BACKUP, encoding="utf-8").read()
    print("[rollback] 备份原文 %d 字" % len(raw))
    if post(raw) is None:
        sys.exit("[stop] 回滚 POST 失败，需人工处理（不重试）")
    for bak, dst, label in [(PUB_BAK, PUB, "发布稿"), (SRC_BAK, SRC, "源文件")]:
        if os.path.exists(bak):
            open(dst, "w", encoding="utf-8").write(open(bak, encoding="utf-8").read())
            print("[rollback] %s已恢复：%s" % (label, os.path.basename(dst)))
    purge()
    print("[rollback] 完成；线上应恢复旧购买路径文案")


if __name__ == "__main__":
    if "--rollback" in sys.argv:
        rollback()
        sys.exit(0)
    if not check_block():
        sys.exit("[stop] 新表单块结构体检未过，不动线上")
    raw = fetch_raw()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(BACKUP):
        open(BACKUP, "w", encoding="utf-8").write(raw)
        print("[backup] 原文已落盘：" + BACKUP)
    if "目前还没开卖" in raw:
        sys.exit("[stop] 线上已是新版（幂等保护），未改线上")
    new = transform(raw, "线上 raw")
    # 先验证本地源也能完成同样的替换，避免「线上改了、源没同步」的中间态
    src_now = open(SRC, encoding="utf-8").read()
    pub_now = open(PUB, encoding="utf-8").read()
    transform(src_now, "本地源预检")
    print("[build] %d -> %d 字 (%+d) / 本地源预检通过" % (len(raw), len(new), len(new) - len(raw)))
    open(AFTER, "w", encoding="utf-8").write(new)
    if "--dry" in sys.argv:
        print("[dry] 未访问写接口；待发布正文：" + AFTER)
        sys.exit(0)
    if not os.path.exists(SRC_BAK):
        open(SRC_BAK, "w", encoding="utf-8").write(src_now)
    if not os.path.exists(PUB_BAK):
        open(PUB_BAK, "w", encoding="utf-8").write(pub_now)
    live = post(new)
    if live is None:
        sys.exit("[stop] 发布失败，线上大概率未变；不重试、不排障")
    if live != new:
        print("[warn] 线上 raw 与本地待发布正文不一致 → 自动回滚（降级）")
        rollback()
        sys.exit("[stop] 已回滚，改动未保留")
    print("[ok] 线上 raw 逐字一致")
    # 同步本地两份，避免下次重发把旧文案带回去
    open(PUB, "w", encoding="utf-8").write(new)
    src = open(SRC, encoding="utf-8").read()
    open(SRC, "w", encoding="utf-8").write(transform(src, "本地源"))
    print("[sync] 发布稿与源 landing.html 已同步")
    purge()
    ok = check_front()
    print("[result] %s" % ("✅ 购买路径已生效" if ok else "⚠ 前端复核未通过，可用 --rollback 回滚"))
