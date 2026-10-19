#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 工作台门户生成器（多 tab 单页）

与 build-morning-board.py 的关系：
  - 本页的「今日晨检」tab **内嵌** `11-运营/reports/morning-fragment.html`（晨检脚本产出）。
  - 因此本页必须每天重建一次，否则 tab 里永远是旧数据；
    `build-morning-board.py --upload` 会自动串起本脚本，无需单独调度。

用法：
  python3 11-运营/scripts/build-workbench.py             # 只生成本地 HTML
  python3 11-运营/scripts/build-workbench.py --upload    # 覆盖更新资料库固定节点
"""
import os
import re
import json
import html
import importlib.util
import subprocess
import sys
from datetime import datetime, date

ROOT = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
OUT = os.path.join(ROOT, "11-运营/reports/工作台.html")
FRAG = os.path.join(ROOT, "11-运营/reports/morning-fragment.html")
IMG_JSON = os.path.join(ROOT, "11-运营/data/workbench-images.json")
FOLDER_JSON = os.path.join(ROOT, "11-运营/data/workbench-folders.json")
NOW_MD = os.path.join(ROOT, ".workbuddy/memory/NOW.md")
MW_JSON = os.path.join(ROOT, "11-运营/data/market-watch.json")
# 站点流量：由 11-运营/scripts/cf-analytics.py collect 产出（每日随晨检采集）
TRAF_JSON = os.path.join(ROOT, "04-市场/03-推广获客/数据回收/站点分析/明细-latest.json")
TRAF_CSV = os.path.join(ROOT, "04-市场/03-推广获客/数据回收/站点分析/站点数据.csv")
# 订阅名单：由 11-运营/scripts/mailerlite-stats.py collect 产出（随每轮刷新采集）
# 🔴 只含数量与时间，绝不落邮箱明文（隐私纪律同 10-09 入库红线）
SUBS_JSON = os.path.join(ROOT, "11-运营/data/订阅-latest.json")
SUBS_CSV = os.path.join(ROOT, "11-运营/data/订阅数据.csv")
XHS_ACCT_CSV = os.path.join(ROOT, "11-运营/data/xhs-账号数据.csv")   # 小红书逐日（每天采一次）
LEDGER_MD = os.path.join(ROOT, "11-运营/积分账本与产能测算.md")        # 积分逐日余额/消耗
# 页面路径的中文名（只列真的有人看的内容页，其余原样显示）
PATH_CN = {
    "/": "首页",
    "/collection/": "藏品总览",
    "/collection/dynasty/": "朝代专栏",
    "/collection/people/": "人物专栏",
    "/collection/books/": "典集专栏",
    "/5000years/": "五千年长卷",
    "/faq/": "常见问题",
    "/privacy/": "隐私政策",
    "/about/": "关于我们",
    "/en/": "英文站",
}
# 朝代页 slug → 中文
DYNASTY_CN = {
    "sanhuang": "三皇五帝", "xia": "夏", "shang": "商", "zhou": "周", "qin": "秦",
    "han": "汉", "sanguo": "三国", "jin": "两晋南北朝", "sui": "隋", "tang": "唐",
    "wudai": "五代十国", "song": "宋", "yuan": "元", "ming": "明", "qing": "清",
    "juexing": "觉醒年代",
}
# 明显不是真人访问的路径（扫描器常用），从"真人页"里剔除
JUNK_HINT = ("@fs", "secrets", "service_account", "readme.html", "license.txt",
             "actuator", "meta-data", ".aws", ".ssh", ".env", "wp-config",
             "credentials", "phpinfo", "shell", "adminer", "phpmyadmin")


def path_cn(p):
    """把路径转成人看得懂的中文名。"""
    if p in PATH_CN:
        return PATH_CN[p]
    m = re.match(r"^/5000years/([a-z]+)/?$", p or "")
    if m and m.group(1) in DYNASTY_CN:
        return f"五千年 · {DYNASTY_CN[m.group(1)]}"
    m = re.match(r"^/collection/dynasty/([a-z]+)/?$", p or "")
    if m and m.group(1) in DYNASTY_CN:
        return f"朝代 · {DYNASTY_CN[m.group(1)]}"
    return p


def is_junk(p):
    lp = (p or "").lower()
    return any(h in lp for h in JUNK_HINT)

# 设计 token 与晨检取数函数都复用同一份实现，避免两边各写一套（风格漂移 / 口径漂移）。
# 注意：项目脚本用连字符命名，Python 不能直接 import，只能按文件路径加载。
def _load(name, filename):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


qj_theme = _load("qj_theme", "qj_theme.py")
bmb = _load("bmb", "build-morning-board.py")
qjr = _load("qjr", "qj_refresh.py")

# 固定节点：团队空间「第七境」› 00-工作台导航 › 第七境 · 工作台
NODE_ID = "KCOnwrcKvGZhtvmIQpobOd"
SPACE_ID = "vtgKWy99bZoF6oKAIzqfHt"
HOME_DOC = "lRuFJ3vuAXgplbPJL2VkGL"          # 00-工作台首页（文字版）
BOARD_NODE = "csMhWQGumhu0dSU3swjthz"        # 每日晨检看板（独立页）
SKILL = "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library"


def load_json(p, default):
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default


IMG = load_json(IMG_JSON, {})
F = load_json(FOLDER_JSON, {})


def img(key):
    for k, v in IMG.items():
        if k.endswith(key) and v:
            return v
    return ""


LOGO_BANNER = img("logo-banner.png")

ORDER = [("sanhuang", "三皇", "传说时代"), ("xia", "夏", "前 2070—前 1600"),
         ("shang", "商", "前 1600—前 1046"), ("zhou", "周", "前 1046—前 256"),
         ("qin", "秦", "前 221—前 206"), ("han", "汉", "前 202—220"),
         ("sanguo", "三国", "220—280"), ("jin", "晋", "265—420"),
         ("sui", "隋", "581—618"), ("tang", "唐", "618—907"),
         ("wudai", "五代", "907—960"), ("song", "宋", "960—1279"),
         ("ming", "明", "1368—1644"), ("qing", "清", "1644—1912")]

SECTIONS = [
    ("01", "内容资产", "146", "典籍库 44 · 历史长卷 36 · 成书稿 22 · 写作 41", "01-内容资产"),
    ("02", "商品与作品规范", "5", "产品线规划 · 作品范式 · 版式铁律", "02-商品与作品规范"),
    ("03", "市场与增长", "38", "竞品研究 · 市场调研 · 推广获客 · 报告", "03-市场与增长"),
    ("04", "课程", "11", "开站实录 · 风险管控 · 变现实录", "04-课程"),
    ("05", "社区与发布", "5", "发帖指南 · 已发布长文", "05-社区与发布"),
    ("06", "规划与决策", "5", "1-3-5-10 年规划 · 节奏表 · 决策日志", "06-规划与决策"),
    ("07", "品牌总纲与铁律", "3", "总原则 · 空间结构 · 事实核查", "07-品牌总纲与铁律"),
]

TABS = [("today", "今日"), ("morning", "晨检详报"), ("content", "内容资产"),
        ("market", "市场风向"), ("traffic", "站点流量"), ("xhs", "小红书"),
        ("subs", "订阅名单"), ("rules", "纪律与边界")]
# 说明（2026-10-19 重构）：今日＝所有平台的汇总与判断；内容分区 + 字形长卷合并为「内容资产」；
# 每个对外平台（站点 / 小红书 / 订阅）各自一个 tab 放详情。晨检详报保留，它是原始逐项读数。

CSS = qj_theme.FONTS + qj_theme.tokens(":root") + """
*{box-sizing:border-box;margin:0;padding:0}
img{max-width:100%;height:auto}
body{background:var(--white);color:var(--ink);font-family:var(--f-body);font-size:17px;line-height:1.9;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
a{color:inherit;text-decoration:none}

.brand{padding:0 0 6px}
.brand img{width:100%;display:block}

.tabbar{position:sticky;top:0;z-index:50;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);border-top:1px solid rgba(26,26,24,.08);border-bottom:1px solid rgba(26,26,24,.08)}
.tabbar .wrap{display:flex;justify-content:center;gap:6px;flex-wrap:wrap;padding:10px 24px}
.tab{font-family:var(--f-brush);font-size:19px;letter-spacing:2px;color:var(--ink3);
 background:none;border:0;border-bottom:2px solid transparent;padding:8px 18px;cursor:pointer;
 transition:color .2s,border-color .2s}
.tab:hover{color:var(--ink2)}
.tab.on{color:var(--cinnabar);border-bottom-color:var(--cinnabar)}
@media(max-width:520px){.tab{font-size:16px;padding:8px 12px}}

/* 面板不再输出标题：tab 上已经写着「今日 / 晨检详报 / …」，页面上再来一遍是重复。
   每个面板只保留一行说明或更新时间。 */
