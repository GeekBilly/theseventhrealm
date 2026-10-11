#!/usr/bin/env python3
"""生成商店页架构「阶段二」的 17 个页面 HTML（朝代专栏 + 16 个单朝页）。

用法：
    python3 11-运营/scripts/build-dynasty-shop.py

产出（可直接作为 WP pages 的 content）：
    03-页面/collection-dynasty.html           朝代专栏 /collection/dynasty/
    03-页面/collection-dynasty-<slug>.html    16 个单朝页 /collection/dynasty/<slug>/
            + 同名 .title / .slug 小文件，供发布脚本读取

口径：
  · 数据只来自 11-运营/朝代页流水线/eras.py（不手写内容）
  · 颜色/版式只来自一份共享 <style>（从 03-页面/collection.html 现取 + 追加栅格覆盖）
    —— 17 页逐字一致，避免各页各写一份
  · 类名只用 sub rule lead price shots cta note fine（+ 站点既有的 sr-collection 外层）
  · 0 HTML 注释、0 直引号（正文）、0 繁体、不出现「卖」字、无购买链接
"""

import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
ERAS_PY = ROOT / '11-运营/朝代页流水线/eras.py'
CANON = ROOT / '03-页面/collection.html'
OUTDIR = ROOT / '03-页面'

# ── 追加在共享样式末尾的栅格覆盖（朝代专栏 16 格用；单朝页用不到，但保持 17 页逐字一致）
# 🔴 样式块内**绝不能有空行**：wpautop 会把空行后面的 CSS 包进 <p>，
#    导致该规则选择器失效（2026-10-03 实测：`<p>.sr-collection .shots{...}` → 4 列变 3 列）。
GRID_CSS = """\
.sr-collection .shots{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.sr-collection .shots li a{display:block;height:100%;background:#fff;border:1px solid #e3ddd0;
 border-radius:6px;padding:14px 16px 12px;color:#45423c}
.sr-collection .shots li a:hover{border-color:#b03826}
.sr-collection .shots b{display:block;font-weight:400;font-size:19px;letter-spacing:2px;
 color:#1f1d1a;margin:0 0 3px;font-family:"Ma Shan Zheng","Songti SC",serif}
.sr-collection .shots span{display:block;font-size:12.5px;color:#6b6559;line-height:1.75;
 text-align:left;margin:0}
.sr-collection .shots em{display:block;font-style:normal;font-size:13.5px;color:#45423c;
 margin-top:6px;line-height:1.75}
.sr-collection .shots i{display:block;font-style:normal;font-size:12.5px;color:#b03826;
 letter-spacing:1px;margin-top:8px;padding-top:8px;border-top:1px solid #f0ebdf}
@media (max-width:900px){.sr-collection .shots{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.sr-collection .shots{gap:10px}.sr-collection .shots b{font-size:17px}}
"""

PRICE_DESKTOP = '预告价：单朝 ¥12 ｜ 商周套装 ¥19 ｜ 首发有折扣'
BTN_SIGNUP = ('<a class="cta" href="/collection/#signup" '
              'style="background:transparent;border:1px solid #cfc7b8;color:#45423c">'
              '即将开售 · 通知我</a>')
BTN_BACK = ('<a class="cta" href="/collection/" '
            'style="background:transparent;border:1px solid #cfc7b8;color:#45423c">'
            '← 回到商店首页</a>')

# 有底纹的朝代：slug -> 底纹名
PATTERN = {'shang': '玄鸟', 'zhou': '凤凰'}


