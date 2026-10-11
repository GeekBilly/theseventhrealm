import subprocess, os
env = dict(os.environ)
env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:" + env["PATH"]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"


def run(a, t=35):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


D = """(()=>{const a=document.querySelector(".era .more[href='/5000years/shang/']");
const r=a.getBoundingClientRect();
const cx=r.x+r.width/2, cy=r.y+r.height/2;
const top=document.elementFromPoint(cx,cy);
return JSON.stringify({rect:{x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)},
inView: r.y>=0 && r.y<=innerHeight,
topEl: top? top.tagName+'.'+top.className : null,
topIsLinkOrChild: top? (top===a || a.contains(top)) : false,
pe:getComputedStyle(a).pointerEvents,
parentCls:a.parentElement.className,
tag:a.tagName})})()"""
RES = "JSON.stringify({href:location.href,h1:(document.querySelector('.hero h1')||{}).textContent,here:Array.from(document.querySelectorAll('.nav-root a.here')).map(a=>a.textContent.trim())})"

run(["set", "viewport", "1440", "1000"])
run(["open", "https://theseventhrealm.com/5000years/"])
run(["wait", "1800"])
print("诊断:", run(["eval", D])[:450])
print("JS click:", run(["eval", "(()=>{document.querySelector(\".era .more[href='/5000years/shang/']\").click();return 'clicked'})()"])[:60])
run(["wait", "1800"])
print("结果:", run(["eval", RES])[:260])
run(["close"])
