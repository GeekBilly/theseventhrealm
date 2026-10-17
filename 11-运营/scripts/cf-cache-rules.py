#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CF 缓存规则配置 —— 让 HTML 进 CDN（解决 cf-cache-status: DYNAMIC 每次回源）

背景（2026-10-17 实测）：
  本机 curl 走透明代理 + 跨境，绝对 TTFB 噪声 ±15s 不可信；
  但「HTML 是否进 CDN」是链路无关的硬指标 —— 现状 0/3 页进 CDN，
  每个访客都要走完「中国 → CF 洛杉矶 → GoDaddy 源站 → 原路返回」。
  favicon（命中 CDN）4.6s vs 首页（回源）10–16s，中间 5–10 秒就是这次往返。

用法：
  python3 cf-cache-rules.py --check     # 只读：权限自检 + 现有规则（零风险，随时可跑）
  python3 cf-cache-rules.py --apply     # 写入两条 Cache Rules（幂等，重复跑会覆盖同名规则集）
  python3 cf-cache-rules.py --purge     # 清空 CF 边缘缓存（改完首页后必须跑）
  python3 cf-cache-rules.py --verify    # 实测首页/子页 cf-cache-status 是否变 HIT

凭据：钥匙串服务名 cf-cache-edit / 账号 theseventhrealm（只读 token 不行，必须带写权限）
  security add-generic-password -a theseventhrealm -s cf-cache-edit -U -w "<TOKEN>"

