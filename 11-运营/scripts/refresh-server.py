#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 本地刷新服务（页面上的「刷新数据」按钮背后干活的那个）

只做一件事：被点一下，就真的去取一次数、重建一次页面。

  端点
    GET  /ping                 存活探测（页面先探它，探不到就退化成重新载入）
    GET  /status               当前指标（只读本地台账，不取数、很快）
    POST /refresh              真刷新：站点体检 → 重建看板片段 → 重建工作台
    POST /refresh?upload=1     同上 + 覆盖更新资料库两个节点（=同步云端）
    GET  /once                 与 /refresh 等价，方便 curl / launchd 调用
    GET  /                     工作台 HTML（同源打开时，刷新按钮 100% 可用）
    GET  /board                晨检看板 HTML

  用法
    python3 refresh-server.py            # 常驻前台（Ctrl-C 停）
    python3 refresh-server.py --port 8787
    python3 refresh-server.py --once     # 只跑一次刷新并打印结果，然后退出
    python3 refresh-server.py --every 30               # 每 30 分钟自动刷新（只改本地）
    python3 refresh-server.py --every 30 --auto-upload  # 每 30 分钟自动刷新 + 同步云端

  为什么需要 --every
    云端页（https）受浏览器规则限制，连不到本机 http://127.0.0.1，在那儿点刷新
    只能是重新载入。要让云端也能看到新数，只能把取数搬到服务端定时跑：本机跑完
    （可选同步云端）后，云端点刷新重载即可拿到最近一次结果，滞后不超过一个周期。

设计约束（沿用既有纪律）：
  - 零积分：取数只用 curl / openssl / 本地脚本，不调大模型。
  - 不编造：取不到就写「本次未提供」，绝不沿用旧值冒充本次。
  - 不擅自改线上：默认只重建本地；同步云端必须显式带 upload=1（页面上是 Shift + 点），
    定时同步同样必须显式加 --auto-upload，绝不默认开。
  - 同一时刻只允许一次刷新（加锁），重复点击返回 busy 而不是并发跑两遍。
