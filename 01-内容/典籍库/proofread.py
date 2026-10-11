#!/usr/bin/env python3
# 典籍库 · 录文校对辅助（只读，不改任何录文）
#
# 用法：
#   python3 proofread.py            # 全量体检，打印分级清单
#   python3 proofread.py --csv      # 额外导出 校对清单.csv
#
# 定位：机器能查的机器查，机器查不了的列成清单交人工。
#   P0 = 硬伤，必须修（状态缺失 / 原文缺失 / 出处无处可查）
#   P1 = 待补（缺本站用法 / 标了争议却没有争议标注）
#   P2 = 待校（节录·待校 / 需核）—— 须查点校本，本脚本只统计不判定
#
# ⚠️ 本脚本不做的事：不核对文字正误。那需要有点校本在手，脚本无从判断。

import re
import csv
import sys
import pathlib
import collections

ROOT = pathlib.Path(__file__).parent
ORIG = ROOT / '原文'

# 有意不录原文的合法标记：本就不录原文，不算缺陷。
# 含四类：① 说明性条目（条约全文、已佚书目、纯文献说明）
#        ② 有意不录原文（争议待核 / 原文在别处 / 数字散见，录了反而误导）
#        ③ 无原文可录（书已亡佚）  ④ 存疑·不裁定（两说并存，录谁都是裁定）
DESCRIPTIVE = re.compile(r'说明性条目|不录全文|无对应原文|有意不录|无原文可录|不裁定|参见')

# 状态归类
# ⚠️ 顺序有意义：「出处已核·文字待校」同时含「待校」二字，必须先判，
#    否则会被归到「待校」，本轮推进的条数就统计不出来。
def norm_state(s: str) -> str:
    s = s.strip()
    if '出处已核' in s:
        return '出处已核'
    if '待补原文' in s:
        return '待补原文'
    if s.startswith('已校'):
        return '已校'
    if '说明性' in s or '不录' in s:
        return '说明性'
    if '需核' in s:
        return '需核'
    if '待校' in s or s == '待校':
        return '待校'
    return '其他'

def parse_blocks(path: pathlib.Path):
    """切出每个「引文 / 附引」块，返回 dict。"""
    s = path.read_text(encoding='utf-8')
    out = []
    pat = re.compile(r'^(#{1,3})\s*((?:引文|附引)\s*\d+.*)$', re.M)
    ms = list(pat.finditer(s))
    for i, m in enumerate(ms):
        start = m.end()
        end = ms[i + 1].start() if i + 1 < len(ms) else len(s)
        blk = s[start:end]
        title = m.group(2).strip()
        st = re.search(r'录文状态[：:]\s*\*{0,2}(.+?)\*{0,2}\s*$', blk, re.M)
        raw_state = st.group(1).strip() if st else ''
        has_quote = bool(re.search(r'^>\s*\S', blk, re.M))
        has_usage = bool(re.search(r'\*\*本站用法\*\*', blk))
        # 争议标注：块内出现 ⚠️ 开头的列表项或「争议」字样（不含标题行）
        body = blk.split('\n')
        body = '\n'.join(l for l in body if not l.startswith('#'))
        # ⚠️ 块内说明的判定。
        # 实测教训：标题里的 ⚠️ **有两种语义**——① 此处有争议/须辨析 ② 此处重要/本站重点。
        # 第 ② 类（如「本站科学技术类最要紧的一条」「印刷史的关键一条」）本就不需要争议栏，
        # 它有「要点与分寸」就够了。而说明块的写法又极多（争议 / 出处说明 / 要点与分寸 /
        # 意义与限定 / 解读 …），用词表穷举必然误报。
        # → 因此判定放宽为「块内有任何 ⚠️ 标记即视为已标注」，
        #    「到底是不是争议」交给人工抽查（报告里单列标题含 ⚠️ 的条目数）。
        has_dispute = '⚠️' in body
        has_kw = bool(re.search(r'关键词[：:]', blk))
        out.append({
            'file': str(path.relative_to(ROOT)),
            'title': title,
            'raw_state': raw_state,
            'state': norm_state(raw_state) if raw_state else '❌无状态',
            'has_quote': has_quote,
            'has_usage': has_usage,
            'has_dispute': has_dispute,
            'has_kw': has_kw,
            'has_note': '🔍 校核' in blk,
            'chars': len(re.findall(r'[\u4e00-\u9fff]', blk)),
        })
    return out

