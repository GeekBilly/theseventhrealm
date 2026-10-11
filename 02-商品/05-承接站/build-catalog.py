# -*- coding: utf-8 -*-
"""商品名录生成器：读 eras.py 素材 → 产出 catalog.csv / sources.csv / 可视化名录 HTML。
本地运行，零积分。用法：python3 02-商品/05-承接站/build-catalog.py
"""
import re, csv, pathlib, urllib.parse

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/01-规划'          # catalog.csv / sources.csv
SHOP = ROOT / '02-商品/05-承接站'        # 可视化名录（也是承接站原型）

# ---- 1. 从 eras.py 抽 16 条金句 ----
src_py = (ROOT / '11-运营/朝代页流水线/eras.py').read_text(encoding='utf-8')
eras = []
for blk in src_py.split("dict(")[1:]:
    g = lambda k: (re.search(rf"{k}='([^']*)'", blk) or [None, ''])[1]
    eras.append(dict(slug=g('slug'), h1=g('h1'), verse=g('verse'), src=g('src')))
eras = [e for e in eras if e['slug']]

# ---- 2. SKU 清单 ----
FIELDS = ['sku', 'tier', 'name', 'form', 'price_cny', 'price_usd', 'material', 'moq', 'status', 'blocker']
SKUS = [
    # A 档 数字纪念品
    # 线二 · 金句线（手机竖版，无底纹 → 免费引流：数字品防不住复制，展示图即成品）
    ('SR-D-001', 'A', '五千年金句 · 手机竖版（免费引流品）', '32 张 PNG（iPhone 1179×2556 + Android 1080×2400）',
     0, 0, '16 朝金句，免费换邮箱', 0, '免费发放', '无（免费引流）'),
    # 线一 · 字形线（桌面横版，带底纹 → 溢价）
    ('SR-Z-001', 'A', '「字之三千年」殷商 · 「商」字三联', '4 尺寸（1080p/4K/Mac/4K-Mac）',
     12, 1.99, '字形三联 + 玄鸟底纹', 0, '成品已出', '商标受理'),
    ('SR-Z-002', 'A', '「字之三千年」西周 · 「周」字三联', '4 尺寸（1080p/4K/Mac/4K-Mac）',
     12, 1.99, '字形三联 + 高冈云气底纹', 0, '成品已出', '商标受理'),
    ('SR-Z-000', 'A', '「字之三千年」第一辑套装（商 + 周）', '8 张（两朝全规格）',
     19, 2.99, '两朝套装，比单买省 ¥5', 0, '成品已出', '商标受理'),
    ('SR-D-003', 'A', '朝代印章藏书票', '16 枚 PNG/PDF', 9, 1.99, '朝代 ghost 字 + 印章样式', 0, '素材现成', '商标受理'),
    ('SR-D-004', 'A', '五千年色卡', '16 套配色（含 HEX）', 0, 0, '现有配色体系', 0, '素材现成', '无（免费引流）'),
    ('SR-D-006', 'A', '朝代诵读音频（试听）', '6 段 mp3', 0, 0, '08-音频/ 已有 6 段', 0, '素材现成', '无（免费引流）'),
    # B 档 数字藏品 / 电子册
    ('SR-E-001', 'B', '《五千年金句帖》', 'A4 PDF，可打印摹写', 39, 6.99, '24 页（16 金句+释义+练习格）', 0, '待排版', '商标受理+平台'),
    ('SR-E-002', 'B', '《甲骨千字课》', 'A4 PDF 字帖', 59, 9.99, '40 页（商字形+楷书对照+描红）', 0, '待排版', '字形授权复核'),
    ('SR-E-003', 'B', '《长卷图谱》', 'A3 PDF 折页', 69, 12.99, '6 折页时间线', 0, '待排版', '商标受理+平台'),
    ('SR-E-004', 'B', '十六朝代诵读全集', 'mp3 包 + 文稿', 39, 6.99, '约 90 分钟', 0, '待录音', '录音排期'),
    ('SR-E-005', 'B', '「一朝一册」系列', '16 册 PDF', 299, 39.99, '每册 8–12 页（单册 29 元）', 0, '待排版', '商标受理+平台'),
    # C 档 众筹实体
    ('SR-P-001', 'C', '《五千年金句帖》装帧本', '线装 / 宣纸内页', 159, 24.99, '24 页', 300, '素材现成', '打样+工厂报价'),
    ('SR-P-002', 'C', '《甲骨千字课》摹本册', '宣纸摹本', 129, 19.99, '40 页', 300, '待排版', '打样+工厂报价'),
    ('SR-P-003', 'C', '《上下五千年 · 第七境版》', '精装', 199, 29.99, '约 200 页', 500, '需扩写', '正文扩至 8–10 万字'),
    ('SR-P-004', 'C', '长卷绢布卷轴', '绢布，约 3 米', 499, 79.99, '全时间线', 200, '后置', '打样成本高'),
    ('SR-P-005', 'C', '十六朝代藏书票套装', '实体钤印 16 枚', 89, 13.99, '16 枚', 500, '可做赠品', '打样'),
]