.panel{padding:34px 0 40px;position:relative}
.panel[hidden]{display:none}
.lead{text-align:center;color:var(--ink2);font-size:15px}
.divider{width:200px;height:1px;margin:38px auto;background:linear-gradient(90deg,transparent,rgba(26,26,24,.18),transparent)}

/* 首屏只剩一行更新时间：进来第一眼要看到的是状态灯和待办，不是标题 */
.hero{text-align:center;padding:0}
.hero .sub{font-size:12.5px;color:var(--ink3);letter-spacing:.4px}
.hero + .secbar{margin-top:18px}
.panel#today-panel{padding-top:26px}
.seal{display:inline-block;margin-top:26px;background:var(--cinnabar);color:#fff;font-family:var(--f-brush);font-size:15px;letter-spacing:3px;padding:7px 18px;border-radius:2px}

.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:44px;text-align:center}
.stat .n{font-family:var(--f-brush);font-size:clamp(34px,4.6vw,46px);color:var(--ink)}
.stat .n em{font-style:normal;color:var(--cinnabar)}
.stat .l{font-size:13px;color:var(--ink3);margin-top:4px;letter-spacing:1px}

/* 今日状态灯：一眼看出有没有红的 */
.pulse{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:30px}
.pulse .p{background:var(--wash);padding:16px 18px;border-top:2px solid var(--line)}
.pulse .p.ok{border-top-color:var(--ok)}
.pulse .p.warn{border-top-color:var(--warn)}
.pulse .p.bad{border-top-color:var(--cinnabar)}
.pulse .p.na{border-top-color:var(--na)}
.pulse .pk{font-size:12px;color:var(--ink3);letter-spacing:.1em}
.pulse .pv{font-family:var(--f-brush);font-size:26px;line-height:1.3;margin-top:2px}
.pulse .pv.bad{color:var(--cinnabar)}.pulse .pv.warn{color:var(--warn)}
.pulse .pv.ok{color:var(--ok)}.pulse .pv.na{color:var(--na)}
.pulse .pn{font-size:11.5px;color:var(--ink3);margin-top:4px;line-height:1.6}

/* 需要你动手的事：按 P0 → 等你拍板 → 待办 排序，置顶于首屏 */
.acts{display:flex;flex-direction:column;gap:10px;margin-top:34px}
.grp{font-size:12.5px;letter-spacing:.14em;color:var(--ink3);margin-top:14px}
.grp.p0{color:var(--cinnabar)}
.grp.block{color:var(--warn)}
.grp:first-child{margin-top:0}
.act{display:flex;background:var(--wash);padding:16px 22px;border-left:3px solid var(--line)}
.act.p0{border-left-color:var(--cinnabar)}
.act.block{border-left-color:var(--warn)}
.act.todo{border-left-color:var(--na)}
.act .ab{flex:1;min-width:0}
.act .at{font-size:16px;line-height:1.75}
.act .ad{font-size:13.5px;color:var(--ink2);margin-top:6px;line-height:1.85}
.act .ad li{margin-left:18px;margin-bottom:2px}
.secbar{display:flex;align-items:baseline;gap:12px;margin-top:40px;flex-wrap:wrap}
.secbar + .pulse,.secbar + .acts,.secbar + .stats{margin-top:16px}
.secbar h3{font-family:var(--f-brush);font-size:24px;font-weight:400;letter-spacing:3px}
.secbar span{font-size:13px;color:var(--ink3)}

.quick{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:40px}
.qcard{display:block;background:var(--wash);border-left:3px solid var(--cinnabar);padding:24px 26px;transition:background .25s,transform .25s}
.qcard:hover{background:var(--wash2);transform:translateX(4px)}
.qcard .qt{font-family:var(--f-brush);font-size:24px;letter-spacing:2px}
.qcard .qd{font-size:13.5px;color:var(--ink2);margin-top:8px;line-height:1.85}
.qcard .qg{display:inline-block;margin-top:12px;font-size:13px;color:var(--cinnabar);letter-spacing:1px}

.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:44px}
.card{display:block;position:relative;background:var(--wash);padding:34px 22px 26px;text-align:center;transition:transform .25s,background .25s;overflow:hidden}
.card:hover{transform:translateY(-4px);background:var(--wash2)}
.card .ghost{position:absolute;top:-18px;right:8px;font-family:var(--f-brush);font-size:clamp(64px,12vw,96px);color:rgba(26,26,24,.05);line-height:1}
.card .cno{font-size:12px;color:var(--cinnabar);letter-spacing:2px}
.card .ctitle{display:block;font-family:var(--f-brush);font-size:26px;margin-top:8px;letter-spacing:2px}
.card .ccount{display:block;font-size:13px;color:var(--ink3);margin-top:6px}
.card .cdesc{display:block;font-size:13px;color:var(--ink2);margin-top:12px;line-height:1.7}

.scrollrow{display:flex;gap:16px;overflow-x:auto;padding:8px 0 20px;margin-top:40px;scroll-snap-type:x mandatory}
.wp{flex:0 0 300px;scroll-snap-align:start;text-align:center}
.wp img{width:100%;display:block;cursor:zoom-in;transition:transform .25s;aspect-ratio:16/9;object-fit:cover}
.wp img:hover{transform:translateY(-3px)}
.wp figcaption{margin-top:12px}
.wp .wn{font-family:var(--f-brush);font-size:22px;letter-spacing:3px}
.wp .wy{display:block;font-size:12px;color:var(--ink3);margin-top:2px}
.note{text-align:center;font-size:13px;color:var(--ink3);margin-top:6px}

.rules{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:40px}
.rule{background:var(--wash);padding:30px 24px;text-align:center}
.rule .rt{font-family:var(--f-brush);font-size:23px;letter-spacing:2px}
.rule .rd{font-size:14px;color:var(--ink2);margin-top:12px;line-height:1.85}
.rule .rn{display:inline-block;margin-bottom:14px;width:26px;height:26px;line-height:26px;background:var(--cinnabar);color:#fff;font-size:13px;border-radius:2px}

.excl{margin-top:44px;background:var(--wash);padding:30px 32px}
.excl h3{font-family:var(--f-brush);font-size:22px;letter-spacing:2px;font-weight:400}
.excl ul{margin-top:14px;padding-left:20px;font-size:14px;color:var(--ink2);line-height:2}
.excl .why{font-size:13px;color:var(--ink3);margin-top:12px}

/* 市场风向：结论卡 + 风向网格。类名一律 mw- 前缀，避免与 .grp/.act 的 ok/warn/bad 撞车 */
.mv{background:var(--wash);border-left:3px solid var(--cinnabar);padding:26px 30px;margin-top:18px}
.mv .mvt{font-family:var(--f-brush);font-size:25px;letter-spacing:2px;line-height:1.6}
.mv .mvd{font-size:15px;color:var(--ink2);margin-top:12px;line-height:1.95}
.mv.mv-ok{border-left-color:var(--ok)}
.mv.mv-warn{border-left-color:var(--warn)}
.mv.mv-bad{border-left-color:var(--cinnabar)}
/* 数据总览：三张柱状图并排。纯 CSS 无依赖，断网也能看，且不引第三方脚本。 */
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:16px;margin-top:16px}
.chart{background:var(--wash);padding:18px 20px 14px}
.chart .ct{font-size:12px;color:var(--ink3);letter-spacing:.1em}
.chart .cv{font-family:var(--f-brush);font-size:28px;line-height:1.3;margin-top:4px;
  font-variant-numeric:tabular-nums}
.chart .cv em{font-style:normal;color:var(--cinnabar)}
.chart .cb{display:flex;align-items:flex-end;justify-content:flex-start;gap:3px;height:84px;
  margin-top:14px;border-bottom:1px solid rgba(26,26,24,.1)}
/* max-width 是刻意的：小红书刚接入时只有 1 天数据，不加限制单根柱会撑满整行，看着像故障 */
.chart .col{flex:1;max-width:26px;min-height:2px;border-radius:2px 2px 0 0;
  background:var(--cinnabar);opacity:.82;transition:opacity .2s}
.chart .col:hover{opacity:1}
.chart .col.zero{background:rgba(26,26,24,.12)}
.chart .lab{display:flex;gap:3px;margin-top:5px}
.chart .lab span{flex:1;text-align:center;font-size:10px;color:var(--ink3);
  overflow:hidden;white-space:nowrap}
.chart .cn{font-size:12px;color:var(--ink2);margin-top:10px;line-height:1.7}
.chart .cn em{font-style:normal;color:var(--cinnabar)}
.ins{margin-top:16px}
.ins .mv{margin-top:12px;padding:18px 22px}
.ins .mvt{font-size:19px}
.ins .mvd{font-size:14px;margin-top:8px}
@media(max-width:640px){.charts{grid-template-columns:1fr}.chart .cv{font-size:24px}}
.winds{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-top:18px}
.wind{background:var(--wash);padding:22px 26px;border-top:2px solid var(--line)}
.wind .wt{font-family:var(--f-brush);font-size:21px;letter-spacing:1px;line-height:1.6}
.wind .wd{font-size:14px;color:var(--ink2);margin-top:10px;line-height:1.9}
.wind.mw-ok{border-top-color:var(--ok)}
.wind.mw-warn{border-top-color:var(--warn)}
.wind.mw-bad{border-top-color:var(--cinnabar)}
@media(max-width:820px){.winds{grid-template-columns:1fr}}

