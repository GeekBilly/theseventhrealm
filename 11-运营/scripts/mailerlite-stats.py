#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · MailerLite 订阅数与新增采集

【为什么要有这个】
  名单是 Y1 唯一的瓶颈（「邮箱 500，至今 0」写在规划里）。订阅数变化不进工作台，
  就只能靠人去后台点开看 —— 中午来的订阅者，晚上才发现。本脚本把这件事变成
  台账里的一行数字，随刷新链自动更新。

【隐私纪律】（沿用 10-09 入库时定的红线）
  · **只存数量与时间，绝不落邮箱明文**。本脚本产出的 csv 与 json 里没有一个
    邮箱地址、没有一个域名 —— 要看是谁，去 MailerLite 后台看。
  · 钥匙串存 token，不落盘、不进 Git（同 cf-analytics.py 的做法）。

【两种 API 自动兼容】
  新版（当前账号用 groot 表单，属新版）：connect.mailerlite.com/api/  · Bearer
  Classic 老账号：api.mailerlite.com/api/v2/  · X-MailerLite-ApiKey
  `check` 会依次探测，把能通的记进 json 的 kind 字段，之后就固定走它不用再猜。

用法：
  python3 mailerlite-stats.py check     # 自检：钥匙串有没有 key、哪个端点能通（先跑这个）
  python3 mailerlite-stats.py collect   # 取数并落盘（并入刷新链，随每轮刷新跑）
  python3 mailerlite-stats.py show      # 打印当前状态（人读）
  python3 mailerlite-stats.py json      # 打印原始快照（调试）

凭据（首次只需做一次）：
  security add-generic-password -a theseventhrealm -s mailerlite -U -w "<API Token>"
  token 在 MailerLite 后台 → Integrations → Developer API → Generate new token
  （免费版给读权限，够用；发信类接口免费版不给，本脚本也用不到）
