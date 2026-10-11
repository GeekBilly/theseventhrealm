import subprocess, os, json
ROOT = '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17'
SITE = os.environ.get('SITE', 'https://theseventhrealm.com')
env = dict(os.environ)
env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:" + env["PATH"]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"


def run(a, t=40):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def ev(js):
    return run(["eval", js])


# 一次性量：一级项可见文本 / 是否换行 / nav 高度 / 横向溢出 / 二级项字体与一级是否一致
LAYOUT = """
(()=>{
  const nav=document.querySelector('nav');
  const items=[...document.querySelectorAll('.nav-root > li')].filter(li=>li.offsetParent!==null);
  const tops=items.map(li=>Math.round(li.getBoundingClientRect().top));
  const l1=items.map(li=>{const a=li.querySelector(':scope > a');
    return {t:a.innerText.trim(), w:Math.round(a.getBoundingClientRect().width),
            ff:getComputedStyle(a).fontFamily.split(',')[0].replace(/["']/g,''),
            fs:getComputedStyle(a).fontSize, grp:a.getAttribute('data-group')||''};});
  const sub=document.querySelector('.nav-root .sub-list a')||document.querySelector('.nav-root .sub a');
  return JSON.stringify({
    url:location.pathname, vw:innerWidth,
    rows:[...new Set(tops)].length,
    navH:Math.round(nav.getBoundingClientRect().height),
    overflowX: document.documentElement.scrollWidth - innerWidth,
    l1:l1,
    subFF: sub? getComputedStyle(sub).fontFamily.split(',')[0].replace(/["']/g,'') : null,
    subFS: sub? getComputedStyle(sub).fontSize : null
  });
})()
"""

HERE = """
JSON.stringify({path:location.pathname,
  here:[...document.querySelectorAll('.nav-root a.here')].map(a=>(a.closest('.sub')||a.closest('.sub-list')?'二级:':'一级:')+a.innerText.trim())})
"""

print("=== 1. 桌面 1440 首页 ===")
run(["set", "viewport", "1440", "1000"])
run(["open", SITE + "/"])
run(["wait", "2000"])
print(ev(LAYOUT))
run(["screenshot", f"{ROOT}/shop/live-v16-桌面-首页.png"])

print("\n=== 2. 桌面 hover：传说与三代 / 关于我们 ===")
run(["hover", ".nav-root > li:nth-child(3) > a"])
run(["wait", "800"])
print(ev("JSON.stringify([...document.querySelectorAll('.nav-root > li:nth-child(3) .sub-list a')].map(a=>a.innerText.trim()+' -> '+a.getAttribute('href')))"))
run(["screenshot", f"{ROOT}/shop/live-v16-桌面-时期面板.png"])
run(["hover", ".nav-root > li:nth-child(7) > a"])
run(["wait", "800"])
print(ev("JSON.stringify([...document.querySelectorAll('.nav-root > li:nth-child(7) .sub a')].map(a=>a.innerText.trim()+' -> '+a.getAttribute('href')))"))
run(["screenshot", f"{ROOT}/shop/live-v16-桌面-关于面板.png"])

print("\n=== 3. 朝代页高亮（真 URL） ===")
for slug in ["shang", "song", "juexing"]:
    run(["open", f"{SITE}/5000years/{slug}/"])
    run(["wait", "1800"])
    print(" ", slug, ev(HERE))
run(["screenshot", f"{ROOT}/shop/live-v16-桌面-商朝页高亮.png"])

print("\n=== 4. 总览页 / 法务页高亮 ===")
for p in ["/5000years/", "/privacy/"]:
    run(["open", SITE + p])
    run(["wait", "1500"])
    print(" ", p, ev(HERE))

print("\n=== 5. 手机 390 ===")
run(["set", "viewport", "390", "844"])
run(["open", SITE + "/"])
run(["wait", "2000"])
print(ev(LAYOUT))
run(["screenshot", f"{ROOT}/shop/live-v16-手机-首页.png"])
run(["click", ".nav-root > li:nth-child(3) .ns-btn"])
run(["wait", "900"])
print(" 展开后：", ev("JSON.stringify({open:[...document.querySelectorAll('.sub-list')].map(u=>getComputedStyle(u).display),navH:Math.round(document.querySelector('nav').getBoundingClientRect().height),overflowX:document.documentElement.scrollWidth-innerWidth})"))
run(["screenshot", f"{ROOT}/shop/live-v16-手机-时期面板.png"])
run(["click", ".nav-root > li:nth-child(7) .ns-btn"])
run(["wait", "900"])
print(" 互斥检查：", ev("JSON.stringify([...document.querySelectorAll('.sub-list,.sub')].map(u=>getComputedStyle(u).display))"))
run(["screenshot", f"{ROOT}/shop/live-v16-手机-关于面板.png"])
run(["close"])
