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


# 可见文本（innerText 会忽略 display:none 的 span）
VIS = "JSON.stringify({desktop:innerWidth,visible:[...document.querySelectorAll('.nav-root > li > a')].map(a=>a.innerText.trim()),navH:Math.round(document.querySelector('nav').getBoundingClientRect().height),scrollW:document.documentElement.scrollWidth})"

# 模拟高亮：把模板里的逻辑对给定 path 跑一遍（file:// 下无法改 pathname，只能逻辑重放）
SIM = """
((p)=>{
  p = p.replace(/\\/+$/,'')||'/';        // 与真实脚本一致：先去掉结尾斜杠
  document.querySelectorAll('.nav-root a.here').forEach(a=>a.classList.remove('here'));
  var alias={'/contact':'/about','/privacy':'/about','/terms':'/about','/disclaimer':'/about'};
  var target=alias[p]||p;
  var G={sanhuang:1,xia:1,shang:1,zhou:1,qin:2,han:2,sanguo:2,jin:2,
         sui:3,tang:3,wudai:3,song:3,yuan:4,ming:4,qing:4,juexing:4};
  document.querySelectorAll('.nav-root > li > a').forEach(function(a){
    if(a.classList.contains('todo'))return;
    var href=a.getAttribute('href')||'';
    if(href.indexOf('#')>-1)return;
    var q=new URL(href,location.origin).pathname.replace(/\\/+$/,'')||'/';
    if(q===target)a.classList.add('here');
  });
  var era=p.match(/^\\/5000years\\/([a-z]+)/);
  if(era&&G[era[1]]){var ga=document.querySelector('.nav-root > li > a[data-group="'+G[era[1]]+'"]');if(ga)ga.classList.add('here');}
  document.querySelectorAll('.nav-root .sub a').forEach(function(a){
    var href=a.getAttribute('href')||'';
    if(href.indexOf('#')>-1)return;
    var q=new URL(href,location.origin).pathname.replace(/\\/+$/,'')||'/';
    if(q===p)a.classList.add('here');
  });
  return JSON.stringify({path:p,here:[...document.querySelectorAll('.nav-root a.here')].map(a=>a.innerText.trim())});
})('%s')
"""

print("== 可见文本（桌面 1440 应全称 / 手机 390 应简称）==")
for vp in [("1440", "1000"), ("390", "844")]:
    run(["set", "viewport"] + list(vp))
    run(["open", URL])
    run(["wait", "1200"])
    print(" ", vp[0], run(["eval", VIS])[:340])

print()
print("== 高亮逻辑模拟 ==")
run(["set", "viewport", "1440", "1000"])
run(["open", URL])
run(["wait", "1000"])
for p in ["/", "/5000years", "/5000years/shang/", "/5000years/juexing/", "/5000years/song/", "/privacy/", "/contact/"]:
    print(" ", run(["eval", SIM % p])[:180])
run(["close"])
