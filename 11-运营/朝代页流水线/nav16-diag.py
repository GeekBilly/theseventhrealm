import pathlib, subprocess, os
ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
URL = f"file://{ROOT}/shop/pv-v16.html"
env = dict(os.environ)
env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:" + env["PATH"]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"


def run(a, t=30):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


DIAG = """JSON.stringify({
 labels:[...document.querySelectorAll('.ns-btn')].map(l=>({for:l.getAttribute('for'),x:Math.round(l.getBoundingClientRect().x),y:Math.round(l.getBoundingClientRect().y),w:Math.round(l.getBoundingClientRect().width)})),
 checked:[...document.querySelectorAll('.ns-toggle')].filter(i=>i.checked).map(i=>i.id),
 inputs:[...document.querySelectorAll('.ns-toggle')].map(i=>i.id),
 open:[...document.querySelectorAll('.nav-root > li')].map(li=>{const s=li.querySelector('.sub');return s?getComputedStyle(s).display:'-'})
})"""

run(["set", "viewport", "390", "844"])
run(["open", URL])
run(["wait", "1200"])
print("初始:", run(["eval", DIAG])[:700])
print("click li3 btn:", run(["click", ".nav-root > li:nth-child(3) .ns-btn"])[:40])
run(["wait", "700"])
print("之后:", run(["eval", DIAG])[:700])
run(["close"])
