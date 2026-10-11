#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mailerlite-edit.py —— 一条命令改 MailerLite 自动化里的交付邮件内容

为什么需要它
    MailerLite **没有配 API Token**，改邮件内容只能走后台 UI。
    而这个 UI 有两个坑（2026-10-02 实测踩过）：
      ① **必须先暂停 workflow 才能编辑内容**，改完**必须 Activate 恢复**
         —— 忘了恢复，新订阅者就不会进入流程（静默失效）
      ② 富文本里的链接要用「浮动工具栏 → 链条图标 → Redirect to」改，
         不是点一下链接就行，而且**工具栏只在双击选中文字后才出现**

本脚本把这些步骤固定下来，并且：
    * 所有点击位置**运行时用 JS 算坐标**，不写死像素
    * 每一步都**验证结果**，对不上就中止
    * **无论如何都会在结束时恢复 Activate**（try/finally），不会留成暂停态

用法
    # 1) 先列出 workflow 与邮件 ID
    python3 11-运营/scripts/mailerlite-edit.py --list

    # 2) 只换邮件里的下载链接
    python3 11-运营/scripts/mailerlite-edit.py \\
        --workflow 200105734236538128 --email 200106360837244871 \\
        --set-link "https://theseventhrealm.com/wp-content/uploads/2026/10/wallpaper-jinju-32-v3.zip"

    # 3) 同时改正文里的文字（可多次）
    ... --replace-text "5.5 MB" "6.8 MB" --replace-text "旧词" "新词"

    # 4) 先看它打算做什么，不动线上
    ... --dry

可选参数
    --port 9333        调试端口（默认 9333，避开常开的 9222）
    --keep-open        结束后不关浏览器（排查用）
    --no-activate      改完**故意**保持暂停（一般别用）

前提
    Chrome 里已登录 MailerLite（脚本复制一份 profile 起独立实例，不碰你正在用的 Chrome）。
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_PROF = pathlib.Path.home() / "Library/Application Support/Google/Chrome"
TMP_PROF = ROOT / ".ml-tmp"
VIEWPORT = (1512, 950)


# ────────────────────────── 基础封装 ──────────────────────────

def ab(*args, timeout=90, check=True):
    """调用 agent-browser

    两个坑（都实测踩过）：
      ① 输出在 **stderr** 上 —— 只读 stdout 会得到空字符串
      ② agent-browser 默认把 socket 放 `~/.agent-browser`，**在工作区之外**
         → 在受限沙箱里会报 "Socket directory ... is not writable"
         ⇒ 用 AGENT_BROWSER_SOCKET_DIR 指到工作区内
    """
    env = dict(os.environ)
    env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin:" + env["PATH"]
    env["AGENT_BROWSER_SOCKET_DIR"] = str(ROOT / ".agent-browser")
    subprocess.run(["mkdir", "-p", env["AGENT_BROWSER_SOCKET_DIR"]], capture_output=True)
    r = subprocess.run([AB, *args], capture_output=True, text=True,
                       timeout=timeout, env=env)
    out = "\n".join(x for x in [(r.stdout or "").strip(),
                                (r.stderr or "").strip()] if x).strip()
    if check and r.returncode != 0 and "timed out" not in out.lower():
        print(f"  ! agent-browser {' '.join(args)}: {out[-200:]}", file=sys.stderr)
    return out


def js(expr, timeout=60):
    """在页面里跑 JS，返回解析后的值（约定 expr 用 JSON.stringify 包一层）

    ⚠️ 必须先折成单行：agent-browser eval 收到多行 JS 时会静默返回空
       （2026-10-02 实测，排查了半小时）。折行不影响本文件里的 JS，
       因为它们都没有跨行的字符串字面量。
    """
    expr = " ".join(expr.split())
    out = ab("eval", expr, timeout=timeout)
    out = re.sub(r"^✓ Done\s*", "", out).strip()
    v = out
    # agent-browser 会把 JSON.stringify 的结果再当字符串输出一次 → 可能出现双重编码
    # 例：期望 'https://x'，实际拿到 '"https://x"'。这里循环剥壳。
    for _ in range(3):
        if not (isinstance(v, str) and len(v) >= 2 and v[0] == '"' and v[-1] == '"'):
            break
        try:
            nv = json.loads(v)
        except Exception:
            break
        if nv == v:
            break
        v = nv
    if isinstance(v, str) and v[:1] in "[{":
        try:
            v = json.loads(v)
        except Exception:
            pass
    return v


