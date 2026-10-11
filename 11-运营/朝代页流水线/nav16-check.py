import re, pathlib, subprocess, os
ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
live = (ROOT / '03-页面/live-5000-v14.html').read_text(encoding='utf-8')
tpl = (ROOT / 'seventhrealm-child/templates/page.html').read_text(encoding='utf-8')
css = str((ROOT / 'seventhrealm-child/assets/qijing.css').resolve())
out = re.sub(r'<nav\b.*?</nav>', lambda m: re.search(r'<nav\b.*?</nav>', tpl, re.S).group(0), live, count=1, flags=re.S)
out = re.sub(r'<footer>.*?</script>', lambda m: re.search(r'<footer>.*?</script>', tpl, re.S).group(0), out, count=1, flags=re.S)
out = re.sub(r'<link[^>]*qijing\.css[^>]*>', f'<link rel="stylesheet" href="file://{css}">', out)
(ROOT / '03-页面/pv-v16.html').write_text(out, encoding='utf-8')

env = dict(os.environ)
env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:" + env["PATH"]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"
URL = f"file://{ROOT}/03-页面/pv-v16.html"


def run(a, t=30):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


JS = """(()=>{const q=s=>document.querySelector(s),qa=s=>document.querySelectorAll(s);
const B=e=>{const r=e.getBoundingClientRect();return{x:Math.round(r.x),w:Math.round(r.width),right:Math.round(r.right),h:Math.round(r.height),y:Math.round(r.y)}};
const items=[...qa('.nav-root > li > a')];
return JSON.stringify({vw:innerWidth,scrollW:document.documentElement.scrollWidth,
navH:Math.round(q('nav').getBoundingClientRect().height),
rows:[...new Set(items.map(a=>Math.round(a.getBoundingClientRect().y)))].length,
top:items.map(a=>a.textContent.trim()+'|'+Math.round(a.getBoundingClientRect().width)),
subFont:getComputedStyle(q('.sub-list a')).fontFamily.slice(0,40),
subSize:getComputedStyle(q('.sub-list a')).fontSize,
subCount:qa('.sub-list a').length+'/'+qa('.sub-pair a').length,
here:[...qa('.nav-root a.here')].map(a=>a.textContent.trim())})})()"""

print("== 桌面 1440 ==")
run(["set", "viewport", "1440", "1000"])
run(["open", URL])
run(["wait", "1500"])
print(run(["eval", JS])[:700])
BOX = "JSON.stringify({vis:getComputedStyle(document.querySelector('.nav-root > li:nth-child(%d) .sub')).visibility,box:(e=>{const r=e.getBoundingClientRect();return{x:Math.round(r.x),w:Math.round(r.width),right:Math.round(r.right),h:Math.round(r.height)}})(document.querySelector('.nav-root > li:nth-child(%d) .sub')),scrollW:document.documentElement.scrollWidth})"
run(["hover", ".nav-root > li:nth-child(3) > a"])
run(["wait", "700"])
print("hover 组1:", run(["eval", BOX % (3, 3)])[:260])
run(["screenshot", str(ROOT / "03-页面/nav16-桌面-时期组面板.png")])
run(["hover", ".nav-root > li:nth-child(7) > a"])
run(["wait", "700"])
print("hover 关于:", run(["eval", BOX % (7, 7)])[:220])
run(["screenshot", str(ROOT / "03-页面/nav16-桌面-关于面板.png")])
run(["close"])

print()
print("== 手机 390 ==")
run(["set", "viewport", "390", "844"])
run(["open", URL])
run(["wait", "1200"])
print(run(["eval", JS])[:600])
run(["click", ".nav-root > li:nth-child(3) .ns-btn"])
run(["wait", "600"])
MOB = "JSON.stringify({d:getComputedStyle(document.querySelector('.nav-root > li:nth-child(3) .sub')).display,w:Math.round(document.querySelector('.nav-root > li:nth-child(3) .sub').getBoundingClientRect().width),scrollW:document.documentElement.scrollWidth,navH:Math.round(document.querySelector('nav').getBoundingClientRect().height)})"
print("开组1:", run(["eval", MOB])[:220])
run(["screenshot", str(ROOT / "03-页面/nav16-手机-时期组面板.png")])
run(["close"])
