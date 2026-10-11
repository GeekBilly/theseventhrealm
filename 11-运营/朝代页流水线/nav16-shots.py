import pathlib, subprocess, os
ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
URL = f"file://{ROOT}/03-页面/pv-v16.html"
env = dict(os.environ)
env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:" + env["PATH"]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"


def run(a, t=30):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


SIM = """
((p)=>{
  p=p.replace(/\\/+$/,'')||'/';
  document.querySelectorAll('.nav-root a.here').forEach(a=>a.classList.remove('here'));
  var alias={'/contact':'/about','/privacy':'/about','/terms':'/about','/disclaimer':'/about'};
  var target=alias[p]||p;
  var G={sanhuang:1,xia:1,shang:1,zhou:1,qin:2,han:2,sanguo:2,jin:2,
         sui:3,tang:3,wudai:3,song:3,yuan:4,ming:4,qing:4,juexing:4};
  document.querySelectorAll('.nav-root > li > a').forEach(function(a){
    var href=a.getAttribute('href')||''; if(href.indexOf('#')>-1)return;
    var q=new URL(href,location.origin).pathname.replace(/\\/+$/,'')||'/';
    if(q===target)a.classList.add('here');
  });
  var era=p.match(/^\\/5000years\\/([a-z]+)/);
  if(era&&G[era[1]]){var ga=document.querySelector('.nav-root > li > a[data-group="'+G[era[1]]+'"]');if(ga)ga.classList.add('here');}
  document.querySelectorAll('.nav-root .sub a').forEach(function(a){
    var href=a.getAttribute('href')||''; if(href.indexOf('#')>-1)return;
    var q=new URL(href,location.origin).pathname.replace(/\\/+$/,'')||'/';
    if(q===p)a.classList.add('here');
  });
  return JSON.stringify([...document.querySelectorAll('.nav-root a.here')].map(a=>(a.closest('.sub')?'二级:':'一级:')+a.textContent.trim()));
})('%s')
"""

print("== 高亮（含二级，用 textContent）==")
run(["set", "viewport", "1440", "1000"])
run(["open", URL])
run(["wait", "1200"])
for p in ["/5000years/shang/", "/5000years/song/", "/privacy/", "/5000years/"]:
    print("  ", p, run(["eval", SIM % p])[:160])

print("\n== 截图 ==")
run(["eval", SIM % "/5000years/shang/"])
run(["hover", ".nav-root > li:nth-child(3) > a"])
run(["wait", "700"])
print(" ", run(["screenshot", str(ROOT / "03-页面/nav16-桌面-时期组面板.png")])[:50])
run(["hover", ".nav-root > li:nth-child(7) > a"])
run(["wait", "700"])
print(" ", run(["screenshot", str(ROOT / "03-页面/nav16-桌面-关于面板.png")])[:50])
run(["set", "viewport", "390", "844"])
run(["open", URL])
run(["wait", "1200"])
run(["click", ".nav-root > li:nth-child(3) .ns-btn"])
run(["wait", "700"])
print(" ", run(["screenshot", str(ROOT / "03-页面/nav16-手机-时期组面板.png")])[:50])
run(["close"])