def main():
    export_csv = '--csv' in sys.argv
    rows = []
    for p in sorted(ORIG.rglob('*.md')):
        if p.name == '00-索引.md':
            continue
        rows.extend(parse_blocks(p))

    p0, p1, p2, p2done = [], [], [], []
    for r in rows:
        # ---- P0 硬伤 ----
        if r['state'] == '❌无状态':
            p0.append((r, '录文状态缺失'))
        elif not r['has_quote'] and not DESCRIPTIVE.search(r['raw_state']):
            p0.append((r, '无原文引用块，且未标为说明性条目'))
        elif r['state'] == '待补原文':
            p0.append((r, '录的不是原书原文（定义式概括），须补原文'))
        # ---- P1 待补 ----
        if not r['has_usage']:
            p1.append((r, '缺「本站用法」（无法关联到正文哪一章）'))
        if '⚠️' in r['title'] and not r['has_dispute']:
            p1.append((r, '标题标了 ⚠️，块内却没有对应的 ⚠️ 说明块'))
        # ---- P2 待校 ----
        # ⚠️ 判据 = 块内有无「🔍 校核」行，不看书面的状态文字。
        #    理由：核出问题的条（如「姜维路线与史实相反」）状态仍写「需核」，
        #    但**它恰恰是核过的**——按状态文字判会把它算成「未推进」，与事实相反。
        #    有校核行 = 逐条看过并写下了结论（结论可以是「未能确认」）。
        if r['state'] in ('待校', '需核', '出处已核'):
            tag = f"{r['state']}：{r['raw_state']}"
            if r['has_note']:
                p2done.append((r, tag))
            else:
                p2.append((r, tag))

    stat = collections.Counter(r['state'] for r in rows)
    print('=' * 64)
    print(f'典籍库录文校对体检 · 共 {len(rows)} 条引文')
    print('=' * 64)
    print('\n【状态分布】')
    for k, v in stat.most_common():
        print(f'  {k:<12} {v:>4}')
    print(f"  有原文块     {sum(1 for r in rows if r['has_quote']):>4}")
    print(f"  有本站用法   {sum(1 for r in rows if r['has_usage']):>4}")
    print(f"  有 ⚠️ 说明块 {sum(1 for r in rows if r['has_dispute']):>4}")
    print(f"  有 🔍 校核行 {sum(1 for r in rows if r['has_note']):>4}")
    print(f"  标题含 ⚠️    {sum(1 for r in rows if '⚠️' in r['title']):>4}"
          "   ← ⚠️ 有两种语义（有争议 / 本站重点），后者不需争议栏，须人工抽查")

    def dump(name, items, tip):
        print(f'\n【{name}】{len(items)} 条 —— {tip}')
        for r, why in items:
            print(f"  · {r['file']}\n      {r['title'][:44]}\n      → {why}")

    dump('P0 硬伤（必须修）', p0, '状态缺失 / 原文缺失 / 录的不是原文')
    dump('P1 待补', p1, '缺关联信息 / 争议标注不闭环')

    total_p2 = len(p2) + len(p2done)
    done = len(p2done)
    print(f'\n【P2 校对进度】{done} / {total_p2} 条已推进（出处确证），余 {len(p2)} 条未动')
    if total_p2:
        bar_n = 30
        filled = round(bar_n * done / total_p2)
        print(f"  [{'█' * filled}{'·' * (bar_n - filled)}] {round(100 * done / total_p2)}%")
    print('  ✅ 已推进（出处已核·文字待校）：')
    for r, why in p2done:
        print(f"      · {r['file'].replace('原文/', '')} — {r['title'][:40]}")
    print(f"\n  ⬜ 未推进（仍标 待校/需核）{len(p2)} 条：")
    for r, why in p2[:12]:
        print(f"      · {r['file'].replace('原文/', '')} — {r['title'][:40]}")
    if len(p2) > 12:
        print(f"      … 另 {len(p2) - 12} 条，见 --csv")

    print('\n' + '=' * 64)
    if p0:
        print(f'❌ P0 {len(p0)} 条未清')
    else:
        print('✅ 无 P0 硬伤')
    print(f"⚠️  P1 {len(p1)} 条 · P2 剩 {len(p2)} 条（均需外部点校本）")
    print('=' * 64)

    if export_csv:
        out = ROOT / '校对清单.csv'
        with out.open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['级别', '文件', '引文', '状态', '问题', '有原文', '有用法', '字数'])
            for r, why in p0:
                w.writerow(['P0', r['file'], r['title'], r['raw_state'], why,
                            r['has_quote'], r['has_usage'], r['chars']])
            for r, why in p1:
                w.writerow(['P1', r['file'], r['title'], r['raw_state'], why,
                            r['has_quote'], r['has_usage'], r['chars']])
            for r, why in p2done:
                w.writerow(['P2-已核', r['file'], r['title'], r['raw_state'], why,
                            r['has_quote'], r['has_usage'], r['chars']])
            for r, why in p2:
                w.writerow(['P2-未核', r['file'], r['title'], r['raw_state'], why,
                            r['has_quote'], r['has_usage'], r['chars']])
        print(f'\n已导出：{out}')

if __name__ == '__main__':
    main()
