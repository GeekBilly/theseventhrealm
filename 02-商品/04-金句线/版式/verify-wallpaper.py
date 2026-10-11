import subprocess, os
BASE='/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/05-承接站/样张'
env=dict(os.environ); env["PATH"]="/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:"+env["PATH"]
AB="/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"
def run(a,t=40):
    try:
        r=subprocess.run([AB]+a,timeout=t,capture_output=True,text=True,env=env); return ((r.stdout or "")+(r.stderr or "")).strip()
    except Exception: return "TIMEOUT"
JS="""
(()=>{const R=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();
 return {l:Math.round(r.left),t:Math.round(r.top),r:Math.round(r.right),b:Math.round(r.bottom),w:Math.round(r.width),h:Math.round(r.height)};};
const ov=(a,b)=>a&&b&&a.l<b.r&&b.l<a.r&&a.t<b.b&&b.t<a.b;
const q=R('.quote'),s=R('.src'),se=R('.seal'),sub=R('.sub'),e=R('.era'),br=R('.brand'),h=R('.hero-char');
return JSON.stringify({vp:[innerWidth,innerHeight],hero:h,quote:q,src:s,seal:se,sub:sub,era:e,brand:br,
 ov_quote_src:ov(q,s),ov_quote_seal:ov(q,se),ov_sub_era:ov(sub,e),ov_src_seal:ov(s,se),
 out:[['quote',q],['src',s],['seal',se],['sub',sub],['era',e],['brand',br]]
   .filter(([n,x])=>!x||x.l<0||x.t<0||x.r>innerWidth||x.b>innerHeight).map(([n])=>n)});})()
"""
for kind,vp in [("desktop","1920 1080"),("mobile","1170 2532")]:
    w,hh=vp.split(); run(["set","viewport",w,hh])
    run(["open",f"file://{BASE}/shang-{kind}.html"]); run(["wait","2200"])
    print(kind, run(["eval",JS]))
run(["close"])