footer{text-align:center;padding:56px 0 80px;color:var(--ink3);font-size:13px;line-height:2;border-top:1px solid rgba(26,26,24,.1);margin-top:40px}
footer .fbrand{font-family:var(--f-brush);font-size:20px;color:var(--ink2);letter-spacing:4px}

.lb{position:fixed;inset:0;background:rgba(255,255,255,.97);display:none;align-items:center;justify-content:center;z-index:100;cursor:zoom-out;padding:24px}
.lb.on{display:flex}
.lb img{max-width:96vw;max-height:80vh}
.lb .cap{position:absolute;bottom:26px;text-align:center;font-family:var(--f-brush);font-size:22px;letter-spacing:3px}
.lb .cap span{display:block;font-family:var(--f-body);font-size:12px;color:var(--ink3);margin-top:4px}

@media (max-width:820px){
  .grid{grid-template-columns:repeat(2,1fr)}
  .rules{grid-template-columns:1fr}
  .stats{grid-template-columns:repeat(2,1fr)}
  .quick{grid-template-columns:1fr}
  .wp{flex:0 0 240px}
}
@media (max-width:520px){ .grid{grid-template-columns:1fr} }
""" + qjr.CSS_HOST

JS = """
var tabs=[].slice.call(document.querySelectorAll('.tab'));
var panels=[].slice.call(document.querySelectorAll('.panel'));
function show(id){
  tabs.forEach(function(t){
    var on=t.getAttribute('data-tab')===id;
    t.classList.toggle('on',on);
    t.setAttribute('aria-selected',on?'true':'false');
  });
  panels.forEach(function(p){ p.hidden = p.getAttribute('data-panel')!==id; });
  if(history.replaceState){ history.replaceState(null,'','#'+id); }
}
tabs.forEach(function(t){
  t.addEventListener('click',function(){ show(t.getAttribute('data-tab')); window.scrollTo(0,0); });
});
var h=(location.hash||'').replace('#','');
var ok=panels.some(function(p){ return p.getAttribute('data-panel')===h; });
show(ok?h:'today');