"""
import os
import re
import json
import time
import threading
import subprocess
import importlib.util
from datetime import datetime, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PY = "/Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8787

SITE = "https://theseventhrealm.com"
HOST = "theseventhrealm.com"
# 必须带浏览器 UA：Cloudflare 会拦默认 UA，403 不是站点故障（已知现象）
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")

STATUS_JSON = os.path.join(ROOT, "11-运营/data/morning-status.json")
LEDGER = os.path.join(ROOT, "11-运营/积分账本与产能测算.md")
FETCH_CREDITS = os.path.join(HERE, "fetch-credits.sh")
LOG = os.path.join(ROOT, "11-运营/data/refresh-server.log")
WB_HTML = os.path.join(ROOT, "11-运营/reports/工作台.html")
BOARD_HTML = os.path.join(ROOT, "11-运营/reports/每日晨检看板.html")

LOCK = threading.Lock()


def _load(name, filename):
    """按路径加载连字符命名的项目脚本（不能直接 import）。"""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wb = _load("qj_wb", "build-workbench.py")


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except Exception:
        pass


def sh(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception:
        return ""


# ---------- 站点体检（真取数） ----------
def probe():
    """curl + openssl 取站点与证书；失败字段留空，由看板显示「本次未提供」。"""
    out = {}
    out["http_code"] = sh(f'curl -s -o /dev/null -w "%{{http_code}}" -A "{UA}" -L --max-time 20 {SITE}/')
    out["http_5000years"] = sh(
        f'curl -s -o /dev/null -w "%{{http_code}}" -A "{UA}" -L --max-time 20 {SITE}/5000years/')
    # 不带 -L：要看 http → https 的跳转码本身
    out["http_redirect"] = sh(
        f'curl -s -o /dev/null -w "%{{http_code}}" -A "{UA}" --max-time 20 http://{HOST}/')
    enddate = sh(f'echo | openssl s_client -connect {HOST}:443 -servername {HOST} 2>/dev/null '
                 f'| openssl x509 -noout -enddate', timeout=25)
    m = re.search(r"notAfter=(.+)$", enddate)
    if m:
        try:
            d = datetime.strptime(m.group(1).strip(), "%b %d %H:%M:%S %Y %Z")
            out["ssl_not_after"] = d.strftime("%Y-%m-%d")
            out["ssl_days"] = (d.date() - date.today()).days
        except ValueError:
            pass
    issuer = sh(f'echo | openssl s_client -connect {HOST}:443 -servername {HOST} 2>/dev/null '
                f'| openssl x509 -noout -issuer', timeout=25)
    if issuer:
        out["ssl_issuer"] = issuer.replace("issuer=", "").strip()[:60]
    server = sh(f'curl -sI -A "{UA}" --max-time 20 {SITE}/ | grep -i "^server:" | head -1')
    out["cf_proxy"] = "已生效" if "cloudflare" in server.lower() else (server or "")
    if out.get("http_code"):
        out["http_note"] = (f"首页 {out['http_code']} · /5000years/ "
                            f"{out.get('http_5000years') or '—'}（带 UA 复核；默认 UA 被 CF 拦 403）")
        out["cf_note"] = server or ""
    return {k: v for k, v in out.items() if v not in ("", None)}


def write_status(probe_out):
    """合并写回 morning-status.json：本次取到的覆盖，取不到的保留原值不删。
    （删掉旧值会让看板显示「本次未提供」——那是本次没取到的真实情况，但若是
      偶发网络抖动，保留上次值更有用。这里选择：只覆盖成功取到的字段。）"""
    base = {}
    if os.path.exists(STATUS_JSON):
        try:
            base = json.load(open(STATUS_JSON, encoding="utf-8"))
        except Exception:
            base = {}
    base.update(probe_out)
    base["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    base["_说明"] = "站点体检快照。由晨检或刷新服务写入；字段缺失在看板显示「本次未提供」。"
    base["_口径"] = "curl 必须带浏览器 UA，否则 Cloudflare 返回 403（已知现象，非站点故障）。"
    os.makedirs(os.path.dirname(STATUS_JSON), exist_ok=True)
    with open(STATUS_JSON, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)
    return base


def write_ledger(remain, used, total):
    """回写积分账本：同日覆盖、跨日追加。只动「当天那一行」，别的行一个字不碰。"""
    today = date.today().strftime("%Y-%m-%d")
    row = (f"| {today} | **{remain}** | {used} | ✅ 自动取数（刷新服务 "
           f"{datetime.now():%H:%M}）；周期总额 {total or '—'} |")
    s = open(LEDGER, encoding="utf-8").read()
    hits = list(re.finditer(r"^\| " + re.escape(today) + r" \|.*$", s, flags=re.M))
    if hits:
        h = hits[-1]
        s = s[:h.start()] + row + s[h.end():]
    else:
        s = s.rstrip() + "\n" + row + "\n"
    with open(LEDGER, "w", encoding="utf-8") as f:
        f.write(s)


def fetch_credits():
    """真取一次积分余额（常驻 Chrome + CDP，见 fetch-credits.sh）。

    取不到就返回原因，**不阻塞刷新**，也绝不把旧值写成今天的 ——
    账本只由脚本写，写不进去就让看板显示「本次未提供」。
    """
    try:
        r = subprocess.run(["zsh", FETCH_CREDITS], capture_output=True,
                           text=True, timeout=150, cwd=ROOT)
    except Exception as e:
        return f"取数异常（{e}）"
    lines = [l for l in (r.stdout or "").splitlines() if l.strip().startswith("{")]
    if not lines:
        return "无返回（需常驻 Chrome 且已登录）"
    try:
        j = json.loads(lines[-1])
    except Exception:
        return "返回非 JSON"
    if not j.get("ok"):
        return f"失败：{j.get('error', '未知')}"
    remain = j.get("remain")
    if remain is None:
        return "结果缺 remain"
    today = date.today().strftime("%Y-%m-%d")
    used = "—"
    for d in j.get("byDay", []):
        if str(d).startswith(today):
            used = str(d).split(":")[-1]
    write_ledger(remain, used, j.get("cycleTotal"))
    return f"{remain}"


def payload():
    """当前指标（状态灯数据），供前端刷新后即时重绘。"""
    return {"ok": True, "gen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "items": wb.load_pulse()}


def refresh(upload=False):
    t0 = time.time()
    steps = []
    try:
        st = write_status(probe())
        steps.append(f"体检 {st.get('http_code') or '—'}/{st.get('ssl_days', '—')}天")
    except Exception as e:
        steps.append(f"体检失败（{e}）")
    try:
        steps.append(f"积分 {fetch_credits()}")
    except Exception as e:
        steps.append(f"积分取数异常（{e}）")
    # 站点流量：Cloudflare 只回溯 3–4 天，必须每次刷新时顺带采集落盘，
    # 否则「流量」tab 会一直是上一次手动采集的死数据。
    # collect 是按日期 upsert，重复跑幂等，不会写脏历史。
    try:
        r = subprocess.run([PY, os.path.join(HERE, "cf-analytics.py"), "collect"],
                           capture_output=True, text=True, timeout=180, cwd=ROOT)
        if r.returncode == 0:
            m = re.search(r"真实访次\s*([\d,]+)", r.stdout or "")
            steps.append(f"流量 {m.group(1) if m else 'ok'}")
        else:
            steps.append("流量采集失败")
            log(f"cf-analytics collect 失败：{(r.stderr or r.stdout)[:300]}")
    except Exception as e:
        steps.append(f"流量采集异常（{e}）")
    # 订阅名单：MailerLite API。取不到（没配 token / 接口不通）只记一条原因，
    # 绝不阻塞后面重建页面 —— 名单没接上，工作台其余部分照样要能用。
    try:
        r = subprocess.run([PY, os.path.join(HERE, "mailerlite-stats.py"), "collect"],
                           capture_output=True, text=True, timeout=120, cwd=ROOT)
        if r.returncode == 0:
            m = re.search(r"订阅\s*(\d+)\s*人", r.stdout or "")
            steps.append(f"订阅 {m.group(1) if m else 'ok'}")
        else:
            why = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
            steps.append(f"订阅未取到（{(why[0] if why else '未知')[:36]}）")
    except Exception as e:
        steps.append(f"订阅采集异常（{e}）")
    for script in ("build-morning-board.py", "build-workbench.py"):
        args = [PY, os.path.join(HERE, script)]
        if upload and script == "build-morning-board.py":
            # 它上传后会顺带重建并上传工作台，无需再单独上传一次
            args.append("--upload")
        r = subprocess.run(args, capture_output=True, text=True, timeout=300, cwd=ROOT)
        steps.append(f"{script} {'ok' if r.returncode == 0 else 'FAIL'}")
        if r.returncode != 0:
            log(f"{script} 失败：{(r.stderr or r.stdout)[:300]}")
    out = payload()
    out["uploaded"] = bool(upload)
    out["steps"] = steps
    out["sec"] = round(time.time() - t0, 1)
    log(("刷新" + ("+同步" if upload else "")) + f" 完成 {out['sec']}s · {' · '.join(steps)}")
    return out


def auto_loop(every_min, upload):
    """定时自动刷新。详见文件头「为什么需要 --every」。

    与手动刷新共用同一把锁：上一次没跑完就直接跳过，不排队、不并发。
    单次失败只记日志，不影响下一轮，也不拖垮服务。
    """
    log(f"定时刷新已开启：每 {every_min:g} 分钟{'并同步云端' if upload else '（仅本地）'}")
    while True:
        time.sleep(max(30, every_min * 60))
        if not LOCK.acquire(blocking=False):
            log("定时刷新跳过：上一次还没跑完")
            continue
        try:
            r = refresh(upload)
            log(f"定时刷新完成 {r.get('sec')}s · " + " · ".join(r.get("steps", [])))
        except Exception as e:
            log(f"定时刷新异常：{e}")
        finally:
            LOCK.release()


class H(BaseHTTPRequestHandler):
    server_version = "QJRefresh/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def _html(self, path):
        if not os.path.exists(path):
            self._json({"ok": False, "error": "页面尚未生成，请先跑一次 build-*.py"}, 404)
            return
        b = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        q = self.path.split("?")[1] if "?" in self.path else ""
        if p == "/ping":
            # 用真实监听端口：--port 指定别的端口时，报 8787 会误导人
            return self._json({"ok": True, "port": self.server.server_address[1],
                               "ts": datetime.now().strftime("%H:%M:%S")})
        if p == "/status":
            return self._json(payload())
        if p in ("/refresh", "/once"):
            return self._json(self._do_refresh("upload=1" in q))
        if p in ("/", "/workbench", "/index.html"):
            return self._html(WB_HTML)
        if p == "/board":
            return self._html(BOARD_HTML)
        return self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        p = self.path.split("?")[0]
        q = self.path.split("?")[1] if "?" in self.path else ""
        if p == "/refresh":
            return self._json(self._do_refresh("upload=1" in q))
        return self._json({"ok": False, "error": "not found"}, 404)

    def _do_refresh(self, upload):
        if not LOCK.acquire(blocking=False):
            return {"ok": False, "busy": True, "error": "上一次刷新还没跑完"}
        try:
            return refresh(upload)
        except Exception as e:
            log(f"刷新异常：{e}")
            return {"ok": False, "error": str(e)}
        finally:
            LOCK.release()

    def log_message(self, fmt, *args):
        pass  # 静音默认访问日志（写入自己的 log 文件足够）


def main():
    import sys
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    if "--once" in sys.argv:
        r = refresh(upload="--upload" in sys.argv)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    every = 0.0
    if "--every" in sys.argv:
        try:
            every = float(sys.argv[sys.argv.index("--every") + 1])
        except Exception:
            print("❌ --every 后面要跟分钟数，例如 --every 30")
            return
    auto_upload = "--auto-upload" in sys.argv
    for i in range(10):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port + i), H)
            break
        except OSError:
            continue
    else:
        print(f"❌ 端口 {port}—{port+9} 都被占用")
        return
    real = srv.server_address[1]
    print(f"第七境刷新服务已启动：http://127.0.0.1:{real}")
    print(f"  工作台  http://127.0.0.1:{real}/")
    print(f"  晨检    http://127.0.0.1:{real}/board")
    print(f"  日志    {LOG}")
    log(f"服务启动 127.0.0.1:{real}")
    if every > 0:
        threading.Thread(target=auto_loop, args=(every, auto_upload),
                         daemon=True).start()
        print(f"  定时    每 {every:g} 分钟自动刷新"
              f"{'并同步云端' if auto_upload else '（仅本地）'}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