退出码：0 正常 / 1 业务未达预期 / 2 凭据缺失或无权（不重试，直接告用户）
"""
import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request

ZONE = "1dbeff2d4400e264591b83de7d48a761"
SITE = "theseventhrealm.com"
KEYCHAIN_SVC = "cf-cache-edit"
KEYCHAIN_ACC = "theseventhrealm"
API = "https://api.cloudflare.com/client/v4"
EDGE_TTL = 7200  # 免费版 Edge TTL 下限就是 2h，改不更小
BROWSER_TTL = 14400

# 必须绕过缓存的路径/条件（缓存了会出事：后台、登录态、预览、搜索、REST）
BYPASS_EXPR = (
    '(http.request.uri.path contains "/wp-admin") or '
    '(http.request.uri.path contains "/wp-login.php") or '
    '(http.request.uri.path contains "/wp-json/") or '
    '(http.request.uri.path contains "/wp-cron.php") or '
    '(http.request.uri.path contains "/xmlrpc.php") or '
    '(http.request.uri.query contains "preview=") or '
    '(http.request.uri.query contains "customize_changeset") or '
    '(http.request.uri contains "sitemap") or '
    '(http.cookie contains "wordpress_logged_in") or '
    '(http.cookie contains "wp-postpass") or '
    '(http.cookie contains "comment_author") or '
    '(http.cookie contains "woocommerce_items_in_cart")'
)

RULESET_NAME = "第七境 HTML 缓存（自动配置）"


def token():
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SVC,
             "-a", KEYCHAIN_ACC, "-w"],
            capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def call(method, path, body=None):
    tok = token()
    if not tok:
        print("❌ 钥匙串里没有 cf-cache-edit token。先建一个有写权限的 Token：")
        print("   1) https://dash.cloudflare.com/profile/api-tokens → Create Token")
        print("   2) 权限：Zone | Cache Rules | Edit + Zone | Cache Purge | Purge")
        print("      另加 Zone | Zone Settings | Read（自检用）")
        print("   3) Zone Resources：Include | Specific zone | theseventhrealm.com")
        print(f'   4) security add-generic-password -a {KEYCHAIN_ACC} -s {KEYCHAIN_SVC} -U -w "<TOKEN>"')
        sys.exit(2)
    req = urllib.request.Request(API + path, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=30) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode()), e.code
        except Exception:
            return {}, e.code
    except Exception as e:
        return {}, str(e)


def find_ruleset(phase="http_request_cache_settings"):
    d, err = call("GET", f"/zones/{ZONE}/rulesets")
    if err:
        return None, f"列规则集失败：{err}"
    for r in (d.get("result") or []):
        if r.get("phase") == phase:
            return r, None
    return None, None  # 还没有该 phase 的规则集（正常，首次配置）


def cmd_check():
    tok = token()
    if not tok:
        print("❌ 无 cf-cache-edit token（只读 token 改不了配置）")
        print("   → 建 Token 后存钥匙串，见本文件顶部注释")
        return 2
    d, err = call("GET", "/user/tokens/verify")
    print("token 状态：", (d.get("result") or {}).get("status") if d.get("success") else f"失败 {err}")

    rs, e = find_ruleset()
    if e:
        print("⚠️", e)
        print("   （若报 Authentication error = token 无 Zone 读权限，需换 Token）")
        return 2
    if not rs:
        print("现有 Cache Rules：无（首次配置）")
    else:
        print(f"现有 Cache Rules（{rs['id']}）：{len(rs.get('rules') or [])} 条")
        for r in rs.get("rules") or []:
            act = (r.get("action_parameters") or {})
            print(f"  - {r.get('name')} | cache={act.get('cache')} "
                  f"edge_ttl={(act.get('edge_ttl') or {}).get('mode') or act.get('edge_ttl')}")
    return 0


def cmd_apply():
    rs, e = find_ruleset()
    if e:
        print("⚠️", e)
        return 2

    # 🔴🔴 **顺序必须反过来**：Cache Rules 是「后匹配覆盖前匹配」（last-match-wins），
    #    不是防火墙那种 first-match。2026-10-17 实测：把 bypass 放前面时，
    #    /wp-json/ 照样三次 HIT（被后面的 cache:true 覆盖），等于后台接口被缓存 2 小时。
    #    ⇒ **bypass 必须排最后**，它才能盖掉前面的 cache:true。
    # ⚠️ ruleset API 的**单条 rule 不接受 "name" 字段**（CF 会报 unknown field "name"）；
    #    rule 的显示名一律用 description，name 只有 ruleset 顶层才有。
    rules = [
        {
            "description": "① 缓存 HTML：Cache Everything + Edge TTL 2h",
            "expression": f'(http.host eq "{SITE}")',
            "action": "set_cache_settings",
            "action_parameters": {
                "cache": True,
                "edge_ttl": {"mode": "override_origin", "default": EDGE_TTL},
                "browser_ttl": {"mode": "override_origin", "default": BROWSER_TTL},
                # ⚠️ 免费版只有 cache/edge_ttl/browser_ttl 三个字段可用。
                #    serve_stale → 400 unknown field "disable"
                #    origin_cache_control / respect_strong_etags → 400 not entitled to ...
                #    加回来之前先确认 plan 已升级，否则必被拒。
            },
        },
        {
            "description": "② 绕过：后台/登录/预览/REST/搜索（必须排最后才能盖掉 ①）",
            "expression": BYPASS_EXPR,
            "action": "set_cache_settings",
            "action_parameters": {"cache": False},
        },
    ]
    # 规则按顺序匹配，① 命中即 bypass，不会落到 ②
    # ⚠️ ruleset 的 name 被 CF 锁死为 "default"，**PUT 更新时带上 name 必被拒**：
    #    400 the name field cannot be modified: got X, want default
    #    所以更新只发 rules；只有首次创建（POST）才带 name/phase。
    if rs:
        path = f"/zones/{ZONE}/rulesets/{rs['id']}"
        method = "PUT"
        body = {"rules": rules}
    else:
        path = f"/zones/{ZONE}/rulesets"
        method = "POST"
        body = {"name": RULESET_NAME, "phase": "http_request_cache_settings", "rules": rules}

    d, err = call(method, path, body)
    if err or not d.get("success"):
        print(f"❌ 写入失败 HTTP {err}")
        for x in (d.get("errors") or []):
            print("   code=", x.get("code"), "|", x.get("message"))
            if x.get("meta"):
                print("   meta=", json.dumps(x.get("meta"), ensure_ascii=False)[:300])
        if "Authentication error" in str(d.get("errors")):
            print("   → token 无 Cache Rules 写权限，需重建 Token（见文件顶部注释）")
        return 2
    print(f"✅ Cache Rules 已写入（{method}）：")
    for r in (d.get("result") or {}).get("rules", []):
        print("   -", (r.get("description") or "")[:50])
    print("\n⚠️ 副作用（必须知道）：HTML 缓存后改首页不会立刻生效 → 跑 --purge 或等 2h")
    print("下一步：python3 cf-cache-rules.py --verify")
    return 0


def cmd_purge():
    d, err = call("POST", f"/zones/{ZONE}/purge_cache", {"purge_everything": True})
    if err or not d.get("success"):
        print("❌ 清缓存失败：", err or d.get("errors"))
        return 2
    print("✅ 已清空边缘缓存（生效约 1 分钟）")
    return 0


def cmd_verify():
    import re
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    ok = 0
    for p in ["/", "/5000years/", "/collection/"]:
        # 第一次必然 MISS（边缘还没有副本），所以预热一次、取第二次的状态
        st = "取不到"
        for _ in range(2):
            try:
                out = subprocess.run(["curl", "-s", "-o", "/dev/null", "-L", "--max-time", "45",
                                      "-A", ua, "-D", "-", f"https://{SITE}{p}"],
                                     capture_output=True, text=True, timeout=60).stdout
            except subprocess.TimeoutExpired:
                st = "超时"
                break
            m = re.search(r"cf-cache-status:\s*(\S+)", out, re.I)
            if m:
                st = m.group(1)
        hit = st.upper() in ("HIT", "REVALIDATED")
        ok += 1 if hit else 0
        print(f"  {p:<16} cf-cache-status = {st}  {'✅' if hit else '❌ 仍在回源'}")
    print(f"\n进 CDN：{ok}/3 页" + (" ✅ 达标" if ok >= 2 else " ⚠️ 未达标"))
    return 0 if ok >= 2 else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--purge", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.check:
        sys.exit(cmd_check())
    if a.apply:
        sys.exit(cmd_apply())
    if a.purge:
        sys.exit(cmd_purge())
    if a.verify:
        sys.exit(cmd_verify())
    ap.print_help()
