#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CF 安全事件采集（每日跑一次 · 零积分）

为什么必须【每日】采：
    Cloudflare 的 firewallEventsAdaptive 只能回溯 3–4 天。
    漏一天＝永久缺一天（和站点分析采集同一个坑，见 2026-09-30 记录）。

产出：11-运营/data/cf-security.csv
      date,events,challenge,block,bypassed,managed_challenge,
      top_path,top_path_n,top_country,top_country_n,top_ua,top_ua_n,collected_at

凭据：钥匙串 服务名 cf-audit / 账号 theseventhrealm（不出现在任何文件里）

用法：
    python3 cf-security-collect.py            # 采最近 3 天（补漏用，幂等）
    python3 cf-security-collect.py --days 1   # 只采昨天到今天
    python3 cf-security-collect.py --report   # 只读 CSV 出趋势，不采集
"""
import argparse, csv, datetime as dt, json, pathlib, subprocess, sys

BASE = pathlib.Path(__file__).resolve().parents[2]
CSV_PATH = BASE / "11-运营/data/cf-security.csv"
KEYCHAIN = ("cf-audit", "theseventhrealm")
ZONE_NAME = "theseventhrealm.com"
API = "https://api.cloudflare.com/client/v4"

FIELDS = ["date", "events", "challenge", "block", "bypassed", "managed_challenge",
          "top_path", "top_path_n", "top_country", "top_country_n",
          "top_ua", "top_ua_n", "collected_at"]


def token():
    t = subprocess.run(["security", "find-generic-password",
                        "-a", KEYCHAIN[1], "-s", KEYCHAIN[0], "-w"],
                       capture_output=True, text=True)
    tok = t.stdout.strip()
    if not tok:
        sys.exit("  🔴 钥匙串读不到 token（服务名 %s）" % KEYCHAIN[0])
    return tok


def curl(url, tok, data=None):
    cmd = ["curl", "-s", "--max-time", "30", "--noproxy", "*",
           "-H", "Authorization: Bearer " + tok]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-X", "POST", "-d", json.dumps(data)]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"success": False, "raw": r.stdout[:200]}


def zone_id(tok):
    d = curl(f"{API}/zones?name={ZONE_NAME}", tok)
    zs = d.get("result") or []
    if not zs:
        sys.exit("  🔴 拿不到 zone id：" + str(d.get("errors")))
    return zs[0]["id"]


def fetch(tok, zid, day):
    """拉某一天的防火墙事件（UTC 日界）"""
    gte = day.strftime("%Y-%m-%dT00:00:00Z")
    lte = (day + dt.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
    q = ('query{viewer{zones(filter:{zoneTag:"%s"}){'
         'firewallEventsAdaptive(limit:10000, filter:{datetime_geq:"%s", datetime_leq:"%s"}, '
         'orderBy:[datetime_DESC]){action clientCountryName clientRequestPath userAgent}}}}'
         ) % (zid, gte, lte)
    d = curl(f"{API}/graphql", tok, {"query": q})
    if d.get("errors"):
        print("  ⚠️ GraphQL 错误:", [e.get("message") for e in d["errors"]][:2])
        return None
    zs = ((d.get("data") or {}).get("viewer") or {}).get("zones") or []
    return (zs[0] if zs else {}).get("firewallEventsAdaptive") or []


def topk(events, key, k=1):
    from collections import Counter
    c = Counter(str((e or {}).get(key) or "") for e in events)
    c.pop("", None)
    return c.most_common(k)


def collect(days):
    tok = token()
    zid = zone_id(tok)
    today = dt.datetime.now(dt.timezone.utc).date()
    rows = []
    for i in range(days):
        day = today - dt.timedelta(days=i + 1)   # 从昨天往回收，避免采到半天
        ev = fetch(tok, zid, day)
        if ev is None:
            continue
        from collections import Counter
        acts = Counter((e or {}).get("action") or "" for e in ev)
        ch = sum(v for k, v in acts.items() if "challenge" in k)
        bl = sum(v for k, v in acts.items() if k in ("block", "drop", "connection_close"))
        by = sum(v for k, v in acts.items() if "bypass" in k or "solved" in k)
        mc = acts.get("managed_challenge", 0)
        tp = topk(ev, "clientRequestPath")
        tc = topk(ev, "clientCountryName")
        tu = topk(ev, "userAgent")
        rows.append({
            "date": day.isoformat(), "events": len(ev),
            "challenge": ch, "block": bl, "bypassed": by, "managed_challenge": mc,
            "top_path": tp[0][0] if tp else "", "top_path_n": tp[0][1] if tp else 0,
            "top_country": tc[0][0] if tc else "", "top_country_n": tc[0][1] if tc else 0,
            "top_ua": (tu[0][0] or "")[:60] if tu else "", "top_ua_n": tu[0][1] if tu else 0,
            "collected_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        print(f"  {day}  {len(ev):>5} 事件  challenge {ch}  block {bl}  bypass {by}"
              f"  首恶路径 {tp[0][0] if tp else '-'}")
    return rows


def upsert(rows):
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    old = {}
    if CSV_PATH.exists():
        with open(CSV_PATH, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                old[r["date"]] = r
    for r in rows:
        old[r["date"]] = r
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for d in sorted(old):
            w.writerow({k: old[d].get(k, "") for k in FIELDS})
    return len(old)


def report():
    if not CSV_PATH.exists():
        sys.exit("  还没有数据")
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("events")]
    if not rows:
        sys.exit("  数据为空")
    print(f"\n  CF 安全事件 · 共 {len(rows)} 天\n")
    print(f"  {'日期':<12}{'事件':>7}{'挑战':>7}{'拦截':>7}{'放行':>7}  {'首恶路径':<26}{'首恶国家'}")
    for r in rows[-14:]:
        print(f"  {r['date']:<12}{r['events']:>7}{r['challenge']:>7}{r['block']:>7}{r['bypassed']:>7}  "
              f"{r['top_path'][:24]:<26}{r['top_country']}")
    tot = sum(int(r["events"]) for r in rows)
    print(f"\n  合计 {tot} 条事件")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
    else:
        print("── 采集 CF 安全事件 ──")
        rows = collect(a.days)
        n = upsert(rows)
        print(f"  ✅ CSV 现有 {n} 天 → {CSV_PATH.relative_to(BASE)}")
        report()
