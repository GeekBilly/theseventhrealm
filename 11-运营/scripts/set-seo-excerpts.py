#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 批量写页面摘要（post_excerpt）→ 自动修好 meta/og/twitter description

原理：子主题 functions.php 第 95 行
    $raw = $post->post_excerpt ? $post->post_excerpt : $post->post_content;
  有摘要就用摘要，没有才回退正文截断。写 excerpt = 零主题改动修三处 description。

用法：
    python3 11-运营/scripts/set-seo-excerpts.py --check   # 只核对 ID↔slug 映射，只读
    python3 11-运营/scripts/set-seo-excerpts.py --apply   # 备份旧值 → 写入 → 复读校验

凭据从钥匙串读（服务名 theseventhrealm-wp / 账号 MollyBot_No.2），不落盘。
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = os.environ.get("SITE", "https://theseventhrealm.com")
WP_USER = os.environ.get("WP_USER", "MollyBot_No.2")
BACKUP_DIR = ROOT / "11-运营" / "backup"

# ── 17 条 SEO 摘要（来源：04-市场/02-市场调研/SEO诊断与引流方案-2026-09-30.md §七）
# key = 页面 ID，value = (期望 slug, 摘要)
EXCERPTS = {
    94:  ("sanhuang", "三皇五帝是哪三皇五帝？本卷讲传说时代的文明起点——火的使用、土壤上的长期投资，以及为什么这段历史应当“当传说读、当史实看”。不附会神话，只梳理文献与考古能对上的部分。"),
    95:  ("xia",      "夏朝到底存不存在？本卷从洪水传说与气候事件讲起：大禹改堵为导的工作方法、九州铸鼎的政治含义，以及二里头遗址能不能对上文献里的夏。前 2070 — 前 1600。"),
    96:  ("shang",    "商朝历史（前 1600 — 前 1046）：为什么商又叫“殷”？甲骨文里记录的占卜如何运作？本卷从殷墟发掘讲起，还原一个由甲骨刻辞与青铜礼器支撑的王朝，含问神者与写字者的分工。"),
    97:  ("zhou",     "周朝多少年（前 1046 — 前 256）：周公如何把“天命”翻译成一套可执行的制度？礼乐怎样成为当时的纲常，又为何在王室东迁后孕育出诸子百家。本卷贯通西周与东周八百年。"),
    98:  ("qin",      "秦朝统一六国靠的不是一场战争：百年积累加一次水渠事故。本卷讲清楚十年灭六国的节奏，以及书同文、车同轨这套标准为何比打仗更深远——前 221 — 前 207，十五年而亡，影响两千年。"),
    99:  ("han",      "汉朝历史（前 202 — 220）：从一个亭长的四年楚汉战争讲起，经文景不折腾、七国之乱与推恩令，到丝路通西域与“明犯强汉者，虽远必诛”的底气来源。看懂汉族为何叫汉族。"),
    100: ("sanguo",   "三国历史（220 — 280）：起点不是一个日期，而是一本书如何覆盖一段史实。本卷撇开演义，讲魏蜀吴三个政权各自的资源困局与解法，以及鼎足三分为什么维持了六十年。"),
    101: ("jin",      "两晋南北朝（266 — 589）：衣冠南渡是怎样的一次大搬家？本卷讲很短的统一之后很长的一段分裂，玄学清谈为何兴起，以及胡汉相融如何为隋唐埋下伏笔。"),
    102: ("sui",      "隋朝两代而亡（581 — 618），却留下了两条用了一千三百年的骨架：大运河与科举。本卷讲关陇集团的权力交接方式，以及一场考试如何开始取代门第。"),
    103: ("tang",     "唐朝历史（618 — 907）：唐的制度骨架直接长在隋的骨头上。本卷讲三省六部如何运转、武则天打破了什么规矩，以及“万国衣冠拜冕旒”的长安靠什么支撑，又为何终于安史之乱。"),
    104: ("wudai",    "五代十国（907 — 960）五十年换了五个姓：士兵的忠诚该归谁？本卷讲这笔账如何从唐末藩镇一路记下来，以及燕云十六州怎样成为一笔持续四百年的欠账。"),
    105: ("song",     "宋朝历史（960 — 1279）：为什么先解决军人的问题？本卷讲科举真正成为主渠道之后，市井为何空前繁华，词与散文为什么在这一刻成熟，以及“格物穷理”如何走向理学。"),
    106: ("yuan",     "元朝（1271 — 1368）不等于蒙古帝国——这是本卷的起点。讲行省与驿站这套治理架构如何被后世沿用，以及曲韵里唱出来的兴亡：关汉卿笔下的窦娥为什么指控天地。"),
    107: ("ming",     "明朝历史（1368 — 1644）：开国那套制度是专门为了“不再乱”而设计的。本卷讲郑和为什么七下西洋、为什么不再有第八次，以及王阳明“你未看此花时”的心学答案。"),
    108: ("qing",     "清朝历史（1636 — 1912）：现代中国版图的底色是这一时期奠定的。本卷讲从关外到入关的路径、康乾盛世到底盛在哪，以及龚自珍“不拘一格降人才”的变法呼声。"),
    109: ("juexing",  "觉醒年代（1912 — 1949）：一九一二之后制度换了，话却还没换。本卷讲白话文为什么一定会来、新青年凭什么成为一面旗帜，以及“摆脱冷气，只是向上走”的来处。"),
    32:  ("5000years", "上下五千年完整时间线：从三皇五帝到觉醒年代，十六卷长文一站式索引。每卷配一手典籍引注与年表，总计 9.5 万字原创，不戏说、不附会，可读可查。"),
}