def load_eras():
    spec = importlib.util.spec_from_file_location('eras', ERAS_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ERAS


def load_shared_css():
    """从站点既有藏品页里现取 <style>，再追加栅格覆盖 —— 全站一份。

    ⚠️ 拼接后必须无空行：wpautop 会把空行之后的 CSS 包进 `<p>`，选择器随即失效。
    """
    html = CANON.read_text(encoding='utf-8')
    m = re.search(r'<style>(.*?)</style>', html, re.S)
    if not m:
        raise SystemExit('取不到 03-页面/collection.html 的 <style> 块')
    css = m.group(1).strip('\n') + '\n' + GRID_CSS.strip('\n')
    if '\n\n' in css:
        raise SystemExit('样式块里出现空行 —— wpautop 会插 <p>，必须先去掉')
    return '<style>' + css + '</style>'


def verse_text(era):
    v = era['verse']
    return '，'.join(v) if isinstance(v, (list, tuple)) else v


def lead_excerpt(era, n=60):
    lead = era['lead']
    cut = lead[:n].rstrip('，。；：、')
    return cut + '……'


def status_of(slug):
    return '即将开售' if slug in PATTERN else '正在准备'


def column_page(eras, css):
    # ⚠️ 每格必须**写成一行**：<a> 不在 wpautop 的块级白名单里，
    #    格子内部一换行就会被插 <br />，而 b/span/em/i 都是 display:block，
    #    多余 <br /> 会在格子里留下空行（2026-10-03 实测）。
    cells = []
    for e in eras:
        cells.append(
            '<li><a href="/collection/dynasty/{slug}/">'
            '<b>{h1}</b><span>{years}</span><em>{verse}</em><i>{status}</i>'
            '</a></li>'.format(slug=e['slug'], h1=e['h1'], years=e['years'],
                               verse=verse_text(e), status=status_of(e['slug'])))
    return (
        '{css}\n'
        '<div class="sr-collection">\n'
        '<h1>朝代</h1>\n'
        '<p class="sub">十六朝 · 朝朝一句金句、一件文物</p>\n'
        '<div class="rule"></div>\n'
        '<div class="lead">\n'
        '  <b>十六朝，朝朝一句金句、一件文物。</b>\n'
        '  手机竖版免费，桌面横版按朝成套。\n'
        '</div>\n\n'
        '<ul class="shots">\n'
        '{cells}\n'
        '</ul>\n\n'
        '<p>{back}</p>\n'
        '</div>\n'
    ).format(css=css, cells='\n'.join(cells), back=BTN_BACK)


def single_page(era, css):
    slug = era['slug']
    h1 = era['h1']
    pat = PATTERN.get(slug)
    desk_tail = '，本朝底纹为{}。'.format(pat) if pat else '。'
    font_block = ''
    if slug in ('shang', 'zhou'):
        font_block = (
            '\n<h2>字体演变</h2>\n'
            '<p class="price">单期 ¥12 ｜ 商周套装 ¥19</p>\n'
            '<p>商是甲骨文，周是金文。一期三联，含 4K。</p>\n'
            '<p>{btn}</p>\n'
        ).format(btn=BTN_SIGNUP)
    return (
        '{css}\n'
        '<div class="sr-collection">\n'
        '<h1>{h1}</h1>\n'
        '<p class="sub">{years}</p>\n'
        '<div class="rule"></div>\n'
        '<div class="lead">\n'
        '  <b>「{verse}」</b>\n'
        '  —— {src}\n'
        '</div>\n\n'
        '<h2>手机竖版 · 免费</h2>\n'
        '<p class="price">iPhone / Android 各 1 张 · 免费领取</p>\n'
        '<p>{h1}的手机竖版壁纸，不带底纹。全十六朝共 32 张，留邮箱一次发给你。</p>\n'
        '<p><a class="cta" href="/collection/#signup">免费领取 32 张 →</a></p>\n\n'
        '<h2>桌面横版</h2>\n'
        '<p class="price">{price}</p>\n'
        '<p>1x 与 4K 两种规格。宣纸底、朱砂点睛{desk_tail}</p>\n'
        '<p>{btn}</p>\n'
        '{font_block}\n'
        '<h2>读这个朝代的长卷</h2>\n'
        '<p>{excerpt}</p>\n'
        '<p><a class="cta" href="/5000years/{slug}/">读《{h1}》全文 →</a></p>\n'
        '</div>\n'
    ).format(css=css, h1=h1, years=era['years'], verse=verse_text(era), src=era['src'],
             price=PRICE_DESKTOP, desk_tail=desk_tail, btn=BTN_SIGNUP,
             font_block=font_block, excerpt=lead_excerpt(era), slug=slug)


def main():
    eras = load_eras()
    css = load_shared_css()
    assert len(eras) == 16, len(eras)

    pages = [('collection-dynasty', '藏品 · 朝代', 'dynasty', '134', column_page(eras, css))]
    for e in eras:
        title = '{} · 壁纸与藏品'.format(e['h1'])
        name = 'collection-dynasty-' + e['slug']
        pages.append((name, title, e['slug'], 'COLUMN_ID', single_page(e, css)))

    for name, title, slug, parent, html in pages:
        (OUTDIR / (name + '.html')).write_text(html, encoding='utf-8')
        (OUTDIR / (name + '.title')).write_text(title, encoding='utf-8')
        (OUTDIR / (name + '.slug')).write_text(slug, encoding='utf-8')
        print('{:34s} {:22s} {:14s} len={}'.format(name, title, slug, len(html)))
    print('共 {} 页 → {}'.format(len(pages), OUTDIR))


if __name__ == '__main__':
    main()