with open(OUT / 'catalog.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(FIELDS)
    w.writerows(SKUS)

# ---- 3. 典籍引用清单（扫站） ----
import collections
cnt = collections.Counter()
where = collections.defaultdict(set)
files = sorted((ROOT / '03-页面/朝代页').glob('*.html')) + [
    ROOT / '01-内容/历史长卷/5000years.html', ROOT / '01-内容/道境/dao-realm.html']
for fp in files:
    h = re.sub(r'<!--.*?-->', '', fp.read_text(encoding='utf-8'), flags=re.S)
    for m in re.findall(r'《([^》]{1,24})》', h):
        cnt[m] += 1
        where[m].add(fp.stem)
with open(OUT / 'sources.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['title', 'hits', 'pages'])
    for k, v in cnt.most_common():
        w.writerow([k, v, '/'.join(sorted(where[k]))])

# ---- 4. 可视化名录 HTML（水墨 / 浅色底 / 无外部依赖） ----
TIERS = {'A': ('数字纪念品', '¥0–39', '#4a6b57'),
         'B': ('数字藏品 · 电子册', '¥39–129', '#8a6d3b'),
         'C': ('众筹实体', '¥129–499', '#9e2b25')}
STAT = {'素材现成': '#4a6b57', '待排版': '#8a6d3b', '需补字形': '#8a6d3b',
        '待录音': '#8a6d3b', '需扩写': '#9e2b25', '后置': '#7b7b7b', '可做赠品': '#4a6b57'}


def card(s):
    sku, tier, name, form, cny, usd, mat, moq, status, blocker = s
    price = '免费' if cny == 0 else f'¥{cny}'
    price2 = '' if cny == 0 else f' / ${usd}'
    moq_s = f'<span class="moq">起订 {moq} 件</span>' if moq else '<span class="moq inf">零库存</span>'
    return f"""<li class="card t{tier}">
      <div class="top"><code>{sku}</code><span class="tier">{TIERS[tier][0]}</span></div>
      <h3>{name}</h3>
      <p class="form">{form}</p>
      <p class="mat">{mat}</p>
      <div class="bot"><span class="price">{price}{price2}</span>{moq_s}
        <span class="stat" style="background:{STAT.get(status, '#777')}">{status}</span></div>
      <p class="blk">上线前置：{blocker}</p>
    </li>"""


def tier_block(t):
    name, band, color = TIERS[t]
    items = [s for s in SKUS if s[1] == t]
    return f"""<section class="tier-sec">
    <h2><span class="dot" style="background:{color}"></span> {t} 档 · {name} <em>{band}</em></h2>
    <ul class="grid">{''.join(card(s) for s in items)}</ul>
  </section>"""


verses = ''.join(
    f"<li><span class=\"v\">「{e['verse']}」</span><span class=\"s\">{e['src']}</span>"
    f"<span class=\"d\">{e['h1']}</span></li>" for e in eras)
srcs = ''.join(f"<li><b>{k}</b> ×{v} <span>{'/'.join(sorted(where[k]))}</span></li>"
               for k, v in cnt.most_common())

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>第七境 · 商品名录 v1</title>
<style>
:root{{--paper:#faf8f4;--ink:#1f1d1a;--ink2:#5a554c;--seal:#9e2b25;--line:#e3ddd0}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
 font-family:"Songti SC","Noto Serif SC",serif;line-height:1.75}}
.wrap{{max-width:1080px;margin:0 auto;padding:48px 24px 72px}}
h1{{font-size:32px;margin:0 0 6px;letter-spacing:2px}}
.sub{{color:var(--ink2);margin:0 0 8px;font-size:15px}}
.rule{{height:1px;background:var(--line);margin:26px 0 34px}}
.lead{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:18px 22px;margin:0 0 34px}}
.lead b{{color:var(--seal)}}
h2{{font-size:19px;letter-spacing:1px;margin:38px 0 16px;display:flex;align-items:center;gap:9px}}
h2 em{{font-style:normal;font-size:13px;color:var(--ink2);font-weight:400}}
.dot{{width:9px;height:9px;border-radius:50%;display:inline-block}}
.grid{{list-style:none;padding:0;margin:0;display:grid;
 grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 18px;
 box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.card .top{{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--ink2)}}
.card code{{letter-spacing:.5px}}
.card .tier{{background:#f2eee4;border-radius:20px;padding:2px 10px}}
.card h3{{margin:8px 0 6px;font-size:17px}}
.card .form{{margin:0;font-size:14px;color:var(--ink2)}}
.card .mat{{margin:4px 0 0;font-size:13px;color:#8a8377}}
.card .bot{{display:flex;align-items:center;gap:10px;margin-top:12px;flex-wrap:wrap}}
.price{{font-size:17px;color:var(--seal)}}
.moq,.stat{{font-size:12px;color:#fff;background:#7b7b7b;border-radius:4px;padding:2px 8px}}
.moq.inf{{background:#4a6b57}}
.blk{{margin:10px 0 0;font-size:12px;color:#8a8377;border-top:1px dashed var(--line);padding-top:8px}}
ul.vlist,ul.slist{{list-style:none;padding:0;margin:0;
 display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:8px}}
ul.vlist li{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:14px}}
ul.vlist .v{{display:block}}
ul.vlist .s{{display:block;font-size:12px;color:var(--seal);margin-top:2px}}
ul.vlist .d{{float:right;font-size:12px;color:#8a8377}}
ul.slist li{{font-size:13px;padding:6px 0;border-bottom:1px dashed var(--line);color:var(--ink2)}}
ul.slist b{{color:var(--ink)}}
ul.slist span{{color:#a09889;font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:#fff}}
th,td{{border:1px solid var(--line);padding:8px 10px;text-align:left}}
th{{background:#f2eee4}}
.foot{{margin-top:40px;font-size:13px;color:var(--ink2)}}
@media(max-width:600px){{.wrap{{padding:28px 16px 48px}}h1{{font-size:25px}}}}
</style></head><body><div class="wrap">
<h1>第七境 · 商品名录 v1</h1>
<p class="sub">2026-09-29 · 三档 {len(SKUS)} 个 SKU · 素材盘点 {len(eras)} 朝代 / {len(cnt)} 处典籍引用</p>
<div class="rule"></div>
<p class="lead">把网站上引用的<b>诗、书、字、经</b>做成「第七境版本」的数字纪念品；
攒够人，再把它<b>众筹成一本实体书</b>。<br>
C 档先收意向、不先生产：达标才开机，不达标全额退或转数字版 —— 永远不压库存、不垫货款。</p>

{''.join(tier_block(t) for t in 'ABC')}

<h2><span class="dot" style="background:#4a6b57"></span> 众筹规则（C 档）</h2>
<table>
<tr><th>项目</th><th>规则</th></tr>
<tr><td>周期</td><td>30 天，达到起订量才生产</td></tr>
<tr><td>未达标</td><td>全额退款，或一键转 B 档数字版（买家自选）</td></tr>
<tr><td>阶梯解锁</td><td>300 册 +藏书票 · 500 册 +函套 · 800 册 +编号钤印</td></tr>
<tr><td>发货</td><td>达标后 45 天内发出，公示打样/开机/装订节点</td></tr>
<tr><td>收款</td><td>海外 Gumroad / Kickstarter；国内走文创类目，不以图书名义</td></tr>
</table>

<h2><span class="dot" style="background:#8a6d3b"></span> 素材原料 · 十六朝代金句</h2>
<ul class="vlist">{verses}</ul>

<h2><span class="dot" style="background:#8a6d3b"></span> 素材原料 · 站内典籍引用 {len(cnt)} 处</h2>
<ul class="slist">{srcs}</ul>

<h2><span class="dot" style="background:#9e2b25"></span> 上线前置（缺一不动）</h2>
<table>
<tr><th>项</th><th>状态 / 要求</th></tr>
<tr><td>商标</td><td>受理号到手即可开卖，核准前一律用 ™；当前状态待确认</td></tr>
<tr><td>打样</td><td>C 档必须先打样拍照，样张不上、众筹不开</td></tr>
<tr><td>平台</td><td>Gumroad（数字）+ 众筹平台（实体），国内类目避开「出版物」</td></tr>
<tr><td>法务</td><td>数字商品不退不换条款、授权范围、发货与退款政策</td></tr>
<tr><td>字体合规</td><td>随产品附 OFL 声明，不单卖字体文件（OFL 1.1 的红线）</td></tr>
</table>

<p class="foot">承接方式定案：站内 <code>/collection/</code> 展示页（讲故事 + 转化）+ 第三方平台收款履约，
流量与邮件名单归自己。编辑角色装不了 WooCommerce，站内只做静态页与外链。<br>
生成器：<code>02-商品/05-承接站/build-catalog.py</code> · 数据表：<code>02-商品/01-规划/catalog.csv</code> / <code>sources.csv</code></p>
</div></body></html>"""

(SHOP / 'index.html').write_text(HTML, encoding='utf-8')
print(f"SKU {len(SKUS)} 条 / 金句 {len(eras)} 条 / 典籍 {len(cnt)} 处")
print("→", OUT / 'catalog.csv', OUT / 'sources.csv', SHOP / 'index.html')