"""
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, date, timedelta

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
CSV_PATH = os.path.join(BASE, "11-运营/data/订阅数据.csv")
JSON_PATH = os.path.join(BASE, "11-运营/data/订阅-latest.json")

KEYCHAIN = ("mailerlite", "theseventhrealm")

NEW_BASE = "https://connect.mailerlite.com/api"
CLASSIC_BASE = "https://api.mailerlite.com/api/v2"

# 拉最近多少条订阅者来统计「每日新增」与「最近一次订阅时间」。
# 免费版上限 250 人，100 条足够覆盖近期；超出部分只影响直方图尾部，不影响总数。
RECENT_LIMIT = 100
DAILY_DAYS = 14


def get_token():
    r = subprocess.run(
        ["security", "find-generic-password", "-a", KEYCHAIN[1], "-s", KEYCHAIN[0], "-w"],
        capture_output=True, text=True)
    return r.stdout.strip()


def api(path, token, kind, timeout=25):
    """调一次 API，返回 parsed JSON；失败返回 {}（不抛，交给上层判断）。"""
    if kind == "new":
        url = NEW_BASE + path
        auth = ["-H", f"Authorization: Bearer {token}"]
    else:
        url = CLASSIC_BASE + path
        auth = ["-H", f"X-MailerLite-ApiKey: {token}"]
    cmd = ["curl", "-s", "--max-time", str(timeout),
           "-H", "Accept: application/json"] + auth + [url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    except Exception:
        return {}
    try:
        return json.loads(r.stdout or "{}")
    except Exception:
        return {}


def _subs_time(s):
    """从不同版本的字段里取订阅时间，取不到返回 None。"""
    for k in ("created_at", "subscribed_at", "date_subscribe", "date_created"):
        v = s.get(k)
        if isinstance(v, str) and v[:4].isdigit():
            return v
    return None


def _status(s):
    """Classic 用 type 字段（active/unconfirmed/bounced/junk），新版用 status。"""
    v = s.get("status")
    if v is None:
        v = s.get("type")
    return str(v).lower() if v else "unknown"


def fetch_new(token):
    """新版 API。总数靠 limit=0（文档口径返回 {total:N}），兼容 meta.total。"""
    j = api("/subscribers?limit=0", token, "new")
    total = None
    if isinstance(j, dict):
        if isinstance(j.get("total"), int):
            total = j["total"]
        elif isinstance(j.get("meta"), dict) and isinstance(j["meta"].get("total"), int):
            total = j["meta"]["total"]
    j2 = api(f"/subscribers?limit={RECENT_LIMIT}", token, "new")
    subs = j2.get("data", []) if isinstance(j2, dict) else []
    if not isinstance(subs, list):
        subs = []
    j3 = api("/groups?limit=100", token, "new")
    groups = j3.get("data", []) if isinstance(j3, dict) else []
    if not isinstance(groups, list):
        groups = []
    return {"total": total, "subs": subs, "groups": groups}


def fetch_classic(token):
    """Classic v2：返回裸数组，总数就是长度（免费版 250 上限，一次拉完）。"""
    j = api(f"/subscribers?limit=1000", token, "classic")
    subs = j if isinstance(j, list) else []
    j3 = api("/groups?limit=100", token, "classic")
    groups = j3 if isinstance(j3, list) else []
    return {"total": len(subs), "subs": subs, "groups": groups}


def detect(token):
    """依次试新版、Classic，返回第一个真的拿到数据的结果。"""
    for kind, fn in (("new", fetch_new), ("classic", fetch_classic)):
        r = fn(token)
        if r.get("total"):
            r["kind"] = kind
            return r
        # 总数 0 也可能是真的没人（新账号），用 groups 能否取到来判定端点通不通
        if r.get("groups"):
            r["kind"] = kind
            r["total"] = r.get("total") or 0
            return r
    return {"ok": False, "error": "两个端点都没拿到数据（token 无效？账号类型不匹配？）"}


def summarize(raw):
    """把原始订阅者列表压成只含数量与时间的快照 —— 邮箱一个都不留。"""
    subs = raw.get("subs", [])
    total = raw.get("total")
    st = {}
    for s in subs:
        k = _status(s)
        st[k] = st.get(k, 0) + 1

    daily = {}
    last_at = None
    for s in subs:
        t = _subs_time(s)
        if not t:
            continue
        d = t[:10]
        daily[d] = daily.get(d, 0) + 1
        if last_at is None or t > last_at:
            last_at = t
    today = date.today().isoformat()
    new_today = daily.get(today, 0)
    new_7d = sum(v for d, v in daily.items()
                 if d >= (date.today() - timedelta(days=6)).isoformat())

    series = []
    for i in range(DAILY_DAYS - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        series.append({"date": d, "n": daily.get(d, 0)})

    groups = []
    for g in raw.get("groups", [])[:20]:
        if not isinstance(g, dict):
            continue
        name = g.get("name") or "（未命名分组）"
        cnt = g.get("active_count", g.get("total", g.get("count")))
        if cnt is None:
            cnt = g.get("active", 0)
        groups.append({"name": name, "count": cnt})
    groups.sort(key=lambda x: (x["count"] is None, -(x["count"] or 0)))

    return {
        "ok": True,
        "kind": raw.get("kind"),
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": total,
        "status": st,
        "active": st.get("active", 0),
        "unconfirmed": st.get("unconfirmed", 0),
        "new_today": new_today,
        "new_7d": new_7d,
        "last_subscribe_at": (last_at or "")[:16].replace("T", " ") or None,
        "daily": series,
        "groups": groups,
        "_note": "只含数量与时间，不含任何邮箱地址；要看是谁去 MailerLite 后台。",
    }


def upsert_csv(snap):
    """按日期 upsert：同一天多次采集只留最新一行，历史每天一行。"""
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    rows = []
    fieldnames = ["date", "total", "active", "unconfirmed", "new_today", "new_7d",
                  "last_subscribe_at", "collected_at"]
    if os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except Exception:
            rows = []
    today = date.today().isoformat()
    row = {
        "date": today,
        "total": snap.get("total", ""),
        "active": snap.get("active", ""),
        "unconfirmed": snap.get("unconfirmed", ""),
        "new_today": snap.get("new_today", ""),
        "new_7d": snap.get("new_7d", ""),
        "last_subscribe_at": snap.get("last_subscribe_at") or "",
        "collected_at": snap.get("collected_at", ""),
    }
    rows = [r for r in rows if r.get("date") != today]
    rows.append(row)
    rows.sort(key=lambda r: r.get("date") or "")
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def prev_total():
    """上一次采集的总数（用于算 delta）。取 csv 倒数第二行（今天那行即将被覆盖）。"""
    if not os.path.exists(CSV_PATH):
        return None
    try:
        with open(CSV_PATH, encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r.get("date") != date.today().isoformat()]
        if not rows:
            return None
        v = rows[-1].get("total")
        return int(v) if str(v).strip().isdigit() else None
    except Exception:
        return None


def collect():
    token = get_token()
    if not token:
        out = {"ok": False, "error": "钥匙串里没有 MailerLite token"}
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("❌ 钥匙串里没有 MailerLite token，先执行：")
        print('   security add-generic-password -a theseventhrealm -s mailerlite -U -w "<Token>"')
        return 1
    raw = detect(token)
    if not raw.get("total") and not raw.get("groups"):
        out = {"ok": False, "error": raw.get("error", "未取到数据")}
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("❌ " + out["error"])
        return 1
    snap = summarize(raw)
    p = prev_total()
    snap["prev_total"] = p
    snap["delta"] = (snap["total"] - p) if (p is not None and snap["total"] is not None) else None
    upsert_csv(snap)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    d = snap["delta"]
    print(f"✅ 订阅 {snap['total']} 人"
          + (f"（较上次 {d:+d}）" if d else "")
          + f" · 今日 +{snap['new_today']} · 最近一次 {snap['last_subscribe_at'] or '—'}")
    return 0


def show():
    if not os.path.exists(JSON_PATH):
        print("尚无快照，先跑 collect")
        return 1
    s = json.load(open(JSON_PATH, encoding="utf-8"))
    if not s.get("ok"):
        print("❌ " + s.get("error", "取数失败"))
        return 1
    print(f"采集于 {s.get('collected_at')}　端点 {s.get('kind')}")
    print(f"  总数      {s.get('total')}"
          + (f"（较上次 {s['delta']:+d}）" if s.get("delta") is not None else ""))
    print(f"  已确认    {s.get('active')}　未确认 {s.get('unconfirmed')}")
    print(f"  今日新增  {s.get('new_today')}　近 7 日 {s.get('new_7d')}")
    print(f"  最近一次  {s.get('last_subscribe_at') or '—'}")
    if s.get("groups"):
        print("  分组：")
        for g in s["groups"]:
            print(f"    {g['name']}　{g['count']}")
    return 0


def check():
    token = get_token()
    if not token:
        print("❌ 钥匙串里没有 token。先执行：")
        print('   security add-generic-password -a theseventhrealm -s mailerlite -U -w "<Token>"')
        return 1
    print(f"✅ 钥匙串读到了 token（长度 {len(token)}）")
    for kind, fn in (("new", fetch_new), ("classic", fetch_classic)):
        r = fn(token)
        ok = bool(r.get("total")) or bool(r.get("groups"))
        print(f"  {kind:8s} {'✅ 通' if ok else '— 不通'}　"
              f"total={r.get('total')}　groups={len(r.get('groups') or [])}")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "collect":
        sys.exit(collect())
    if cmd == "show":
        sys.exit(show())
    if cmd == "json":
        print(open(JSON_PATH, encoding="utf-8").read() if os.path.exists(JSON_PATH) else "{}")
        sys.exit(0)
    if cmd == "check":
        sys.exit(check())
    print(__doc__)
    sys.exit(0)
