import subprocess, os
env = dict(os.environ)
env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:" + env["PATH"]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"
CWD = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/shop"


def run(a, t=35):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


# 1) 首页 / 关于页：分支入口必须仍是隐藏
print("== 分支入口复核 ==")
run(["set", "viewport", "1440", "1000"])
for url in ["https://theseventhrealm.com/", "https://theseventhrealm.com/about/"]:
    run(["open", url])
    run(["wait", "1500"])
    js = ("JSON.stringify({url:location.pathname,"
          "branch:[...document.querySelectorAll('.branches a')].map(a=>a.textContent.trim().replace(/\\s+/g,' ')),"
          "todo:document.querySelectorAll('.branches a.todo').length,"
          "bad:[...document.querySelectorAll('a')].filter(a=>/\\/(novel|anime|film|game)/.test(a.getAttribute('href')||'')).length,"
          "footer:document.querySelectorAll('footer a').length})")
    print(" ", run(["eval", js])[:260])

# 2) 截图：时间线「展卷」入口 + 商朝页
print("== 截图 ==")
run(["open", "https://theseventhrealm.com/5000years/"])
run(["wait", "1800"])
run(["eval", "window.scrollTo(0, document.querySelector(\".era .more[href='/5000years/shang/']\").getBoundingClientRect().top + window.scrollY - 420)"])
run(["wait", "900"])
print(" ", run(["screenshot", f"{CWD}/线上-时间线-展卷入口.png"])[:40])

run(["open", "https://theseventhrealm.com/5000years/shang/"])
run(["wait", "1800"])
print(" ", run(["screenshot", f"{CWD}/线上-商朝页-桌面.png"])[:40])
run(["eval", "window.scrollTo(0, 1500)"])
run(["wait", "900"])
print(" ", run(["screenshot", f"{CWD}/线上-商朝页-三卡.png"])[:40])

run(["set", "viewport", "390", "844"])
run(["open", "https://theseventhrealm.com/5000years/shang/"])
run(["wait", "1500"])
print(" ", run(["screenshot", f"{CWD}/线上-商朝页-手机.png"])[:40])
run(["close"])
