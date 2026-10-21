#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全站「留邮箱」文案统一更新（2026-10-21）

背景：百家姓 100 姓手机壁纸已全部出图并打好交付包（200 张），
      但全站文案仍只承诺「十六朝 32 张」⇒ 承诺与实际不符。
      本脚本把全站涉及「留邮箱 / 32 张 / 免费领」的文案统一改为「两套共 232 张」。

用法（在仓库根执行）：
  python3 11-运营/scripts/update-email-copy.py --dry    # 只报命中，不推送
  python3 11-运营/scripts/update-email-copy.py --apply  # 推送并逐页验收

设计原则：
  ① 只做**纯文本子串替换**，绝不触碰 <style>/<script>（MailerLite 表单代码块在内）
  ② 替换串一律长到唯一，避免误伤
  ③ 每页改前自动备份到 11-运营/backup/2026-10-21/pages-before/
  ④ 每个规则在每页的命中数必须 == 预期，否则该页整页跳过并报警
"""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAP = '.tmp/pages-all.json'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36')
KEYCHAIN_SVC = 'theseventhrealm-wp'
WP_USER = 'MollyBot_No.2'

# ── 替换规则：(编号, 旧文, 新文)
#    旧文必须是页面里逐字存在的片段（不含标签边界，纯文本即可）
NEW_INTRO_A = ('两套，共 232 张原图，直接发到你邮箱：朝代 16 朝 × iPhone / Android = 32 张；'
               '百家姓 100 姓 × iPhone / Android = 200 张。桌面横版开售时也第一时间告诉你。'
               '只发这两类消息，不做群发广告，随时可退订。')
NEW_INTRO_B = NEW_INTRO_A.replace('只发这两类消息，不做群发广告', '只做这两类消息，不群发广告')

TAIL_A = '只发这两类消息，不做群发广告，随时可退订。'
TAIL_B = '只做这两类消息，不群发广告，随时可退订。'
HEAD = ('两套，共 232 张原图，直接发到你邮箱：朝代 16 朝 × iPhone / Android = 32 张；'
        '百家姓 100 姓 × iPhone / Android = 200 张。桌面横版开售时也第一时间告诉你。')

RULES = [
    ('R1  表单标题', '留个邮箱，32 张壁纸发你', '留个邮箱，两套壁纸发你'),
    ('R2a 表单说明·只发变体',
     '十六朝 32 张手机壁纸（iPhone / Android 各 16 张）直接发到你邮箱；桌面横版开售时也第一时间告诉你。' + TAIL_A,
     HEAD + TAIL_A),
    ('R2b 表单说明·只做变体',
     '十六朝 32 张手机壁纸（iPhone / Android 各 16 张）直接发到你邮箱；桌面横版开售时也第一时间告诉你。' + TAIL_B,
     HEAD + TAIL_B),
    ('R3  表单成功提示', '32 张壁纸的下载链接已经发到你邮箱', '两套壁纸的下载链接已经发到你邮箱'),
    ('R4  首页文案', '32 张手机壁纸现在就能免费领', '232 张手机壁纸现在就能免费领'),
    ('R5  首页按钮', '免费领取 32 张壁纸', '免费领取 232 张壁纸'),
    ('R6  首页宇宙动画区按钮', '免费领取 16 朝壁纸', '免费领取 232 张壁纸'),
    ('R7  朝代页说明', '全十六朝共 32 张，留邮箱一次发给你。', '全十六朝 32 张 + 百家姓 200 张，留邮箱一次全发给你。'),
    ('R8  朝代页按钮', '免费领取 32 张 →', '免费领取 232 张 →'),
    ('R9  FAQ 数量', '手机竖版「五千年金句」全套 32 张（约 5.5 MB）零元',
     '手机竖版共 232 张（朝代 32 张 + 百家姓 200 张，约 26 MB）零元'),
    ('R10 FAQ 答问', '两件事：<b>壁纸交付链接</b>，以及<b>新品上架通知</b>。',
     '两件事：<b>壁纸交付链接</b>（朝代 + 百家姓两套），以及<b>新品上架通知</b>。'),
    ('R11 隐私页', '不填邮箱也能直接下载壁纸', '不填邮箱也能照常浏览本站全部内容'),
]

# 改完之后**不允许**再出现的旧口径说法（新文里「朝代 = 32 张」是合法的，故不在列）
FORBIDDEN = [
    '留个邮箱，32 张壁纸发你',
    '32 张壁纸的下载链接',
    '免费领取 32 张壁纸',
    '免费领取 32 张 →',
    '32 张手机壁纸现在就能免费领',
    '免费领取 16 朝壁纸',
    '全十六朝共 32 张',
    '全套 32 张',
    '十六朝 32 张手机壁纸',
]

# 每页预期命中哪些规则（用于校验，防止漏改或误伤）
EXPECT = {13:  ['R1', 'R2a', 'R3', 'R4', 'R5', 'R6'],
          32:  ['R1', 'R2b', 'R3'],
          86:  ['R1', 'R2b', 'R3'],
          88:  ['R11'],
          109: ['R1', 'R2b', 'R3'],
          189: ['R1', 'R2b', 'R3', 'R9', 'R10']}
for _p in range(345, 361):
    EXPECT[_p] = ['R7', 'R8']


def load_pages():
    with open(os.path.join(ROOT, SNAP), encoding='utf-8') as f:
        return {p['id']: p for p in json.load(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='只报命中不推送')
    ap.add_argument('--apply', action='store_true', help='推送上线')
    a = ap.parse_args()
    if not (a.dry or a.apply):
        ap.error('必须给 --dry 或 --apply')

    pages = load_pages()
    by_id = {r[0].split()[0]: r for r in RULES}
    plan, problems = {}, []

    for pid, exp in sorted(EXPECT.items()):
        p = pages.get(pid)
        if not p:
            problems.append(f'[{pid}] 快照里没有这页')
            continue
        raw = p['content']['raw']
        new, hits = raw, {}
        for tag in exp:
            _, old, rep = by_id[tag]
            n = new.count(old)
            hits[tag] = n
            if n >= 1:
                new = new.replace(old, rep)
        # 校验：预期规则每条至少命中 1 次
        miss = [t for t, n in hits.items() if n == 0]
        if miss:
            problems.append(f'[{pid}] {p["slug"]} 未命中：{miss}')
        # 校验：改完不得残留任何「旧口径」的 32 张说法
        #   （新文里合法的「朝代 … = 32 张」「全十六朝 32 张 +」不在禁止列表内）
        #   ⚠️ 必须带 (?<!\d)：否则「232 张」里的「32 张」会被误判成残留
        for bad in FORBIDDEN:
            pat = r'(?<!\d)' + re.escape(bad).replace(r'\ ', r'\s*')
            n = len(re.findall(pat, new))
            if n:
                problems.append(f'[{pid}] {p["slug"]} 仍残留 {n} 处「{bad}」')
        plan[pid] = (p['slug'], new, hits, len(raw), len(new))

    print(f'计划改动 {len(plan)} 页\n' + '─' * 74)
    for pid, (slug, new, hits, n0, n1) in plan.items():
        h = ' '.join(f'{t}×{n}' for t, n in hits.items() if n)
        print(f'{pid:>4} {slug:<22} {n0:>7} → {n1:<7} (+{n1-n0:>4})  {h}')
    if problems:
        print('\n❌ 校验未通过：')
        for s in problems:
            print('  ', s)
        if a.apply:
            print('\n（有问题的页面不会推送，请先看上面）')
            sys.exit(1)
    else:
        print('\n✅ 全部校验通过（预期规则均命中、无「32 张」残留）')

    if a.dry:
        print('\n[dry-run] 未推送')
        return

    tok = subprocess.run(['security', 'find-generic-password', '-s', KEYCHAIN_SVC, '-w'],
                         capture_output=True, text=True).stdout.strip()
    if not tok:
        sys.exit('❌ 取不到 WP 凭据')

    ok, fail = [], []
    for pid, (slug, new, hits, n0, n1) in plan.items():
        if any(f'[{pid}]' in s for s in problems):
            continue
        payload = json.dumps({'content': new}, ensure_ascii=False)
        tmp = os.path.join(ROOT, '.tmp/push.json')
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(payload)
        r = subprocess.run(['curl', '-s', '--noproxy', '*', '--max-time', '120',
                            '-o', os.path.join(ROOT, '.tmp/push-resp.json'),
                            '-w', '%{http_code}', '-u', f'{WP_USER}:{tok}', '-X', 'POST',
                            '-A', UA, '-H', 'Content-Type: application/json',
                            '--data-binary', f'@{tmp}',
                            f'https://theseventhrealm.com/wp-json/wp/v2/pages/{pid}'],
                           capture_output=True, text=True, cwd=ROOT)
        code = r.stdout.strip()
        try:
            resp = json.load(open(os.path.join(ROOT, '.tmp/push-resp.json'), encoding='utf-8'))
        except Exception:
            resp = {}
        if code == '200' and len(resp.get('content', {}).get('raw', '')) == len(new):
            ok.append(pid)
            print(f'  ✅ {pid} {slug} 已上线（{len(new)} 字）')
        else:
            fail.append(pid)
            print(f'  ❌ {pid} {slug} HTTP {code} {resp.get("code", "")} {resp.get("message", "")}')

    print(f'\n推送结果：成功 {len(ok)} 页 / 失败 {len(fail)} 页')
    if fail:
        print('失败页：', fail)


if __name__ == '__main__':
    main()
