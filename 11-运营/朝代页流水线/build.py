# -*- coding: utf-8 -*-
"""生成 16 个朝代独立页正文（HTML 片段），供 WordPress 发布。

用法：python3 build.py   → 输出到 03-页面/朝代页/<slug>.html

数据来源：
  - eras.py   ：静态元数据（slug / seo / h1 / sub / ghost / seal / verse / src）
  - bodies.py ：由 sync-from-drafts.py 从 01-内容/历史长卷/朝代稿 生成（正文、三卡、收尾、引用）
                **改稿后先跑 sync-from-drafts.py，再跑本脚本**，不要手改 bodies.py。

版式复用站点现有类；新增样式内联在本页 <style> 内（避免为了 CSS 再传一次主题包）。
"""
import os, sys, pathlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eras import ERAS, CN_NUM
from bodies import BODIES

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / '03-页面' / '朝代页'
OUT.mkdir(parents=True, exist_ok=True)

STYLE = """<style>
section{padding:clamp(44px,6vw,60px) 24px}
.hero{min-height:54vh}
.verse{position:relative;padding:clamp(34px,5vw,54px) 24px}
.vsrc{margin-top:22px;font-size:13px;letter-spacing:3px;color:rgba(26,26,24,.5)}
.era-toc{max-width:760px;margin:0 auto;padding:6px 24px 0;font-size:14px;letter-spacing:2px;
  line-height:2.15;color:rgba(26,26,24,.6)}
.era-toc .ttl{font-family:var(--f-brush);font-size:16px;letter-spacing:4px;
  color:rgba(26,26,24,.45);margin-bottom:6px}
.era-toc a{color:inherit;border-bottom:1px dotted rgba(26,26,24,.3)}
.era-toc a:hover{color:var(--cinnabar);border-bottom-color:var(--cinnabar)}
.prose h2{font-family:var(--f-brush);font-size:clamp(19px,2.7vw,26px);letter-spacing:3px;
  color:var(--ink);margin:52px 0 18px;scroll-margin-top:80px}
.prose h2:first-of-type{margin-top:36px}
.prose p.q{font-size:17px;letter-spacing:3px;line-height:2.1;color:var(--ink2);
  border-left:2px solid rgba(158,43,37,.35);padding:6px 0 6px 20px;margin:26px 0;
  background:rgba(255,255,255,.4)}
.dispute{max-width:760px;margin:44px auto 0;padding:16px 20px;font-size:13.5px;letter-spacing:1.6px;
  line-height:2;color:rgba(26,26,24,.66);border-left:3px solid rgba(158,43,37,.5);
  background:rgba(255,255,255,.5)}
.relic{display:grid;grid-template-columns:repeat(3,1fr);gap:clamp(14px,3vw,30px);max-width:840px;margin:0 auto}
.relic .card{border:1px solid rgba(26,26,24,.13);border-radius:3px;padding:20px 16px;background:rgba(255,255,255,.55)}
.relic .card .k{font-family:var(--f-brush);font-size:clamp(20px,2.8vw,28px);color:var(--cinnabar);display:block;margin-bottom:8px}
.relic .card .t{font-size:13px;letter-spacing:4px;color:var(--ink2);margin-bottom:8px}
.relic .card .d{font-size:15.5px;letter-spacing:2px;line-height:1.85;color:var(--ink)}
.cites{max-width:760px;margin:0 auto;font-size:13px;letter-spacing:1.4px;line-height:2;
  color:rgba(26,26,24,.6)}
.cites summary{cursor:pointer;font-family:var(--f-brush);font-size:15px;letter-spacing:4px;
  color:rgba(26,26,24,.55);padding:8px 0}
.cites summary:hover{color:var(--cinnabar)}
.cites ul{margin:12px 0 0;padding-left:20px}
.cites li{margin-bottom:7px}
.era-nav{display:flex;justify-content:center;align-items:center;gap:16px;flex-wrap:wrap;
  font-family:var(--f-brush);font-size:clamp(15px,2vw,18px);letter-spacing:3px}
.era-nav a{color:var(--ink)}
.era-nav a:hover{color:var(--cinnabar)}
.era-nav .sep{color:rgba(26,26,24,.25)}
.fineprint{max-width:660px;margin:26px auto 0;font-size:12.5px;letter-spacing:2px;
  line-height:1.9;color:rgba(26,26,24,.45);text-align:center}
@media(max-width:640px){.relic{grid-template-columns:1fr}}
</style>"""


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def blocks(blk):
    """[(kind, html)] → HTML 片段（kind: p / quote）"""
    return '\n'.join(
        ('    <p class="q">%s</p>' % h) if k == 'quote' else ('    <p>%s</p>' % h)
        for k, h in blk)


