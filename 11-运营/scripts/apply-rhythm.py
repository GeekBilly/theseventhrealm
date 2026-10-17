#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「垂直节奏」注入全站页面正文，并可发布 / 验收。

真源 = 11-运营/spacing-rhythm.css。为什么靠注入而不是改主题：
qijing.css 在主题目录里，本机只有 WP 应用密码、没有 cPanel/FTP 凭据，主题文件改不动。

⚠️ 两条硬约束（都是踩过的坑）：
  1) 注入内容必须**无空行、压成单行** —— WP 的 wpautop 会按空行切块并插 <p>，
     插进 <style> 就是非法 token，后面规则会被整段吞掉（首页动画全白那次就是它）。
  2) 注入位置必须在正文**末尾** —— 页面自己的内联 <style> 在正文开头，
     同特异性下后出现的赢，放前面会被压住。

用法：
  python3 11-运营/scripts/apply-rhythm.py --apply     # 生成新版到 <备份目录>-new
  python3 11-运营/scripts/apply-rhythm.py --publish   # POST 到线上
  python3 11-运营/scripts/apply-rhythm.py --verify    # 抓线上确认已生效
  DRY=1 ... --publish                                  # 只体检不发布
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "11-运营/spacing-rhythm.css"
BAK = ROOT / "11-运营/上线备份/spacing-20261017"
NEW = ROOT / "11-运营/上线备份/spacing-20261017-new"
MARK = "qj-rhythm"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
API = "https://theseventhrealm.com/wp-json/wp/v2/pages"


def build_css():
    """把真源压成一行（去注释、去空行）。"""
    s = SPEC.read_text(encoding="utf-8")
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    s = re.sub(r"\s+", " ", s)
    parts = [p.strip() for p in s.split("}") if p.strip()]
    return "".join(p + "}" for p in parts)


def tag():
    return f'<style id="{MARK}">{build_css()}</style>'


def strip_old(text):
    """移除此前注入过的同名块，保证幂等。"""
    return re.sub(rf'<style id="{MARK}">.*?</style>\s*', "", text, flags=re.S)


def apply():
    NEW.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(BAK.glob("*.html")):
        src = strip_old(f.read_text(encoding="utf-8"))
        NEW.joinpath(f.name).write_text(src + "\n" + tag(), encoding="utf-8")
        n += 1
    print(f"已生成 {n} 页 → {NEW}")
    print(f"注入块 {len(tag())} 字节；含空行检查：",
          "无空行 ✓" if "\n" not in tag() else "有空行 ✗")


def auth():
    out = subprocess.run(
        ["security", "find-generic-password", "-a", "MollyBot_No.2",
         "-s", "theseventhrealm-wp", "-w"],
        capture_output=True, text=True, check=True)
    return "MollyBot_No.2", out.stdout.strip()


def post(pid, body, user, pwd):
    payload = json.dumps({"content": body}, ensure_ascii=False)
    tmp = ROOT / ".tmp-rhythm.json"
    tmp.write_text(payload, encoding="utf-8")
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "90", "-u", f"{user}:{pwd}",
         "-A", UA, "-X", "POST", "-H", "Content-Type: application/json",
         "-H", "Accept: application/json", "--compressed",
         "--data-binary", f"@{tmp}", f"{API}/{pid}"],
        capture_output=True, text=True)
    return r.stdout


def publish():
    user, pwd = auth()
    dry = os.environ.get("DRY")
    ok, bad = [], []
    for f in sorted(NEW.glob("*.html")):
        pid = int(f.name.split("-")[0])
        body = f.read_text(encoding="utf-8")
        if MARK not in body:
            bad.append((pid, "正文缺少注入标记")); continue
        if dry:
            ok.append((pid, "DRY")); continue
        out = post(pid, body, user, pwd)
        # 响应超过约 190KB 会被截断，解析失败不代表写入失败 —— 以再查一次为准
        try:
            d = json.loads(out)
            if d.get("id") == pid:
                ok.append((pid, d.get("modified", "")[:19]))
            else:
                bad.append((pid, str(d)[:100]))
        except Exception:
            # 截断兜底：再 GET 一次看 modified 与标记
            g = subprocess.run(
                ["curl", "-sL", "--max-time", "60", "-u", f"{user}:{pwd}",
                 "-A", UA, "-H", "Accept: application/json", "--compressed",
                 f"{API}/{pid}?context=edit&_fields=id,modified,content"],
                capture_output=True, text=True).stdout
            try:
                d = json.loads(g)
                hit = MARK in d["content"]["raw"]
                (ok if hit else bad).append((pid, d.get("modified", "")[:19] + (" ✓" if hit else " ✗未生效")))
            except Exception as e:
                bad.append((pid, f"GET 校验失败 {str(e)[:60]}"))
        print(f"  {pid:>3} {f.name:22s} {ok[-1][1] if ok and ok[-1][0] == pid else bad[-1][1]}")
    print(f"\n成功 {len(ok)} / 失败 {len(bad)}")
    for b in bad:
        print("  失败:", b)


def verify():
    """抓线上页面，确认注入块存在且没被 wpautop 插坏。"""
    idmap = {}
    for f in sorted(NEW.glob("*.html")):
        idmap[int(f.name.split("-")[0])] = f.name
    user, pwd = auth()
    rows = []
    for pid in sorted(idmap):
        g = subprocess.run(
            ["curl", "-sL", "--max-time", "60", "-u", f"{user}:{pwd}",
             "-A", UA, "-H", "Accept: application/json", "--compressed",
             f"{API}/{pid}?context=edit&_fields=id,modified,content"],
            capture_output=True, text=True).stdout
        try:
            d = json.loads(g)
            raw = d["content"]["raw"]
        except Exception as e:
            rows.append((pid, idmap[pid], f"拉取失败 {str(e)[:40]}", False)); continue
        m = re.search(rf'<style id="{MARK}">(.*?)</style>', raw, re.S)
        if not m:
            rows.append((pid, idmap[pid], "线上无注入块", False)); continue
        css = m.group(1)
        p_bad = len(re.findall(r"</?p[ >]", css))
        rows.append((pid, idmap[pid],
                     f"CSS {len(css)} 字节 / 内嵌<p>={p_bad} / 花括号 {css.count('{')}/{css.count('}')}",
                     p_bad == 0 and css.count("{") == css.count("}")))
    bad = [r for r in rows if not r[3]]
    for pid, name, info, good in rows:
        print(f"  {'✓' if good else '✗'} {pid:>3} {name:22s} {info}")
    print(f"\n线上生效 {len(rows) - len(bad)}/{len(rows)} 页")
    return 1 if bad else 0


def main():
    if "--apply" in sys.argv:
        apply()
    elif "--publish" in sys.argv:
        publish()
    elif "--verify" in sys.argv:
        sys.exit(verify())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