def click_xy(x, y):
    """按屏幕坐标点一下（比选择器可靠：UI 全是 SVG 图标没有文本）"""
    ab("mouse", "move", str(int(x)), str(int(y)), check=False)
    time.sleep(0.35)
    ab("mouse", "down", check=False)
    time.sleep(0.18)
    ab("mouse", "up", check=False)


def find_buttons(pattern_js):
    """返回 [{t,x,y}]，坐标已算好中心点"""
    return js(f"""JSON.stringify([...document.querySelectorAll('button,a,[role=button]')]
        .map(e=>{{const r=e.getBoundingClientRect();
                 return {{t:(e.textContent||'').trim().replace(/\\s+/g,' ').slice(0,40),
                          x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
                          vis:r.width>0&&r.height>0}}}})
        .filter(b=>b.vis && {pattern_js}))""") or []


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)
    print(f"    ✓ {msg}")


def wait_for(cond_js, timeout=40, interval=2, label="页面就绪"):
    """轮询等条件成立（MailerLite 是重 SPA，open 返回不代表渲染完）"""
    for _ in range(max(1, int(timeout / interval))):
        try:
            if js(cond_js):
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


# ────────────────────────── 浏览器生命周期 ──────────────────────────

def port_alive(port):
    """直接探端口，别去解析 agent-browser 的输出（踩过：解析不可靠）"""
    try:
        r = subprocess.run(["curl", "-s", "--noproxy", "*", "--max-time", "3",
                            f"http://127.0.0.1:{port}/json/version"],
                           capture_output=True, text=True, timeout=8)
        return "webSocketDebuggerUrl" in (r.stdout or "")
    except Exception:
        return False


def free_port(start):
    for p in range(start, start + 12):
        if not port_alive(p):
            return p
    raise RuntimeError(f"{start}..{start+11} 端口都被占用")


