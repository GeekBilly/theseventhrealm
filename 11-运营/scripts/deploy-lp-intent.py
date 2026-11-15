#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REQ-2026-11-15-01 · /memory-token/（页面 729）零风险意向收集。

在现有 MailerLite 表单里插一道**非必填**的「愿意付多少」四选一。
选中的值随表单一起提交到 MailerLite 的 price_intent 自定义字段。

顺序（保证「字段没建好 → 页面一个字不改」）：
  ① GET  /api/fields        字段已存在则复用（幂等）
  ② POST /api/fields        唯一一次机会，失败即降级：不重试、不排障
  ③ GET  /api/fields        回读确认 key
  ④ 拉线上 raw → 备份 → 唯一锚点最小增量插入 → 本地源预检
  ⑤ POST {"content":...} → 逐字比对，不一致自动回滚
  ⑥ purge CDN → 前端复核 → 同步两份本地稿

用法：
    python3 deploy-lp-intent.py --dry       # 纯读：只生成待发布正文，不建字段、不写线上
    python3 deploy-lp-intent.py             # 正式执行
    python3 deploy-lp-intent.py --rollback  # 恢复线上与两份本地稿（不删字段）

铁律：新增块单行、内部无空行；不带 ml-validate-required（否则必填校验会挡订阅）；
      POST 只传 content；所有 curl 带浏览器 UA + --noproxy '*'；
      发完必清 CDN 再复核；失败一次即降级，不重试、不排障。