def build(i, e, prev_e, next_e):
    b = BODIES[e['slug']]

    # 竖排金句：多句时拆成竖列，且按「从右往左读」倒序输出（flex 首个子元素在左）
    v = e['verse']
    lines = v if isinstance(v, list) else [v]
    vpoem = ''.join(f'<p>{esc(s)}</p>' for s in reversed(lines))

    toc = '\n'.join('      <a href="#s%d">%s</a><br>' % (n + 1, h)
                    for n, (h, _) in enumerate(b['body']))

    secs = []
    for n, (h, blk) in enumerate(b['body']):
        secs.append('    <h2 id="s%d">%s</h2>\n%s' % (n + 1, h, blocks(blk)))
    body_html = '\n'.join(secs)

    cards = '\n'.join(
        f'      <div class="card"><span class="k">{esc(k)}</span>'
        f'<p class="t">{t}</p><p class="d">{d}</p></div>'
        for k, t, d in b['relic'])

    dispute_html = ('    <div class="dispute">%s</div>' % esc(b['dispute'])
                    if b['dispute'] else '')

    cites_html = ''
    if b['cites']:
        items = '\n'.join('        <li>%s</li>' % esc(c) for c in b['cites'])
        cites_html = ('    <details class="cites">\n'
                      '      <summary>引用出处（%d 条）</summary>\n'
                      '      <ul>\n%s\n      </ul>\n    </details>' % (len(b['cites']), items))

    prev_link = (f'<a href="/5000years/{prev_e["slug"]}/">← {esc(prev_e["h1"])}</a>'
                 if prev_e else '<a href="/5000years/">← 长卷之首</a>')
    next_link = (f'<a href="/5000years/{next_e["slug"]}/">{esc(next_e["h1"])} →</a>'
                 if next_e else '<a href="/5000years/">长卷暂止 →</a>')

    parts = [STYLE, '',
             '<header class="hero">',
             '  <p class="zi-top">上下五千年 · 第%s卷</p>' % CN_NUM[i],
             '  <h1>%s</h1>' % esc(e['h1']),
             '  <p class="subtitle">%s</p>' % esc(e['sub']),
             '  <div><span class="seal">%s</span></div>' % esc(e['seal']),
             '</header>', '',
             '<section class="verse reveal">',
             '  <div class="vpoem">%s</div>' % vpoem,
             '  <span class="ghost">%s</span>' % esc(e['ghost']),
             '  <p class="vsrc">—— %s</p>' % esc(e['src']),
             '</section>', '',
             '<section>',
             '  <div class="era-toc">',
             '    <p class="ttl">本卷目录</p>',
             toc,
             '  </div>',
             '</section>', '',
             '<section>',
             '  <div class="prose">',
             blocks(b['lead']),
             body_html,
             blocks(b['close']),
             '  </div>',
             dispute_html,
             '</section>', '',
             '<section>',
             '  <div class="relic reveal">',
             cards,
             '  </div>',
             '</section>', '',
             '<section class="reveal">',
             '  <div class="finale">',
             '    <p class="final-line">%s</p>' % b['fin'],
             '  </div>',
             '</section>', '']
    if cites_html:
        parts += ['<section>', cites_html, '</section>', '']
    parts += ['<section>',
              '  <div class="era-nav">',
              '    %s<span class="sep">☷</span><a href="/5000years/">总览</a>'
              '<span class="sep">☷</span>%s' % (prev_link, next_link),
              '  </div>',
              '  <p class="fineprint">年代与字形取通行说法；先秦部分学者间存在不同意见，凡有争议处已在文中标明。若发现错漏，欢迎写信至 hello@theseventhrealm.com 指正，核实后即改。</p>',
              '  <p style="text-align:center;margin-top:22px"><a class="back-home" href="/5000years/">← 回到上下五千年</a>　<span class="sep">☷</span>　<a class="back-home" href="/collection/">藏品 · 把五千年带在身边 →</a></p>',
              '</section>', '']
    return '\n'.join(parts)


if __name__ == '__main__':
    for i, e in enumerate(ERAS):
        prev_e = ERAS[i - 1] if i > 0 else None
        next_e = ERAS[i + 1] if i < len(ERAS) - 1 else None
        html = build(i, e, prev_e, next_e)
        (OUT / f"{e['slug']}.html").write_text(html, encoding='utf-8')
        n = len(BODIES[e['slug']]['body'])
        print(f"  ✓ {e['slug']:9s} {len(html):6d} 字节  {n:2d} 节  {e['seo']}")
    print(f"\n共 {len(ERAS)} 页 → {OUT}")
