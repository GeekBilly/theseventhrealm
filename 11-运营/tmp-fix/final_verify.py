#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最终校验：线上 raw vs 排版前备份
只允许 ①" -> “” ②插入 </p><p>
"""
import json, re, sys, difflib
sys.path.insert(0, '11-运营/tmp-fix')
from fix_typo import (tokenize, protected_mask, find_paragraphs, inner_html,
                      plain_len, section_ranges, VOID)

BK = '11-运营/风险管控/站点改动备份-20261002'
NAMES = {98: '秦', 99: '汉', 100: '三国', 101: '两晋'}
OUT = []


def tag_stack_errors(raw):
    toks = tokenize(raw)
    prot = protected_mask(toks)
    stack = []
    for k, (t, s) in enumerate(toks):
        if t != 'tag' or prot[k]:
            continue
        low = s.strip().lower()
        m = re.match(r'</\s*([a-z0-9]+)', low)
        if m:
            if not stack or stack[-1] != m.group(1):
                return '标签不匹配 </%s> near %d' % (m.group(1), k)
            stack.pop()
        else:
            m2 = re.match(r'<\s*([a-z0-9]+)', low)
            if m2 and m2.group(1) not in VOID and not low.endswith('/>'):
                stack.append(m2.group(1))
    return None if not stack else '未闭合 %s' % stack


for pid, name in NAMES.items():
    old = open('%s/page-%d-%s-排版前.raw.html' % (BK, pid, name), encoding='utf-8').read()
    new = json.load(open('11-运营/tmp-fix/out/final-%d.json' % pid))['content']['raw']
    errs = []

    # A. 字符级 diff 白名单
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    nq = ns = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        a, b = old[i1:i2], new[j1:j2]
        if a == '' and b == '</p><p>':
            ns += 1
        elif tag == 'replace' and len(a) == len(b) and set(a) == {'"'} and set(b) <= {'\u201c', '\u201d'}:
            nq += len(a)
        else:
            errs.append('非法改动 %s %r -> %r' % (tag, a[:40], b[:40]))

    # B. 合并后正文（引号归一）必须逐字相同
    norm = lambda s: s.replace('\u201c', '"').replace('\u201d', '"')
    if norm(new.replace('</p><p>', '')) != norm(old):
        errs.append('正文（去标签前后）不一致')

    # C. 纯文本长度
    t_old = re.sub(r'<[^>]*>', '', old)
    t_new = re.sub(r'<[^>]*>', '', new)

    # D. 引号
    left, right = new.count('\u201c'), new.count('\u201d')
    if left < right - 1:
        errs.append('引号失衡')

    # E. 正文残留直引号
    toks = tokenize(new)
    prot = protected_mask(toks)
    straight = sum(s.count('"') for k, (t, s) in enumerate(toks) if t == 'text' and not prot[k])
    if straight:
        errs.append('正文残留直引号 %d' % straight)

    # F. 超长非 verse 段落
    verse = section_ranges(toks)
    long_before = long_after = 0
    for o, c in find_paragraphs(tokenize(old)):
        pass
    vt = section_ranges(tokenize(old))
    pt = tokenize(old)
    pr = protected_mask(pt)
    for o, c in find_paragraphs(pt):
        if any(a <= o < b for a, b in vt):
            continue
        if any(pr[j] for j in range(o, c + 1)):
            continue
        if plain_len(inner_html(pt, o, c)) > 180:
            long_before += 1
    over = []
    for o, c in find_paragraphs(toks):
        if any(a <= o < b for a, b in verse):
            continue
        if any(prot[j] for j in range(o, c + 1)):
            continue
        L = plain_len(inner_html(toks, o, c))
        if L > 180:
            long_after += 1
            over.append(L)

    e = tag_stack_errors(new)
    if e:
        errs.append(e)
    if len(t_old) != len(t_new):
        errs.append('纯文本长度不一致 %d -> %d' % (len(t_old), len(t_new)))

    OUT.append(dict(id=pid, name=name, quotes_left=left, quotes_right=right,
                    long_before=long_before, long_after=long_after,
                    text_len_before=len(t_old), text_len_after=len(t_new),
                    ok=(not errs), errs=errs, splits=ns, quote_repl=nq, over=over))

for r in OUT:
    print(json.dumps({k: v for k, v in r.items() if k != 'errs'}, ensure_ascii=False))
    if r['errs']:
        print('   ERRORS:', r['errs'])
print()
print('RESULT JSON:')
clean = [{k: v for k, v in r.items() if k not in ('errs', 'splits', 'quote_repl', 'over')} for r in OUT]
print(json.dumps(clean, ensure_ascii=False))
print()
print('splits:', [(r['id'], r['splits'], r['quote_repl'], r['over']) for r in OUT])