def load_password():
    pw = os.environ.get("WP_APP_PASS", "")
    if pw:
        return pw
    try:
        pw = subprocess.run(
            ["security", "find-generic-password", "-s", "theseventhrealm-wp", "-w"],
            capture_output=True, text=True,
        ).stdout.strip()
    except FileNotFoundError:
        pass
    if not pw:
        sys.exit("✗ 拿不到应用密码（钥匙串服务名 theseventhrealm-wp）")
    return pw


def make_auth():
    pw = load_password()
    token = base64.b64encode(f"{WP_USER}:{pw}".encode()).decode()
    return {"Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "User-Agent": "seventhrealm-seo-bot/1.0"}


def get_page(pid, headers):
    url = f"{SITE}/wp-json/wp/v2/pages/{pid}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def set_excerpt(pid, text, headers):
    url = f"{SITE}/wp-json/wp/v2/pages/{pid}"
    body = json.dumps({"excerpt": text}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只读核对 ID↔slug 映射")
    ap.add_argument("--apply", action="store_true", help="备份 → 写入 → 复读校验")
    args = ap.parse_args()
    if not (args.check or args.apply):
        ap.print_help()
        sys.exit(1)

    headers = make_auth()
    ids = sorted(EXCERPTS)

    # ── 阶段 1：读现状
    print("【读取线上现状】")
    current = {}
    mismatch = []
    for pid in ids:
        try:
            p = get_page(pid, headers)
        except urllib.error.HTTPError as e:
            print(f"  ✗ {pid}: HTTP {e.code}")
            mismatch.append((pid, f"HTTP {e.code}", ""))
            continue
        slug = p.get("slug", "")
        title = strip_html(p.get("title", {}).get("rendered", ""))
        # 坑：REST 默认 view 上下文不给 excerpt.raw（恒为空），只有 context=edit 才给。
        # 所以这里退回 rendered 再去标签，否则现状会全显示 0 字、备份也记成空值。
        exc_raw = strip_html(
            p.get("excerpt", {}).get("raw") or p.get("excerpt", {}).get("rendered", "")
        )
        want_slug, _ = EXCERPTS[pid]
        ok = "✓" if slug == want_slug else "✗"
        if slug != want_slug:
            mismatch.append((pid, want_slug, slug))
        print(f"  {ok} {pid:>3}  slug={slug:<12} 标题={title[:18]:<20} 现摘要={len(exc_raw)}字")
        current[pid] = {"slug": slug, "title": title, "excerpt": exc_raw}
        time.sleep(0.3)

    if mismatch:
        print("\n⚠️  ID↔slug 映射不符，已中止（未写入任何数据）：")
        for pid, want, got in mismatch:
            print(f"   id={pid} 期望 slug={want} 实际={got}")
        sys.exit(2)

    if args.check:
        print("\n✅ 映射全部正确。要写入请跑：--apply")
        return

    # ── 阶段 2：备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")  # 日期一律 YYYY-MM-DD（见 README-空间结构.md §文件命名规范）
    bak = BACKUP_DIR / f"seo-excerpts-before-{ts}.json"
    bak.write_text(json.dumps(
        {str(k): v for k, v in current.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n【已备份旧摘要】→ {bak.relative_to(ROOT)}")

    # ── 阶段 3：写入
    print("\n【写入摘要】")
    ok_n = 0
    for pid in ids:
        _, text = EXCERPTS[pid]
        try:
            set_excerpt(pid, text, headers)
            print(f"  ✓ {pid} 写入 {len(text)} 字")
            ok_n += 1
        except urllib.error.HTTPError as e:
            print(f"  ✗ {pid} HTTP {e.code}: {e.read().decode()[:200]}")
        time.sleep(0.4)

    # ── 阶段 4：复读校验
    print("\n【复读校验】")
    bad = 0
    for pid in ids:
        want = EXCERPTS[pid][1]
        got = strip_html(get_page(pid, headers).get("excerpt", {}).get("rendered", ""))
        # WP 的 rendered 会包 <p>，去掉后比对
        same = got == want
        print(f"  {'✓' if same else '✗'} {pid} {'一致' if same else f'不一致：{got[:40]}…'}")
        if not same:
            bad += 1
        time.sleep(0.3)

    print(f"\n完成：写入 {ok_n}/{len(ids)}，校验不符 {bad}。")


if __name__ == "__main__":
    main()