function openLb(u,n,y){
  document.getElementById('lbimg').src=u;
  var c=document.getElementById('lbcap');
  c.textContent='';
  var s=document.createElement('span');
  s.textContent=y;
  c.appendChild(document.createTextNode(n));
  c.appendChild(s);
  document.getElementById('lb').classList.add('on');
}
function closeLb(){document.getElementById('lb').classList.remove('on');}
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeLb();}});
""" + qjr.js("host")


def esc(s):
    return html.escape(str(s))


def md_plain(s):
    """去掉 markdown 强调与代码标记，只留纯文本（随后统一 esc）。"""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s.strip()


def load_actions():
    """从 NOW.md 解析「需要你动手的事」。

    刻意不另建 action-items.json：NOW.md 本来就是每次收工必写的当前状态，
    再开一份真源必然双份漂移（这正是我们一直在消除的东西）。
    解析三段：`🔴 正在进行` → 立即处理 ｜ `⛔ 阻塞/拍板` → 等你拍板 ｜ `▶️ 下一步` → 待办。
    """
    if not os.path.exists(NOW_MD):
        return []
    text = open(NOW_MD, encoding="utf-8", errors="ignore").read()
    out = []
    for blk in re.split(r"^## ", text, flags=re.M):
        head = blk.splitlines()[0] if blk.splitlines() else ""
        if "正在进行" in head:
            lvl = "p0"
        elif "阻塞" in head or "拍板" in head:
            lvl = "block"
        elif "下一步" in head:
            lvl = "todo"
        else:
            continue
        items = []
        if lvl == "p0":
            cur = None
            for ln in blk.splitlines()[1:]:
                m = re.match(r"^\d+\.\s+(.+)$", ln.strip())
                if m:
                    if cur:
                        items.append(cur)
                    cur = {"t": md_plain(m.group(1)), "d": []}
                elif cur and ln.strip().startswith("- "):
                    cur["d"].append(md_plain(ln.strip()[2:]))
            if cur:
                items.append(cur)
        elif lvl == "todo":
            for ln in blk.splitlines()[1:]:
                m = re.match(r"^- \[ \] (.+)$", ln.strip())
                if m:
                    items.append({"t": md_plain(m.group(1)), "d": []})
        else:  # 阻塞表：| 事项 | 需要你决定 | 不决定的代价 |
            for ln in blk.splitlines()[1:]:
                ln = ln.strip()
                if not ln.startswith("|"):
                    continue
                cells = [c.strip() for c in ln.strip("|").split("|")]
                if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0] in ("事项",):
                    continue
                items.append({"t": md_plain(cells[0]),
                              "d": [md_plain(c) for c in cells[1:] if c and c != "—"]})
        for it in items:
            if "——" in it["t"]:      # 「标题 —— 说明」拆成两行更好读
                a, _, b = it["t"].partition("——")
                it["t"], it["d"] = a.strip(), [b.strip()] + it["d"]
            out.append({"lv": lvl, "t": it["t"], "d": it["d"]})
    out.sort(key=lambda a: {"p0": 0, "block": 1, "todo": 2}[a["lv"]])
    return out


def render_acts(acts):
    """按级别分组：首屏先看到「立即处理」，常规待办排在最后。
    分组而不用徽标，是为了让「眼下该做什么」一眼可读，而不是 12 条平铺。"""
    if not acts:
        return '<p class="lead">NOW.md 里目前没有待办项。</p>'
    groups = [("p0", "立即处理"), ("block", "等你拍板"), ("todo", "常规待办")]
    out = ['<div class="acts">']
    for lv, label in groups:
        sub = [a for a in acts if a["lv"] == lv]
        if not sub:
            continue
        out.append(f'<div class="grp {lv}">{label}　·　{len(sub)} 项</div>')
        for a in sub:
            det = "".join(f"<li>{esc(d)}</li>" for d in a["d"])
            det = f"<ul class='ad'>{det}</ul>" if det else ""
            out.append(f'<div class="act {lv}"><div class="ab">'
                       f'<div class="at">{esc(a["t"])}</div>{det}</div></div>')
    out.append("</div>")
    return "".join(out)


def load_pulse():
    """今日状态灯。复用晨检脚本的取数函数：零联网、零额外实现、口径不会两边跑偏。"""
    st = bmb.load_status()
    tr = bmb.load_traffic()
    ds = bmb.load_deepseek()
    cr = bmb.load_credits()
    items = []

    http = st.get("http_code")
    items.append({"k": "站点", "v": http or bmb.NA,
                  "cls": "ok" if http == "200" else ("na" if not http else "bad"),
                  "n": st.get("http_note") or "首页响应"})

    ssl = st.get("ssl_days")
    items.append({"k": "证书剩余", "v": f"{ssl} 天" if ssl is not None else bmb.NA,
                  "cls": "ok" if (ssl or 0) >= 30 else ("bad" if ssl is not None else "na"),
                  "n": st.get("ssl_not_after") or "Cloudflare 签发"})

    if tr.get("ok"):
        jt = f"较前一日 {tr['jump']:+d}%" if tr["jump"] is not None else tr["date"]
        # 跳变 50% 用 warn（看一眼）而非 bad（故障）：数据不满 2 周本就不下趋势结论
        cls = "warn" if (tr["jump"] is not None and abs(tr["jump"]) >= 50) else "ok"
        items.append({"k": "访次（净）",
                      "v": tr["clean"] if tr["clean"] is not None else bmb.NA,
                      "cls": cls, "n": jt})
    else:
        items.append({"k": "访次（净）", "v": bmb.NA, "cls": "na", "n": "无站点数据"})

    if cr.get("balance"):
        b = cr["balance"]
        cls, note = "ok", f"快照 {b['date']}"
        if not b["val"] or "未取到" in str(b["val"]):
            # 取数失败不能显示成绿色正常，否则等于用旧值冒充当日
            cls, note = "na", "自动取数暂不可用，请看客户端左下角余额"
        else:
            try:
                lag = (date.today() - datetime.strptime(b["date"], "%Y-%m-%d").date()).days
                if lag >= 1:
                    cls, note = "warn", f"快照 {b['date']}（{lag} 天前）"
            except ValueError:
                pass
        items.append({"k": "积分余额", "v": b["val"], "cls": cls, "n": note})
    else:
        items.append({"k": "积分余额", "v": bmb.NA, "cls": "na", "n": "账本未读到"})

    if ds.get("ok"):
        cls = "bad" if ds["total"] < 20 else "ok"
        note = f"较上次 {ds['drop']:+.2f} 元" if ds["drop"] is not None else ds["date"]
        if ds.get("lag") and ds["lag"] >= 3:
            cls = "warn"
            note += f" · {ds['lag']} 天未记账"
        items.append({"k": "DeepSeek", "v": f"¥{ds['total']:.2f}", "cls": cls, "n": note})
    else:
        items.append({"k": "DeepSeek", "v": bmb.NA, "cls": "na", "n": ""})

    # 名单是 Y1 唯一瓶颈，放进首屏状态灯 —— 来人时一眼看见，不用切 tab
    sb = load_json(SUBS_JSON, {})
    if sb.get("ok"):
        nt = sb.get("new_today") or 0
        last = (sb.get("last_subscribe_at") or "")[5:16] or "—"
        v = f"{sb.get('total')} 人" + (f"（今日 +{nt}）" if nt else "")
        items.append({"k": "订阅名单", "v": v, "cls": "ok",
                      "n": f"最近一次 {last}"})
    else:
        items.append({"k": "订阅名单", "v": bmb.NA, "cls": "na", "n": "未接 MailerLite API"})
    return items


def render_pulse(items):
    # id 供刷新按钮拿到新数据后原地重绘（不重载整页也能更新状态灯）
    out = ['<div class="pulse" id="qj-pulse">']
    for it in items:
        out.append(f'<div class="p {it["cls"]}"><div class="pk">{esc(it["k"])}</div>'
                   f'<div class="pv {it["cls"]}">{esc(it["v"])}</div>'
                   f'<div class="pn">{esc(it["n"])}</div></div>')
    out.append("</div>")
    return "".join(out)


def load_market():
    """市场风向面板的数据源：`11-运营/data/market-watch.json`。

    刻意让「结论写在报告文档里、工作台读同一份 JSON」：
    JSON 由月度竞品扫描自动化更新，本脚本只消费不生产，
    避免工作台显示另一套口径（真源漂移正是我们一直在消除的东西）。
    """
    return load_json(MW_JSON, {})


MW_GROUPS = [("now", "立刻做　·　零成本"), ("not", "不要做　·　已否掉"),
             ("later", "触发才动　·　记着")]


def render_market(mw):
    """四段式：一句结论 → 关键数据 → 风向 → 应对 → 战略走向 → 观测清单。

    排序与今日 tab 同构（先判断、后数据、再动作），
    这样扫一眼就能决定"这个月有没有需要我改方向的"。"""
    if not mw:
        return ('<p class="lead">尚未生成 <code>market-watch.json</code>。'
                '跑一次月度竞品扫描即可出现在这里。</p>')

    out = []
    v = mw.get("verdict", {})
    lvl = v.get("level", "ok")

    out.append('<div class="secbar"><h3>一句结论</h3><span>'
               f'{esc(mw.get("updated", "—"))} 扫描　·　'
               f'下次 {esc(mw.get("next_scan", "—"))}</span></div>')
    out.append(f'<div class="mv mv-{esc(lvl)}">'
               f'<div class="mvt">{esc(v.get("headline", ""))}</div>'
               f'<div class="mvd">{esc(v.get("detail", ""))}</div></div>')

    ms = mw.get("metrics", [])
    if ms:
        out.append(f'<div class="secbar"><h3>关键数据</h3>'
                   f'<span>{len(ms)} 项 · 每月可追踪</span></div>')
        out.append('<div class="pulse">')
        for it in ms:
            c = it.get("cls", "na")
            out.append(f'<div class="p {esc(c)}">'
                       f'<div class="pk">{esc(it.get("k", ""))}</div>'
                       f'<div class="pv {esc(c)}">{esc(it.get("v", ""))}</div>'
                       f'<div class="pn">{esc(it.get("n", ""))}</div></div>')
        out.append("</div>")

    ws = mw.get("winds", [])
    if ws:
        out.append(f'<div class="secbar"><h3>风向</h3>'
                   f'<span>环境在往哪边变 · {len(ws)} 条</span></div>')
        out.append('<div class="winds">')
        for w in ws:
            c = w.get("cls", "ok")
            out.append(f'<div class="wind mw-{esc(c)}">'
                       f'<div class="wt">{esc(w.get("t", ""))}</div>'
                       f'<div class="wd">{esc(w.get("d", ""))}</div></div>')
        out.append("</div>")

    mvs = mw.get("moves", [])
    if mvs:
        out.append('<div class="secbar"><h3>我们的应对</h3>'
                   f'<span>共 {len(mvs)} 条 · 按能不能现在动排序</span></div>')
        out.append('<div class="acts">')
        for lv, label in MW_GROUPS:
            sub = [m for m in mvs if m.get("lv") == lv]
            if not sub:
                continue
            out.append(f'<div class="grp {esc(lv)}">{label}　·　{len(sub)} 项</div>')
            for m in sub:
                det = "".join(f"<li>{esc(d)}</li>" for d in m.get("d", []))
                det = f"<ul class='ad'>{det}</ul>" if det else ""
                out.append(f'<div class="act {esc(lv)}"><div class="ab">'
                           f'<div class="at">{esc(m.get("t", ""))}</div>{det}</div></div>')
        out.append("</div>")

    st = mw.get("strategy", [])
    if st:
        out.append('<div class="secbar"><h3>战略走向</h3>'
                   '<span>不随月度结论改，只在前提变了才动</span></div>')
        out.append('<div class="rules">')
        for s in st:
            out.append(f'<div class="rule"><span class="rn">{esc(s.get("n", ""))}</span>'
                       f'<div class="rt">{esc(s.get("t", ""))}</div>'
                   f'<div class="rd">{esc(s.get("d", ""))}</div></div>')
        out.append("</div>")

    wl = mw.get("watchlist", [])
    if wl:
        out.append('<div class="excl"><h3>下次扫什么</h3><ul>')
        for w in wl:
            out.append(f"<li>{esc(w)}</li>")
        out.append('</ul></div>')

    return "".join(out)


def load_traffic():
    """站点流量的两个数据源：
      · 明细-latest.json —— 最近一次采集的 4 天窗口明细（页面/国家/设备）
      · 站点数据.csv     —— 15 天逐日汇总，每日 upsert
    """
    import csv as _csv
    detail = load_json(TRAF_JSON, {})
    rows = []
    if os.path.exists(TRAF_CSV):
        try:
            with open(TRAF_CSV, encoding="utf-8") as f:
                rows = list(_csv.DictReader(f))
        except Exception:
            rows = []
    # CSV 是日期【倒序】写的（新的在前），而下面所有切片都按「越往后越近」来取。
    # 不排序的话 rows[-8:] 取到的是最旧的 8 天 —— 逐日列表和柱状图都会画错时间段。
    try:
        rows.sort(key=lambda r: r.get("date", ""))
    except Exception:
        pass
    return detail, rows


def _num(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _fmt(n):
    """整数加千分位、小数保留一位 —— 柱状图 hover 上要显示原始值。"""
    try:
        f = float(n)
        return f"{int(f):,}" if f == int(f) else f"{f:,.1f}"
    except Exception:
        return str(n)


def render_traffic(detail, rows):
    """一句话结论 → 关键数字 → 逐日 → 真人页 → 人与设备 → 口径说明。

    口径纪律（与晨检一致）：
      · 「真人访次」= Cloudflare 的 visits_clean，已剔除已知爬虫；
        但免费版 bot 分类不完整，所以它还偏乐观，页面里如实标注。
      · 没数据就写「本次未提供」，不编造。
    """
    if not detail and not rows:
        return ('<p class="lead">尚未采集流量数据。'
                '跑一次 <code>11-运营/scripts/cf-analytics.py collect</code> 即可出现在这里。</p>')

    cln = detail.get("visits_clean_total", 0)
    bot = detail.get("visits_bot_total", 0)
    tot = (cln + bot) or 1
    noise = bot / tot * 100
    # ⚠️ detail 是 4 天窗口的汇总，rows 是 CSV 里累积的逐日。
    # 日均必须用【CSV 总和 ÷ CSV 天数】，不能拿 4 天窗口的数去除 15 天。
    try:
        csv_cln = sum(int(r.get("visits_clean") or 0) for r in rows)
        csv_days = len([r for r in rows if r.get("date")])
    except Exception:
        csv_cln, csv_days = cln, 4
    csv_days = csv_days or 4
    per_day = csv_cln / csv_days
    ts = detail.get("collected_at", "—")

    out = []

    # ── 一句结论 ──
    out.append('<div class="secbar"><h3>一句结论</h3>'
               f'<span>{esc(ts)} 采集　·　每日 06:30 自动更新</span></div>')
    out.append('<div class="mv mv-ok">'
               f'<div class="mvt">真人访次约 {_num(round(per_day))} / 天，'
               f'噪声占 {noise:.0f}%</div>'
               '<div class="mvd">噪声 = 爬虫 + 系统请求。'
               'WAF 已挡掉一批扫描器（返回 403 不进统计），'
               '但 Cloudflare 免费版的 bot 分类不完整，下面「真人页」里仍可能混入少量扫描器。</div></div>')

    # ── 关键数字 ──
    out.append('<div class="secbar"><h3>关键数字</h3>'
               f'<span>近 4 天窗口　·　累计已采 {csv_days} 天　·　"真人"口径偏乐观</span></div>')
    out.append('<div class="stats">')
    out.append(f'<div class="stat"><div class="n"><em>{_num(cln)}</em></div>'
               '<div class="l">真人访次</div></div>')
    out.append(f'<div class="stat"><div class="n">{_num(bot)}</div>'
               '<div class="l">爬虫与系统</div></div>')
    out.append(f'<div class="stat"><div class="n">{noise:.0f}<em>%</em></div>'
               '<div class="l">噪声占比</div></div>')
    out.append(f'<div class="stat"><div class="n">{_num(round(per_day))}</div>'
               '<div class="l">日均真人访次</div></div>')
    out.append('</div>')

    # ── 逐日 ──
    if rows:
        out.append('<div class="secbar"><h3>逐日</h3>'
                   f'<span>最近 {min(len(rows), 8)} 天（已累计 {len(rows)} 天）　·　越往下越早</span></div>')
        out.append('<div class="winds">')
        for r in reversed(rows[-8:]):
            d = r.get("date", "—")
            cr = r.get("visits_clean", "—")
            vv = r.get("visits", "—")
            bp = r.get("bot_pct", "—")
            cs = (r.get("countries_top5") or "").replace(" ", " · ")[:44]
            out.append(f'<div class="wind mw-ok"><div class="wt">{esc(d)}'
                       f'　真人 {esc(cr)} / 总 {esc(vv)}　噪声 {esc(bp)}%</div>'
                       f'<div class="wd">{esc(cs)}</div></div>')
        out.append('</div>')

    # ── 真人看的页 ──
    pages = [p for p in detail.get("clean_pages", []) if not is_junk(p.get("path", ""))]
    if pages:
        out.append('<div class="secbar"><h3>真人在看哪些页</h3>'
                   f'<span>Top {min(len(pages), 10)}　·　已剔除扫描器路径</span></div>')
        out.append('<div class="winds">')
        for p in pages[:10]:
            out.append(f'<div class="wind mw-ok">'
                       f'<div class="wt">{esc(path_cn(p.get("path", "")))}'
                       f'　<em>{esc(p.get("visits", 0))}</em> 次</div>'
                       f'<div class="wd"><code>{esc(p.get("path", ""))}</code></div></div>')
        out.append('</div>')

    # ── 人与设备 ──
    cs = detail.get("countries", [])
    dp = detail.get("devices_pct", {})
    if cs or dp:
        out.append('<div class="secbar"><h3>人从哪来 · 用什么设备</h3>'
                   '<span>国家含爬虫来源，仅供参考</span></div>')
        out.append('<div class="winds">')
        if cs:
            top = " · ".join(f"{c} {_num(v)}" for c, v in cs[:6])
            out.append(f'<div class="wind mw-ok"><div class="wt">国家</div>'
                       f'<div class="wd">{esc(top)}</div></div>')
        if dp:
            dev = " · ".join(f"{k} {v}%" for k, v in dp.items())
            out.append(f'<div class="wind mw-ok"><div class="wt">设备</div>'
                       f'<div class="wd">{esc(dev)}</div></div>')
        out.append('</div>')

    # ── 口径说明 ──
    out.append('<p class="note">'
               '「真人访次」来自 Cloudflare Zone Analytics 的 visits（同 IP 30 分钟内去重）；'
               '免费版不给 bot 分类维度，也不给 referer，所以这里只能做到「剔除已知爬虫」，'
               '真实人数会低于显示值。<br>'
               '数据每天 06:30 随晨检采集；Cloudflare 只回溯约 3–4 天，'
               '历史靠 <code>站点数据.csv</code> 逐日累积，断采即永久丢失。</p>')
    return "".join(out)


def load_subs():
    """订阅面板的两个数据源：
      · 订阅-latest.json —— 最近一次采集的快照（总数/分组/最近一次订阅时间/近 14 天）
      · 订阅数据.csv     —— 逐日累积（每天一行，同日覆盖）
    """
    import csv as _csv
    snap = load_json(SUBS_JSON, {})
    rows = []
    if os.path.exists(SUBS_CSV):
        try:
            with open(SUBS_CSV, encoding="utf-8") as f:
                rows = list(_csv.DictReader(f))
        except Exception:
            rows = []
    return snap, rows


def render_subs(snap, rows):
    """一句结论 → 关键数字 → 分组 → 近 14 天 → 口径说明。

    纪律：
      · 只显示数量与时间。**是谁一律回 MailerLite 后台看**，本页不落任何一个邮箱地址
        （沿用 10-09 定的隐私红线：订阅者邮箱不上云、不进 Git、不进台账）。
      · 取不到就写清怎么补上，绝不拿旧数冒充本次。
    """
    if not snap.get("ok"):
        return ('<p class="lead">订阅数据还没接上。三步（一次性的事）：<br>'
                '① MailerLite 后台 → Integrations → Developer API → 生成一个 token<br>'
                '② 终端执行 <code>security add-generic-password -a theseventhrealm '
                '-s mailerlite -U -w "&lt;Token&gt;"</code><br>'
                '③ 跑一次 <code>11-运营/scripts/mailerlite-stats.py collect</code><br>'
                '之后每轮刷新会自动带上，这里就开始有数了。</p>')

    total = snap.get("total")
    nt = snap.get("new_today") or 0
    n7 = snap.get("new_7d") or 0
    last = snap.get("last_subscribe_at") or "—"
    ts = snap.get("collected_at", "—")
    delta = snap.get("delta")
    active = snap.get("active")
    unconf = snap.get("unconfirmed") or 0

    out = []
    # ── 一句结论 ──
    out.append('<div class="secbar"><h3>一句结论</h3>'
               f'<span>{esc(ts)} 采集　·　随每轮刷新更新</span></div>')
    if nt > 0:
        # 名单是 Y1 唯一瓶颈，来人是大事 —— 用朱红条（本命色）而不是绿色 OK 条
        out.append('<div class="mv">'
                   f'<div class="mvt">今日新增 {nt} 人　·　名单共 {_num(total)} 人</div>'
                   '<div class="mvd">最近一次有人留邮箱是 '
                   f'{esc(last)}。<br>'
                   '要看是谁，去 MailerLite 后台 —— 本页刻意不显示邮箱地址。</div></div>')
    else:
        out.append('<div class="mv mv-ok">'
                   f'<div class="mvt">今日暂无新增　·　名单共 {_num(total)} 人</div>'
                   f'<div class="mvd">最近一次有人留邮箱是 {esc(last)}。'
                   '留邮箱的人要点了确认信才会进组、才会触发交付邮件，'
                   '所以「总数」和「能收到邮件的人」不是一回事。</div></div>')

    # ── 关键数字 ──
    out.append('<div class="secbar"><h3>关键数字</h3>'
               '<span>今日新增按订阅时间统计，与采集时刻无关</span></div>')
    out.append('<div class="stats">')
    out.append(f'<div class="stat"><div class="n"><em>{_num(total)}</em></div>'
               '<div class="l">名单总数</div></div>')
    out.append(f'<div class="stat"><div class="n">{_num(nt)}</div>'
               '<div class="l">今日新增</div></div>')
    out.append(f'<div class="stat"><div class="n">{_num(n7)}</div>'
               '<div class="l">近 7 日新增</div></div>')
    out.append(f'<div class="stat"><div class="n">{_num(unconf)}</div>'
               '<div class="l">未点确认信</div></div>')
    out.append('</div>')

    # ── 分组 ──
    groups = [g for g in snap.get("groups", []) if isinstance(g, dict)]
    if groups:
        out.append('<div class="secbar"><h3>分组</h3>'
                   '<span>组名与 MailerLite 后台一致</span></div>')
        out.append('<div class="winds">')
        for g in groups[:8]:
            out.append('<div class="wind mw-ok">'
                       f'<div class="wt">{esc(g.get("name", "—"))}'
                       f'　<em>{_num(g.get("count"))}</em> 人</div>'
                       '<div class="wd">组名是分组基准，与 <code>README-空间结构.md</code> '
                       '口径必须一字不差</div></div>')
        out.append('</div>')

    # ── 近 14 天 ──
    daily = [d for d in snap.get("daily", []) if isinstance(d, dict)]
    if daily:
        out.append('<div class="secbar"><h3>近 14 天</h3>'
                   '<span>只列有人来的日子　·　越往下越早</span></div>')
        out.append('<div class="winds">')
        hit = [d for d in daily if d.get("n")]
        if not hit:
            out.append('<div class="wind"><div class="wt">这 14 天还没有人留邮箱</div>'
                       '<div class="wd">表单在 <code>/collection/</code> 与 21 个内容页上</div></div>')
        for d in reversed(hit[-14:]):
            out.append(f'<div class="wind mw-ok"><div class="wt">{esc(d.get("date", "—"))}'
                       f'　<em>{_num(d.get("n"))}</em> 人</div>'
                       '<div class="wd">留邮箱 → 点确认信 → 进组 → 触发交付邮件</div></div>')
        out.append('</div>')

    # ── 口径 ──
    lag = ""
    if delta:
        lag = f"较上次采集 {delta:+d} 人。"
    out.append('<p class="note">'
               f'{esc(lag)}'
               '总数来自 MailerLite API；「今日新增」按订阅者创建时间统计，'
               '不受采集频率影响 —— 中午来的人，中午那一轮就能看到。<br>'
               '🔴 隐私：本页与所有台账只存数量与时间，'
               '<b>不落任何一个邮箱地址</b>；要看是谁去 MailerLite 后台。</p>')
    return "".join(out)


def load_xhs_series(n=14):
    """小红书逐日曝光：来自 xhs-账号数据.csv（每天晨检采一次，按日期 upsert）。

    只有 1 天数据时不画趋势线（一个点画不成趋势），但数字照常显示。
    """
    import csv as _csv
    if not os.path.exists(XHS_ACCT_CSV):
        return []
    try:
        with open(XHS_ACCT_CSV, encoding="utf-8") as f:
            rows = list(_csv.DictReader(f))
    except Exception:
        return []
    out = []
    for r in rows[-n:]:
        try:
            v = int(str(r.get("曝光数") or "0").replace(",", ""))
        except ValueError:
            continue
        out.append({"d": r.get("日期", ""), "v": v})
    return out


def load_credit_series(n=14):
    """积分逐日消耗：解析积分账本表格。

    账本行形如 `| 2026-10-18 | **391.17** | 265.56 | … |`，
    消耗列可能是 `—`（没填）或小数。解析不出来就跳过该日，不猜。
    """
    import re as _re
    if not os.path.exists(LEDGER_MD):
        return []
    out = []
    pat = _re.compile(r'^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*\*{0,2}([\d.,]+)\*{0,2}\s*\|\s*([^|]*)\|')
    try:
        with open(LEDGER_MD, encoding="utf-8") as f:
            for line in f:
                m = pat.match(line)
                if not m:
                    continue
                used = (m.group(3) or "").strip()
                try:
                    v = float(used.replace(",", ""))
                except ValueError:
                    continue      # 「—」之类没记的数不补 0，0 会被误读成「今天没花钱」
                out.append({"d": m.group(1), "v": v, "bal": m.group(2)})
    except Exception:
        return []
    return out[-n:]


def render_chart(title, value, unit, series, note=""):
    """一张柱状图。series = [{"d":"2026-10-13","v":273}]，最多画 14 根。"""
    s = series[-14:]
    mx = max((x["v"] for x in s), default=0) or 1
    bars = "".join(
        f'<div class="col{" zero" if x["v"] == 0 else ""}" '
        f'style="height:{max(3, round(x["v"] / mx * 100))}%" '
        f'title="{esc(x["d"])}　{_fmt(x["v"])}"></div>' for x in s)
    lab = "".join(f'<span>{esc(x["d"][5:].replace("-", "/"))}</span>' for x in s)
    if not s:
        bars = '<div class="cn">暂无逐日数据</div>'
        lab = ""
    return (f'<div class="chart"><div class="ct">{esc(title)}</div>'
            f'<div class="cv"><em>{esc(str(value))}</em>{esc(unit)}</div>'
            f'<div class="cb">{bars}</div><div class="lab">{lab}</div>'
            f'<div class="cn">{note}</div></div>')


def render_insight(tr, xhs, cred, subs_snap):
    """把所有重要数据归拢成几条判断。

    纪律：只写能从数据直接读出来的东西 —— 不编趋势、不做预测。
    「数据不满 2 周不下趋势结论」这条口径与晨检一致，这里同样遵守。
    """
    out = []
    add = lambda lv, t, d: out.append(
        f'<div class="mv mv-{lv}"><div class="mvt">{t}</div><div class="mvd">{d}</div></div>')

    # ── 站点 ──
    s = tr.get("series") or []
    if s:
        last7 = s[-7:]
        a = sum(x["v"] for x in last7) / len(last7)
        prev7 = s[-14:-7]
        botp = tr.get("bot")
        if len(s) >= 14 and prev7:
            b = sum(x["v"] for x in prev7) / len(prev7)
            chg = (a - b) / b * 100 if b else 0
            lv = "ok" if abs(chg) < 30 else ("warn" if abs(chg) < 50 else "bad")
            trend = (f"近 7 日 <em>{a:.0f}</em> / 天，前 7 日 {b:.0f} / 天，"
                     f"{'涨' if chg >= 0 else '跌'} {abs(chg):.0f}%")
        else:
            lv = "ok"
            trend = (f"近 {len(last7)} 日 <em>{a:.0f}</em> / 天"
                     f"　·　累计 {len(s)} 天，不足 14 天暂不下趋势结论")
        noise = f"噪声 {botp}%" if botp is not None else "噪声未知"
        top = f"{tr.get('top1')} {tr.get('top1v')} 次" if tr.get("top1") else "—"
        add(lv, "站点", f"{trend}　·　{noise}　·　内容页 Top1 {esc(top)}。"
                        f"噪声低于 30% 时这些数可以信；高于 50% 时先看是不是被扫了，别当结论。")

    # ── 小红书 ──
    if xhs.get("ok"):
        ov = xhs.get("overview") or {}
        dg = xhs.get("diag") or {}
        fn = xhs.get("fans") or {}
        e, v = ov.get("exposure") or 0, ov.get("views") or 0
        ctr = ov.get("ctr") or "—"
        nf = dg.get("newFans") or 0
        rate = (v / e * 100) if e else 0
        cost = f"　·　约 {e // nf:,} 次曝光换 1 个粉丝" if nf and e else ""
        add("ok", "小红书",
            f"近 7 日曝光 <em>{e:,}</em>　·　观看 {v:,}（曝光转化率 {rate:.1f}%）　·　"
            f"封面点击率 {esc(ctr)}　·　涨粉 {nf}　·　总粉丝 {fn.get('total')}{cost}。"
            f"封面点击率说明封面好不好；它不低但涨粉为 0，说明钩子不行，不是内容不行。")
    else:
        add("na", "小红书", "本次未取到数据（Chrome 未开或掉登录）。7 天滚动窗口，断一天缺一天。")

    # ── 积分 ──
    if cred:
        used7 = [x["v"] for x in cred[-7:] if x["v"] > 0]
        bal = cred[-1].get("bal") if cred else None
        if used7:
            avg = sum(used7) / len(used7)
            heavy = [v for v in used7 if v > 100]
            normal = [v for v in used7 if v <= 100]
            navg = sum(normal) / len(normal) if normal else None
            run = None
            try:
                b0 = float(str(bal).replace(",", ""))
                run = b0 / (navg or avg)
            except (TypeError, ValueError):
                pass
            lv = "warn" if (run is not None and run < 15) else "ok"
            # 含重活日的均值会算出「2 天见底」这种伪警报，所以两个口径都给
            detail = f"近 {len(used7)} 日均耗 {avg:.1f} 分/天"
            if heavy and navg is not None:
                detail += (f"（含 {len(heavy)} 个重活日，单日最高 {max(heavy):.0f} 分）；"
                           f"剔除重活日后 <em>{navg:.1f}</em> 分/天")
            add(lv, "积分",
                f"余额 <em>{esc(str(bal))}</em>　·　{detail}"
                + (f"　·　按日常节奏约 {run:.0f} 天见底" if run else "")
                + "。跑道 &lt;15 天就停批量出图与视频。")

    # ── 订阅 ──
    if subs_snap.get("ok"):
        n = subs_snap.get("total") or 0
        nt = subs_snap.get("new_today") or 0
        add("ok" if n else "warn", "订阅名单",
            f"<em>{n}</em> 人" + (f"（今日 +{nt}）" if nt else "") +
            "　·　这是 Y1 唯一瓶颈：内容再多，没人留下联系方式就等于没发生。")

    return "".join(out) if out else ""


def render_xhs(x):
    """小红书创作服务平台 · 近 7 日滚动窗口。

    口径纪律（与站点流量一致）：
      · 创作服务平台只给「近 7 天 / 近 30 天」滚动窗口，断一天就永久缺一天
        ⇒ 每天随晨检采一次，采集脚本 11-运营/scripts/xhs-stats.sh。
      · 数据直接取页面渲染值，不做估算；取不到就写「本次未提供」，不编造。
    """
    if not x.get("ok"):
        return ('<p class="lead">尚未采集小红书数据。跑一次 '
                '<code>11-运营/scripts/xhs-stats.sh</code>'
                '（需先 <code>start-xhs-browser.sh</code> 登录一次）即可出现在这里。</p>')

    def n(v):
        return f"{v:,}" if isinstance(v, (int, float)) else "—"

    ov = x.get("overview") or {}
    dg = x.get("diag") or {}
    fn = x.get("fans") or {}
    mm = x.get("mom") or {}
    notes = x.get("notes") or []

    out = []
    out.append('<div class="secbar"><h3>一句结论</h3>'
               f'<span>{esc(x.get("fetchedAt", "—"))} 采集　·　'
               f'统计周期 {esc(x.get("period") or "—")}　·　每天 06:30 随晨检更新</span></div>')
    out.append('<div class="mv mv-ok">'
               f'<div class="mvt">近 7 日曝光 {n(ov.get("exposure"))}　·　'
               f'观看 {n(ov.get("views"))}　·　封面点击率 {esc(ov.get("ctr") or "—")}</div>'
               '<div class="mvd">曝光与观看是「被看到多少」，封面点击率才是「封面好不好」——'
               '点击率低说明内容没问题、封面不行；点击率不低但涨粉为 0，'
               '说明看完了没理由关注你，钩子得改。</div></div>')

    out.append('<div class="secbar"><h3>关键数字</h3><span>近 7 日 · 环比见小字</span></div>')
    out.append('<div class="stats">')
    for val, lab, sub in [
        (n(ov.get("exposure")), "曝光", f"环比 {esc(mm.get('exposure') or '—')}"),
        (n(ov.get("views")), "观看", f"环比 {esc(mm.get('views') or '—')}"),
        (esc(ov.get("ctr") or "—"), "封面点击率", f"环比 {esc(mm.get('ctr') or '—')}"),
        (n(fn.get("total")), "总粉丝", f"近 7 日涨粉 {n(dg.get('newFans'))}"),
    ]:
        out.append(f'<div class="stat"><div class="n"><em>{val}</em></div>'
                   f'<div class="l">{esc(lab)}</div>'
                   f'<div class="l" style="font-size:12px;opacity:.75">{sub}</div></div>')
    out.append('</div>')

    out.append('<div class="secbar"><h3>账号诊断</h3><span>与同类创作者相比</span></div>')
    out.append(
        '<div class="mv"><div class="mvd">'
        f'主页访客 {n(dg.get("profileVisits"))}　·　发布 {n(dg.get("published"))} 篇　·　'
        f'互动 {n(dg.get("interactions"))}　·　涨粉 {n(dg.get("newFans"))}　·　'
        f'平均观看 {esc(ov.get("avgWatch") or "—")}　·　观看总时长 {esc(ov.get("totalWatch") or "—")}'
        '</div></div>')

    if notes:
        out.append('<div class="secbar"><h3>笔记明细</h3>'
                   f'<span>共 {len(notes)} 篇 · 近半年发布</span></div>')
        for nt in notes[:6]:
            out.append(
                '<div class="mv"><div class="mvt" style="font-size:20px">'
                f'{esc(nt.get("title") or "—")}</div>'
                '<div class="mvd">'
                f'{esc((nt.get("publishedAt") or "—")[:10])} 发布　·　'
                f'曝光 {n(nt.get("exposure"))}　·　观看 {n(nt.get("views"))}　·　'
                f'点击率 {esc(nt.get("ctr") or "—")}<br>'
                f'赞 {n(nt.get("likes"))}　·　藏 {n(nt.get("collects"))}　·　'
                f'评 {n(nt.get("comments"))}　·　分享 {n(nt.get("shares"))}　·　'
                f'涨粉 {n(nt.get("newFans"))}　·　人均观看 {esc(nt.get("avgWatch") or "—")}'
                '</div></div>')

    out.append('<p class="note" style="margin-top:22px">数字取自小红书创作服务平台页面原值，'
               '不做估算；7 天滚动窗口，断一天缺一天，所以每天必采。</p>')
    return "".join(out)


def build():
    gallery = ""
    for slug, name, year in ORDER:
        u = img(f"{slug}-1920x1080.png") or img(f"{slug}-1400.png")
        if not u:
            continue
        gallery += (f'      <figure class="wp" onclick="openLb(\'{u}\',\'{name}\',\'{year}\')">\n'
                    f'        <img src="{u}" alt="{name}·字形演变壁纸" width="1920" height="1080" loading="lazy">\n'
                    f'        <figcaption><span class="wn">{name}</span><span class="wy">{year}</span></figcaption>\n'
                    f'      </figure>\n')

    cards = ""
    for no, title, cnt, desc, key in SECTIONS:
        nid = F.get(key, "")
        cards += (f'      <a class="card" href="https://www.workbuddy.cn/space/d/{nid}" target="_blank" rel="noopener">\n'
                  f'        <span class="ghost">{no}</span>\n'
                  f'        <span class="cno">{no}</span>\n'
                  f'        <span class="ctitle">{title}</span>\n'
                  f'        <span class="ccount">{cnt} 份</span>\n'
                  f'        <span class="cdesc">{desc}</span>\n'
                  f'      </a>\n')

    tabbar = "".join(
        f'    <button class="tab{" on" if i == 0 else ""}" type="button" data-tab="{tid}" '
        f'role="tab" aria-selected="{"true" if i == 0 else "false"}">{tname}</button>\n'
        for i, (tid, tname) in enumerate(TABS))
    # 刷新按钮常驻 tabbar：任何 tab 都能一键重新取数
    tabbar += '    <div class="qjbar">\n      ' + qjr.button("随时重新取数") + '\n    </div>\n'

    frag = ""
    frag_ts = ""
    if os.path.exists(FRAG):
        frag = open(FRAG, encoding="utf-8").read()
        # 片段自己不带 header（那是刻意的设计），所以生成时刻要从文件 mtime 取
        frag_ts = datetime.fromtimestamp(os.path.getmtime(FRAG)).strftime("%m 月 %d 日 %H:%M")
    else:
        frag = ('<p class="lead">晨检片段尚未生成。跑一次 '
                '<code>build-morning-board.py</code> 即可出现在这里。</p>')

    now = datetime.now()

    pulse_items = load_pulse()
    pulse_html = render_pulse(pulse_items)
    acts = load_actions()
    acts_html = render_acts(acts)
    mw = load_market()
    mw_html = render_market(mw)
    traf_detail, traf_rows = load_traffic()
    traf_html = render_traffic(traf_detail, traf_rows)
    subs_snap, subs_rows = load_subs()
    subs_html = render_subs(subs_snap, subs_rows)
    xhs_snap = bmb.load_xhs()
    xhs_html = render_xhs(xhs_snap)

    # 今日 tab 的「数据总览」：三张柱状图 + 从数据直接读出来的判断。
    # 数据源全部走各自的真源（CF CSV / 小红书 CSV / 积分账本），不在这里另起一套口径。
    tr_bmb = bmb.load_traffic()
    xhs_series = load_xhs_series()
    cred_series = load_credit_series()
    # 站点序列优先取 CSV 的逐日累积（已 20+ 天），比晨检那个 7 日窗口长得多，
    # 柱状图才看得出趋势；取不到再退回晨检的 series。
    s = []
    for r in traf_rows[-14:]:
        try:
            s.append({"d": r.get("date", ""),
                      "v": int(str(r.get("visits_clean") or 0).replace(",", ""))})
        except ValueError:
            continue
    if not s:
        s = tr_bmb.get("series") or []
    # 判断与图表共用同一条序列，避免两处口径打架
    tr_bmb = dict(tr_bmb)
    tr_bmb["series"] = s
    site_avg = round(sum(x["v"] for x in s[-7:]) / 7) if len(s) >= 7 else (s[-1]["v"] if s else 0)
    charts_html = (
        render_chart("站点 · 真人访次/天", _num(site_avg), "", s,
                     f"近 {len(s)} 日　·　已剔除已知爬虫　·　越往右越近")
        + render_chart("小红书 · 曝光/天",
                       _num((xhs_snap.get("overview") or {}).get("exposure") or 0), "",
                       xhs_series,
                       "近 7 日滚动窗口　·　每天晨检采一次，断一天缺一天")
        + render_chart("积分 · 每日消耗",
                       (cred_series[-1]["bal"] if cred_series else "—"), " 分余额",
                       cred_series, "柱高＝当日消耗　·　单日 >100 分是重活日"))
    insight_html = render_insight(tr_bmb, xhs_snap, cred_series, subs_snap)
    red = sum(1 for x in pulse_items if x["cls"] in ("bad", "warn"))

    panels_html = f'''
<section class="panel" id="today-panel" data-panel="today" role="tabpanel">
  <div class="wrap">
    <div class="hero">
      <p class="sub"><span id="qj-gen">{now:%m 月 %d 日 %H:%M} 生成</span> · 数据来自本地台账</p>
    </div>
    <div class="secbar"><h3>今日状态</h3><span id="qj-pulse-sum">{len(pulse_items)} 项指标{('　·　有 %d 项不在正常区间' % red) if red else '　·　全部正常'}</span></div>
{pulse_html}
    <div class="secbar"><h3>数据总览</h3><span>所有平台的关键数字 · 每天 06:30 随晨检更新</span></div>
    <div class="charts">
{charts_html}
    </div>
    <div class="secbar"><h3>今日判断</h3><span>只写能从数据直接读出来的东西 · 不编趋势 · 不预测</span></div>
    <div class="ins">
{insight_html}
    </div>
    <div class="secbar"><h3>需要你动手的事</h3><span>来自 NOW.md · 共 {len(acts)} 项</span></div>
{acts_html}
    <div class="divider"></div>
    <div class="secbar"><h3>家底</h3><span>沉淀了多少，不常变</span></div>
    <div class="stats">
      <div class="stat"><div class="n"><em>213</em></div><div class="l">已入库知识资产</div></div>
      <div class="stat"><div class="n">263</div><div class="l">典籍条目</div></div>
      <div class="stat"><div class="n">120</div><div class="l">历史事件条目</div></div>
      <div class="stat"><div class="n">14</div><div class="l">已完成底纹的朝代</div></div>
    </div>
    <div class="quick">
      <a class="qcard" href="https://www.workbuddy.cn/space/d/{HOME_DOC}" target="_blank" rel="noopener">
        <span class="qt">工作台首页</span>
        <span class="qd">文字版导航 · 分区说明 · 纪律原文</span>
        <span class="qg">打开文档 →</span>
      </a>
      <a class="qcard" href="https://www.workbuddy.cn/space/d/{BOARD_NODE}" target="_blank" rel="noopener">
        <span class="qt">晨检看板（独立页）</span>
        <span class="qd">与「晨检详报」tab 同源，可单独收藏或分享</span>
        <span class="qg">打开独立页 →</span>
      </a>
    </div>
    <p class="note">九个 tab 各自成一页，切换不跳转；当前 tab 会记在地址栏，刷新后仍在原处。</p>
  </div>
</section>

<section class="panel" data-panel="morning" role="tabpanel" hidden>
  <div class="wrap">
    <p class="lead">{frag_ts or '—'} 生成 · 每天 06:30 自动跑 · 缺失显示「本次未提供」，不编造</p>
{frag}
  </div>
</section>

<section class="panel" data-panel="content" role="tabpanel" hidden>
  <div class="wrap">
    <p class="lead">点开直接进对应目录</p>
    <div class="grid">
{cards}    </div>
    <div class="secbar"><h3>字形长卷</h3><span>十四朝自有底纹成品 · 点击放大</span></div>
    <p class="lead">横向滑动　·　十六朝中尚缺「元」与「觉醒年代」两朝底纹，待补</p>
    <div class="scrollrow">
{gallery}    </div>
  </div>
</section>

<section class="panel" data-panel="market" role="tabpanel" hidden>
  <div class="wrap">
    <p class="lead">{mw.get('updated','—')} 扫描 · 每月 10 日自动更新 · 数字均标来源，未核实的一律不进结论</p>
{mw_html}
    <p class="note">原文与逐条来源见 <code>{esc(mw.get('source_doc','—'))}</code></p>
  </div>
</section>

<section class="panel" data-panel="traffic" role="tabpanel" hidden>
  <div class="wrap">
    <p class="lead">站点真实流量 · 已剔除已知爬虫与扫描器 · 未核实的数字一律标口径，不编造</p>
{traf_html}
  </div>
</section>

<section class="panel" data-panel="xhs" role="tabpanel" hidden>
  <div class="wrap">
    <p class="lead">小红书创作服务平台 · 近 7 日滚动窗口 · 数字取自页面原值，未核实的一律不进结论</p>
{xhs_html}
  </div>
</section>

<section class="panel" id="subs-panel" data-panel="subs" role="tabpanel" hidden>
  <div class="wrap">
    <p class="lead">订阅名单 · 只显示数量与时间 · 邮箱地址一律不落台账</p>
{subs_html}
  </div>
</section>

<section class="panel" data-panel="rules" role="tabpanel" hidden>
  <div class="wrap">
    <p class="lead">这套东西能长期不散，靠的是这三条</p>
    <div class="rules">
      <div class="rule"><span class="rn">一</span><div class="rt">单向副本</div><div class="rd">这里是消费端。要改内容，一律改本地工作区再重传；这里的改动不回写，避免两份互相矛盾的「真的」。</div></div>
      <div class="rule"><span class="rn">二</span><div class="rt">真源唯一</div><div class="rd">本地工作区是真源，这里是它的只读投影。两边不一致时以本地为准。</div></div>
      <div class="rule"><span class="rn">三</span><div class="rt">不存个人信息</div><div class="rd">订阅者邮箱、客户联系方式、账号凭据一律不进云端。这是有意为之，不是遗漏。</div></div>
    </div>
    <div class="excl">
      <h3>刻意没放进来的东西</h3>
      <ul>
        <li>运营凭据与台账（含订阅者真实邮箱，属个人信息）</li>
        <li>客户库与联系方式</li>
        <li>壁纸产物约 980 MB、音频 171 MB（是脚本要处理的产物，两边都会漂移）</li>
        <li>本地脚本源码、临时目录 <code>.work/</code> 与 <code>.scratch/</code></li>
      </ul>
      <p class="why">原因：资料库存「沉淀」不存「进行中」；产物与源数据一旦双份，漂移只是时间问题。</p>
    </div>
  </div>
</section>
'''

    doc = (f'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           f'<title>第七境 · 工作台</title>\n<style>{CSS}</style>\n</head>\n<body>\n'
           f'<header class="brand"><img src="{LOGO_BANNER}" alt="第七境 · The Seventh Realm" '
           f'width="1920" height="260"></header>\n\n'
           f'<nav class="tabbar" role="tablist"><div class="wrap">\n{tabbar}  </div></nav>\n'
           f'{panels_html}\n'
           f'<footer>\n  <div class="fbrand">第七境 · The Seventh Realm</div>\n'
           f'  <div>一个个人创作者</div>\n'
           f'  <div>工作台门户 · 内容沉淀于团队空间 · 页面生成于 {now:%Y-%m-%d %H:%M}</div>\n'
           f'  <div>「刷新数据」要真取数，需本机刷新服务在跑：'
           f'<code>http://127.0.0.1:{qjr.PORT}/</code>（服务未启动时会退化为重新载入）</div>\n'
           f'</footer>\n\n'
           f'<div class="lb" id="lb" onclick="closeLb()">\n'
           f'  <img id="lbimg" src="" alt="" width="1920" height="1080">\n'
           f'  <div class="cap" id="lbcap"></div>\n</div>\n\n'
           f'<script type="application/json" id="qj-pulse-data">{qjr.pulse_payload(pulse_items)}</script>\n\n'
           f'<script>{JS}</script>\n</body>\n</html>\n')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)
    return OUT


def upload(path):
    cmd = ["python3", f"{SKILL}/page/import_html.py", path,
           "--space-id", SPACE_ID, "--node-block-id", NODE_ID]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = (r.stdout or "") + (r.stderr or "")
    # ⚠️ import_html.py 业务失败时同样 exit 0，只是输出一行 {"error":"..."}。
    # 只看 returncode 会把失败当成成功 —— 2026-10-11 就踩了这个坑：
    # 刷新日志写着「同步 ok」，云端页面却一直停在旧版本上，排查时完全没线索。
    # 所以这里必须检查输出内容，并以非零码退出，让 refresh-server 记下 FAIL。
    if r.returncode != 0 or '"error"' in out.lower():
        print("❌ 同步云端失败：" + out.strip()[:400], file=sys.stderr)
        sys.exit(1)
    return out


if __name__ == "__main__":
    out = build()
    print(f"已生成：{out}（{os.path.getsize(out)/1024:.1f} KB）")
    txt = open(out, encoding="utf-8").read()
    print(f"  tab {txt.count('data-tab=')} 个 ｜面板 {txt.count('data-panel=')} 个 "
          f"｜画廊 {txt.count('class=\"wp\"')} 幅 ｜内嵌晨检片段 {'有' if 'class=\"mb\"' in txt else '无'}")
    if "--upload" in sys.argv:
        s = open(out, encoding="utf-8").read()
        bad = [b for b in re.findall(r'(?:src|srcset)\s*=\s*["\'](?:https?:)?//[^"\']+', s)
               if "workbuddy" not in b and "codebuddy" not in b]
        if bad:
            print("❌ 存在第三方图片链接，已中止上传：", bad[:3])
            sys.exit(1)
        print(upload(out).strip())