"""
import json
import os
import re
import subprocess
import sys

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
BACKUP_DIR = os.path.join(BASE, "11-运营", "上线备份")
BACKUP = os.path.join(BACKUP_DIR, "page729-raw-before-intent-20261115.html")
AFTER = os.path.join(BACKUP_DIR, "page729-raw-after-intent-20261115.html")
SRC_BAK = os.path.join(BACKUP_DIR, "page729-src-landing-before-intent-20261115.html")
PUB_BAK = os.path.join(BACKUP_DIR, "page729-pub-before-intent-20261115.html")
SRC = os.path.join(BASE, "07-课程", "记忆体改造工具包", "landing.html")
PUB = os.path.join(BASE, "03-页面", "memory-token.html")
PAYLOAD = "/tmp/qj_page729_intent_payload.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
API = "https://theseventhrealm.com/wp-json/wp/v2/pages/729"
PAGE = "https://theseventhrealm.com/memory-token/"
ML_API = "https://connect.mailerlite.com/api"
CF_PURGE = os.path.join(BASE, "11-运营", "scripts", "cf-cache-rules.py")

FIELD_NAME = "Price intent"
FIELD_KEY = "price_intent"

# 单行、内部无空行、div 平衡、不含 ml-validate-required。
# 文案不用任何引号（中文引号铁律），不写「卖/收入/副业」话术，不虚构主体。
LABEL = ('style="display:inline-block;margin:0 14px 6px 0;font-size:14px;'
         'color:#1f1d1a;cursor:pointer"')
RADIO = ('style="margin-right:5px;vertical-align:-1px"')
INTENT_BLOCK = (
    '<div class="ml-form-fieldRow"><div class="ml-field-group">'
    '<div style="margin:0 0 10px;color:#5a554c;font-size:14px;line-height:1.8">'
    '顺带问一句，可以不选，也不影响留邮箱：如果以后把这套做法做成一个装在本机、'
    '只读不写的小工具，哪个价位对你才算合理？现在不收钱，这一题只是帮我判断，不涉及购买。</div>'
    '<label ' + LABEL + '><input type="radio" name="fields[' + FIELD_KEY + ']" value="free" '
    + RADIO + '>只看免费的就够了</label>'
    '<label ' + LABEL + '><input type="radio" name="fields[' + FIELD_KEY + ']" value="lt20" '
    + RADIO + '>最多 ¥19</label>'
    '<label ' + LABEL + '><input type="radio" name="fields[' + FIELD_KEY + ']" value="around39" '
    + RADIO + '>¥39 左右能接受</label>'
    '<label ' + LABEL + '><input type="radio" name="fields[' + FIELD_KEY + ']" value="gt99" '
    + RADIO + '>¥99 以上也愿意</label>'
    '</div></div>'
)

# ml-form-formContent 内、邮箱字段行之后，formContent 闭合之前
ANCHOR = '</div>\n</div>\n<div class="ml-form-embedPermissions">'
ANCHOR_NEW = '</div>\n' + INTENT_BLOCK + '\n</div>\n<div class="ml-form-embedPermissions">'


# ────────────────────────── 通用 curl ──────────────────────────

def curl(args, timeout=120):
    base = ["curl", "-s", "-A", UA, "--noproxy", "*", "--compressed", "-L",
            "--max-time", str(timeout)]
    return subprocess.run(base + args, capture_output=True, text=True).stdout


def pw():
    return subprocess.run(["security", "find-generic-password", "-s",
                           "theseventhrealm-wp", "-w"],
                          capture_output=True, text=True).stdout.strip()


def ml_token():
    return subprocess.run(["security", "find-generic-password", "-a",
                           "theseventhrealm", "-s", "mailerlite", "-w"],
                          capture_output=True, text=True).stdout.strip()


def ml_api(method, path, body=None, timeout=30):
    tok = ml_token()
    if not tok:
        sys.exit("[降级] 钥匙串读不到 MailerLite token；页面未改，不重试、不排障")
    cmd = ["-X", method, "-H", "Accept: application/json",
           "-H", "Authorization: Bearer " + tok]
    if body is not None:
        cmd += ["-H", "Content-Type: application/json",
                "-d", json.dumps(body, ensure_ascii=False)]
    out = curl(cmd + [ML_API + path], timeout=timeout)
    try:
        return json.loads(out)
    except Exception:
        return {"_raw": out[:400]}


# ────────────────────────── MailerLite 字段 ──────────────────────────

def field_exists():
    j = ml_api("GET", "/fields")
    data = j.get("data") if isinstance(j, dict) else None
    if not isinstance(data, list):
        sys.exit("[降级] GET /fields 未返回字段列表；页面未改，不重试、不排障"
                 + ("：" + str(j.get("_raw", "")) if isinstance(j, dict) else ""))
    hit = [f for f in data if isinstance(f, dict) and f.get("key") == FIELD_KEY]
    print("[field] 现有字段 %d 个 / %s %s"
          % (len(data), FIELD_KEY, "已存在" if hit else "不存在"))
    return hit[0] if hit else None


def ensure_field(dry=False):
    """字段先建、页面后改。POST 只有一次机会，失败即整体降级。"""
    f = field_exists()
    if f:
        print("[field] 复用已有字段 id=%s key=%s type=%s"
              % (f.get("id"), f.get("key"), f.get("type")))
        return f
    if dry:
        print("[dry] 将新建字段 name=%s → key=%s（本次不写）" % (FIELD_NAME, FIELD_KEY))
        return None
    j = ml_api("POST", "/fields", {"name": FIELD_NAME, "type": "text"})
    d = j.get("data") if isinstance(j, dict) else None
    if not isinstance(d, dict) or d.get("key") != FIELD_KEY:
        sys.exit("[降级] 建字段未成功，页面一个字未改。不重试、不排障。\n"
                 "  响应：" + json.dumps(j, ensure_ascii=False)[:400] + "\n"
                 "  手动三步：MailerLite 后台 → Subscribers → Fields → Create field\n"
                 "  名称填 Price intent、类型 Text，建好后重跑本脚本即可自动复用。")
    print("[field] 新建 id=%s key=%s type=%s"
          % (d.get("id"), d.get("key"), d.get("type")))
    if not field_exists():
        sys.exit("[降级] 回读未确认该字段；页面未改，不重试、不排障")
    print("[field] 回读确认 ✅")
    return d


# ────────────────────────── WordPress ──────────────────────────

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


# ────────────────────────── 变换与体检 ──────────────────────────

def transform(s, label):
    if s.count(ANCHOR) != 1:
        sys.exit("[stop] [%s] 插入锚点出现 %d 次（应为 1）" % (label, s.count(ANCHOR)))
    if s.count('fields[' + FIELD_KEY + ']') != 0:
        sys.exit("[stop] [%s] 已含该单选（幂等保护）" % label)
    return s.replace(ANCHOR, ANCHOR_NEW, 1)


def check_block():
    opens = len(re.findall(r"<div\b", INTENT_BLOCK))
    closes = INTENT_BLOCK.count("</div>")
    radios = INTENT_BLOCK.count('type="radio"')
    names = INTENT_BLOCK.count('name="fields[' + FIELD_KEY + ']"')
    blanks = len(re.findall(r"\n\s*\n", INTENT_BLOCK))
    ok = (opens == closes and radios == 4 and names == 4 and blanks == 0
          and "ml-validate-required" not in INTENT_BLOCK and "\n" not in INTENT_BLOCK)
    print("[block] 新块 %d 字节 / <div>=%d </div>=%d / radio=%d / name=%d / "
          "空行=%d / 含必填class=%s / 含换行=%s"
          % (len(INTENT_BLOCK), opens, closes, radios, names, blanks,
             "ml-validate-required" in INTENT_BLOCK, "\n" in INTENT_BLOCK))
    if not ok:
        sys.exit("[stop] 新块结构体检未过，不动线上")
    return True


def check_front():
    html = curl(["-H", "Accept: text/html", PAGE], timeout=150)
    good = ["顺带问一句", "只看免费的就够了", "最多 ¥19", "¥39 左右能接受",
            "¥99 以上也愿意", 'fields[' + FIELD_KEY + ']', "目前还没开卖",
            "现在能做的两件事", "ml-subscribe-form-46577392", "webforms.min.js"]
    bad = ["两档都在", "32 张壁纸", "方式一 · 淘宝"]
    miss = [x for x in good if x not in html]
    left = [x for x in bad if x in html]
    i = html.find("顺带问一句")
    near = html[max(0, i - 400):i + 2400] if i >= 0 else ""
    empty_p = len(re.findall(r"<p[^>]*>\s*(?:<br\s*/?>\s*)*</p>", near))
    req = html.count("ml-validate-required")
    print("[front] HTML=%d 字节 / 应有缺失=%s / 旧文案残留=%s / 新增段空<p>=%d / "
          "ml-validate-required=%d（应为 1）"
          % (len(html), miss or "无", left or "无", empty_p, req))
    return not miss and not left and empty_p == 0 and req == 1


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
    print("[rollback] 页面已还原；MailerLite 的空字段 price_intent 保留（不自动删，避免连带清值）")


# ────────────────────────── 主流程 ──────────────────────────

if __name__ == "__main__":
    dry = "--dry" in sys.argv
    if "--rollback" in sys.argv:
        rollback()
        sys.exit(0)

    check_block()
    raw = fetch_raw()
    os.makedirs(BACKUP_DIR, exist_ok=True)

    if 'fields[' + FIELD_KEY + ']' in raw:
        sys.exit("[stop] 线上已有该单选（幂等保护），未改线上")

    src_now = open(SRC, encoding="utf-8").read()
    pub_now = open(PUB, encoding="utf-8").read()
    transform(src_now, "本地源预检")   # 源稿也必须能完成同样的插入

    new = transform(raw, "线上 raw")
    print("[build] %d -> %d 字 (%+d) / 本地源预检通过" % (len(raw), len(new), len(new) - len(raw)))

    if not os.path.exists(BACKUP):
        open(BACKUP, "w", encoding="utf-8").write(raw)
        print("[backup] 原文已落盘：" + BACKUP)
    open(AFTER, "w", encoding="utf-8").write(new)

    # ①~③ 字段阶段：dry 时纯读，不 POST
    ensure_field(dry=dry)

    if dry:
        print("[dry] 未建字段、未写线上；待发布正文：" + AFTER)
        sys.exit(0)

    if not os.path.exists(SRC_BAK):
        open(SRC_BAK, "w", encoding="utf-8").write(src_now)
    if not os.path.exists(PUB_BAK):
        open(PUB_BAK, "w", encoding="utf-8").write(pub_now)

    # ④⑤ 页面阶段
    live = post(new)
    if live is None:
        sys.exit("[stop] 发布失败，线上大概率未变；不重试、不排障")
    if live != new:
        print("[warn] 线上 raw 与本地待发布正文不一致 → 自动回滚（降级）")
        rollback()
        sys.exit("[stop] 已回滚，改动未保留；空字段保留并已在输出中说明")

    print("[ok] 线上 raw 逐字一致")
    open(PUB, "w", encoding="utf-8").write(new)
    open(SRC, "w", encoding="utf-8").write(transform(src_now, "本地源"))
    print("[sync] 发布稿与源 landing.html 已同步")

    # ⑥ 清缓存必须在复核之前
    purge()
    ok = check_front()
    print("[result] %s" % ("✅ 意向收集已生效" if ok else "⚠ 前端复核未通过，可用 --rollback 回滚"))