def setup_browser(port):
    print("── 准备隔离浏览器 ──")
    port = free_port(port)
    if TMP_PROF.exists():
        shutil.rmtree(TMP_PROF, ignore_errors=True)
    (TMP_PROF / "Default").mkdir(parents=True, exist_ok=True)
    coped = []
    for src, dst in [(CHROME_PROF / "Local State", TMP_PROF / "Local State")]:
        if src.exists():
            shutil.copy2(src, dst); coped.append(src.name)
    for name in ["Cookies", "Login Data", "Preferences", "Secure Preferences"]:
        src = CHROME_PROF / "Default" / name
        if src.exists():
            shutil.copy2(src, TMP_PROF / "Default" / name); coped.append(f"Default/{name}")
    net = CHROME_PROF / "Default/Network/Cookies"
    if net.exists():
        (TMP_PROF / "Default/Network").mkdir(parents=True, exist_ok=True)
        shutil.copy2(net, TMP_PROF / "Default/Network/Cookies")
        coped.append("Default/Network/Cookies")
    require(len(coped) >= 2, f"复制了 {len(coped)} 个 profile 文件（含登录态）")

    subprocess.Popen(
        [CHROME, f"--user-data-dir={TMP_PROF}", f"--remote-debugging-port={port}",
         "--no-sandbox", "--disable-setuid-sandbox", "--no-first-run",
         "--no-default-browser-check", "--headless=new", "--disable-gpu", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        if port_alive(port):
            break
    else:
        raise RuntimeError(f"调试端口 {port} 没起来")
    require(True, f"调试端口 {port} 已就绪")
    ab("connect", str(port), check=False)
    ab("set", "viewport", str(VIEWPORT[0]), str(VIEWPORT[1]), check=False)
    return port


def teardown(keep_open=False):
    if keep_open:
        print("\n（--keep-open：浏览器留着，端口仍可用）")
        return
    ab("close", "--all", check=False)
    time.sleep(2)
    # 只杀「用我们这份临时 profile」的实例 —— 绝不动用户自己的 Chrome
    subprocess.run(["pkill", "-f", f"user-data-dir={TMP_PROF}"], capture_output=True)
    shutil.rmtree(TMP_PROF, ignore_errors=True)
    print("\n── 已关闭隔离浏览器并清理 profile 副本 ──")


def goto(url, wait=9):
    ab("open", url, check=False)          # 经常报 timeout，但页面其实已经打开
    time.sleep(wait)


# ────────────────────────── 核心操作 ──────────────────────────

def pause_workflow(wf):
    """暂停：先点顶栏 Pause，再点确认弹窗里的 Pause

    注意：邮件侧栏里那个「Pause automation」只在点开邮件节点后才出现，
    别依赖它 —— 顶栏的 Pause 才是常驻入口。
    """
    print("── 暂停 workflow（MailerLite 要求先暂停才能改内容）──")
    goto(f"https://dashboard.mailerlite.com/automations/{wf}/edit")
    require(wait_for("JSON.stringify([...document.querySelectorAll('button')].some(e=>/^(activate|pause)$/i.test(e.textContent.trim())))"),
            "workflow 编辑器已加载")

    for _ in range(3):
        btns = [b for b in find_buttons("/pause/i.test(b.t)")
                if re.fullmatch(r"Pause", b["t"], re.I)]
        require(bool(btns), "找到 Pause 按钮")
        # 只有一个 → 顶栏那个；出现两个 → 下面那个是弹窗确认按钮
        target = min(btns, key=lambda b: b["y"]) if len(btns) == 1 \
            else max(btns, key=lambda b: b["y"])
        click_xy(target["x"], target["y"])
        time.sleep(6)
        state = js("""JSON.stringify([...document.querySelectorAll('button')]
            .map(e=>e.textContent.trim()).filter(t=>/^(activate|pause)$/i.test(t)))""")
        if "Activate" in (state or []):
            require(True, f"已暂停（顶部按钮变为 {state}）")
            return
    raise RuntimeError("暂停未生效")


def activate_workflow(wf):
    """恢复运行：工具栏 Activate → 弹窗确认 Activate"""
    print("── 恢复 workflow（关键：忘了这步新订阅者就进不来）──")
    goto(f"https://dashboard.mailerlite.com/automations/{wf}/edit")
    require(wait_for("JSON.stringify([...document.querySelectorAll('button')].some(e=>/^(activate|pause)$/i.test(e.textContent.trim())))"),
            "workflow 编辑器已加载")
    btns = find_buttons("/^activate$/i.test(b.t)")
    require(bool(btns), "找到 Activate 按钮")
    top = min(btns, key=lambda b: b["y"])
    click_xy(top["x"], top["y"]); time.sleep(4)

    btns = find_buttons("/^activate$/i.test(b.t)")
    if len(btns) >= 2:
        dlg = max(btns, key=lambda b: b["y"])
        click_xy(dlg["x"], dlg["y"]); time.sleep(6)
    state = js("JSON.stringify([...document.querySelectorAll('button')]"
               ".map(e=>e.textContent.trim()).filter(t=>/^(activate|pause)$/i.test(t)))")
    require("Pause" in (state or []), f"已恢复运行（顶部按钮变为 {state}）")


def open_email_editor(email, wf):
    """直接开邮件内容编辑器（不点节点，稳）"""
    print("── 打开邮件内容编辑器 ──")
    goto(f"https://dashboard.mailerlite.com/emails/{email}/edit"
         f"?redirect=https%3A%2F%2Fdashboard.mailerlite.com%2Fautomations%2F{wf}%2Fedit", wait=11)
    require(wait_for("JSON.stringify(location.pathname.includes('/emails/'))", timeout=40),
            "邮件内容编辑器已打开")


def set_link(url):
    """改富文本里的链接：双击选中 → 链条图标 → 填 URL → Insert"""
    print(f"── 改链接 → {url} ──")
    wait_for("""JSON.stringify([...document.querySelectorAll('a')].some(a=>{
        const h=a.getAttribute('href')||'';
        return /^https?:/.test(h) && !/unsubscribe|preference/i.test(h)}))""", timeout=30)
    anchors = js("""JSON.stringify([...document.querySelectorAll('a')]
        .map(a=>{const r=a.getBoundingClientRect();
                 return {h:a.getAttribute('href'),t:a.textContent.trim().slice(0,20),
                         x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2),
                         w:Math.round(r.width)}})
        .filter(a=>a.h && /^https?:/.test(a.h) && !/unsubscribe|preference/i.test(a.h)))""")
    require(bool(anchors), f"找到 {len(anchors)} 个正文链接")
    a = anchors[0]
    print(f"      当前: {a['h']}")
    print(f"      文字: 「{a['t']}」")

    # 双击链接 → 浮动工具栏
    # ⚠️ 两个坑：① 手工 down/up 两次不一定被当成双击，要用 agent-browser 的 dblclick
    #          ② 工具栏是**瞬时**的（判存在之后就可能消失），所以存在性与按钮必须**同一次 eval**取
    TB = """JSON.stringify([...document.querySelectorAll('.bubble-menu button,[class*=floating-toolbar] button')]
        .map(e=>{const r=e.getBoundingClientRect();const p=e.querySelector('path');
                 return {d:p?p.getAttribute('d'):'', x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}}))"""
    cand = []
    for attempt in range(3):
        ab("dblclick", "a.ml-content-link", check=False)
        time.sleep(1.0)
        cand = js(TB) or []
        if cand:
            break
        print(f"      （第 {attempt+1} 次双击没出工具栏，重试）")
        click_xy(a["x"], a["y"])
    if not cand:
        dbg = js("""(()=>{const t=document.querySelector('.bubble-menu,[class*=floating-toolbar]');
            return JSON.stringify(t?{tag:t.tagName,cls:(t.className||'').toString().slice(0,80),
                btns:t.querySelectorAll('button').length}: '没有工具栏元素')})()""")
        print(f"      🔍 诊断: {dbg}")
        raise RuntimeError("双击后浮动工具栏里取不到 button")
    require(True, f"浮动工具栏有 {len(cand)} 个按钮")
    linkbtn = [b for b in cand
               if "18.3638" in b["d"] or "16.9496" in b["d"] or "12.7071" in b["d"]]
    if not linkbtn:
        print("      ⚠️ 没认出链条按钮，工具栏按钮清单：")
        for b in cand:
            print(f"         i={b['i']}  x={b['x']}  path={b['d'][:48]}")
        raise RuntimeError("没有匹配到链条（链接）按钮的 SVG 路径特征")
    click_xy(linkbtn[0]["x"], linkbtn[0]["y"]); time.sleep(3)

    inp = js("""JSON.stringify([...document.querySelectorAll('input')]
        .filter(i=>/^https:\\/\\/$/.test(i.placeholder||'')).map(i=>({v:i.value})))""")
    require(bool(inp), "链接对话框已打开")
    # 填 URL（React 受控输入，fill 偶尔不落，重试几次）
    READ = """JSON.stringify([...document.querySelectorAll('input')]
        .filter(i=>/^https:\\/\\/$/.test(i.placeholder||'')).map(i=>i.value)[0]||'')"""
    ok = ""
    for attempt in range(4):
        ab("fill", 'input[placeholder="https://"]', url, check=False)
        time.sleep(1.6)
        ok = js(READ)
        if ok == url:
            break
        print(f"      （第 {attempt+1} 次 fill 后读到 {ok!r}，重试）")
    require(ok == url, f"URL 已填入输入框（实际 {ok!r}）")

    ins = find_buttons("/^insert$/i.test(b.t)")
    require(bool(ins), "找到 Insert 按钮")
    click_xy(ins[0]["x"], ins[0]["y"]); time.sleep(4)

    now = js("""JSON.stringify([...document.querySelectorAll('a')]
        .map(a=>a.getAttribute('href'))
        .filter(h=>h && /^https?:/.test(h) && !/unsubscribe|preference/i.test(h)))""")
    require(now and now[0] == url, "链接已生效")


def replace_text(old, new):
    """改正文纯文字：定位 → 放光标 → Shift+Right 选中 → 输入"""
    print(f"── 改文字 「{old}」→「{new}」──")
    pos = js(f"""(()=>{{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        let n;while(n=w.nextNode()){{const i=n.nodeValue.indexOf({json.dumps(old)});
        if(i>=0){{const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+{len(old)});
        const b=r.getBoundingClientRect();
        return JSON.stringify({{x:Math.round(b.x),y:Math.round(b.y+b.height/2)}})}}}}return JSON.stringify(null)}})()""")
    require(pos is not None, "找到目标文字")

    click_xy(pos["x"] - 6, pos["y"]); time.sleep(1.2)
    cur = js("""(()=>{const s=window.getSelection();
        return JSON.stringify({t:(s.anchorNode&&s.anchorNode.nodeValue||''),o:s.anchorOffset})})()""")
    require(old in cur.get("t", ""), "光标已落在该文字所在文本节点")
    if cur["o"] != cur["t"].indexOf(old):
        raise RuntimeError(f"光标位置不对（在 {cur['o']}，应为 {cur['t'].indexOf(old)}）——已中止，未做修改")

    for _ in range(len(old)):
        ab("press", "Shift+ArrowRight", check=False); time.sleep(0.2)
    sel = js("JSON.stringify((window.getSelection()||{}).toString())")
    require(sel == old, f"已选中「{sel}」")
    ab("keyboard", "type", new, check=False); time.sleep(2)

    after = js(f"""(()=>{{const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        let n;while(n=w.nextNode()){{if(n.nodeValue.includes({json.dumps(new)}))return JSON.stringify(n.nodeValue.trim())}}
        return JSON.stringify(null)}})()""")
    require(after is not None, f"文字已改为「{after}」")


def save_email():
    print("── 保存（点 Next，编辑器会自动落盘）──")
    nxt = find_buttons("/^next$/i.test(b.t)")
    require(bool(nxt), "找到 Next")
    click_xy(nxt[0]["x"], nxt[0]["y"]); time.sleep(7)


def verify_email(email, want_link=None, want_texts=None):
    print("── 复核 ──")
    goto(f"https://dashboard.mailerlite.com/emails/{email}/edit", wait=11)
    links = js("""JSON.stringify([...document.querySelectorAll('a')]
        .map(a=>a.getAttribute('href'))
        .filter(h=>h && /^https?:/.test(h) && !/unsubscribe|preference/i.test(h)))""") or []
    if want_link:
        require(links and links[0] == want_link, f"链接 = {links[0] if links else '无'}")
    if want_texts:
        body = js("JSON.stringify(document.body.innerText)") or ""
        for t in want_texts:
            # 若期望项本身是 URL，去 href 里找，而不是正文文字里找
            # （超链接的 URL 不会出现在 innerText —— 2026-10-02 踩过这个假阴性）
            if isinstance(t, str) and t.startswith(("http://", "https://")):
                require(t in links, f"链接含 {t}（实际 href={links}）")
            else:
                require(t in body, f"正文含「{t}」")


def list_workflows():
    print("── 现有自动化 ──")
    goto("https://dashboard.mailerlite.com/automations/status/workflows", wait=9)
    rows = js(r"""JSON.stringify([...document.querySelectorAll('a')]
        .map(a=>{const h=a.getAttribute('href')||'';
                 const m=h.match(/^\/automations\/(\d+)/);
                 return m?{id:m[1],t:a.textContent.trim().slice(0,30)}:null})
        .filter(Boolean))""") or []
    seen = {}
    for r in rows:
        seen.setdefault(r["id"], r)
    for wid in seen:
        print(f"\n  workflow id = {wid}")
        goto(f"https://dashboard.mailerlite.com/automations/{wid}", wait=8)
        mails = js(r"""JSON.stringify([...document.querySelectorAll('a')]
            .map(a=>{const m=(a.getAttribute('href')||'').match(/emails\/(\d+)\//);
                     return m?{id:m[1]}:null}).filter(Boolean))""") or []
        for m in {x["id"] for x in mails}:
            print(f"      email id    = {m}")


# ────────────────────────── 主流程 ──────────────────────────

def main():
    ap = argparse.ArgumentParser(add_help=True, description="改 MailerLite 自动化邮件内容")
    ap.add_argument("--list", action="store_true", help="列出 workflow / email id")
    ap.add_argument("--workflow", help="workflow id")
    ap.add_argument("--email", help="email id")
    ap.add_argument("--set-link", help="把正文第一个链接改成这个 URL")
    ap.add_argument("--replace-text", nargs=2, action="append", metavar=("OLD", "NEW"),
                    help="替换正文文字，可重复")
    ap.add_argument("--port", type=int, default=9333)
    ap.add_argument("--dry", action="store_true", help="只检查不改动")
    ap.add_argument("--keep-open", action="store_true")
    ap.add_argument("--no-activate", action="store_true", help="改完保持暂停（一般别用）")
    args = ap.parse_args()

    if args.list:
        try:
            setup_browser(args.port)
            list_workflows()
        finally:
            teardown(args.keep_open)
        return

    if not (args.workflow and args.email):
        ap.error("需要 --workflow 与 --email（或先用 --list 查）")
    if not (args.set_link or args.replace_text):
        ap.error("没有什么要改的：给 --set-link 或 --replace-text")

    print("=" * 62)
    print(f"  目标 workflow : {args.workflow}")
    print(f"  目标 email    : {args.email}")
    if args.set_link:
        print(f"  改链接        : {args.set_link}")
    for old, new in (args.replace_text or []):
        print(f"  改文字        : 「{old}」→「{new}」")
    print(f"  模式          : {'DRY RUN（不改动）' if args.dry else '实际写入'}")
    print("=" * 62)

    paused = False
    try:
        setup_browser(args.port)      # ← 必须在 try 内：否则它一失败就不会 teardown
        if args.dry:
            goto(f"https://dashboard.mailerlite.com/emails/{args.email}/edit", wait=11)
            links = js("""JSON.stringify([...document.querySelectorAll('a')]
                .map(a=>a.getAttribute('href'))
                .filter(h=>h && /^https?:/.test(h) && !/unsubscribe|preference/i.test(h)))""")
            print(f"\n  DRY：当前链接 = {links}")
            print("  DRY：未暂停、未修改、未保存")
            return

        pause_workflow(args.workflow)
        paused = True
        open_email_editor(args.email, args.workflow)
        if args.set_link:
            set_link(args.set_link)
        for old, new in (args.replace_text or []):
            replace_text(old, new)
        save_email()
        verify_email(args.email, args.set_link,
                     [n for _, n in (args.replace_text or [])])
    finally:
        if paused and not args.dry:
            if args.no_activate:
                print("\n⚠️ --no-activate：workflow 仍处于暂停状态，记得手动恢复！")
            else:
                try:
                    activate_workflow(args.workflow)
                except Exception as e:
                    print(f"\n🔴 恢复失败：{e}")
                    print("🔴 请立刻手动去 MailerLite 点 Activate，否则新订阅者进不来！")
        teardown(args.keep_open)
    print("\n✅ 完成")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 中止：{e}", file=sys.stderr)
        print("   （若已暂停，脚本已在 finally 里尝试恢复；请确认一下）", file=sys.stderr)
        sys.exit(1)
