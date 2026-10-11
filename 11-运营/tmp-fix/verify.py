#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 new-<ID>.html 做全面体检：只允许 ①引号方向修正 ②插 </p><p>"""
import re, sys, difflib
sys.path.insert(0, '11-运营/tmp-fix')
from fix_typo import (tokenize, protected_mask, find_paragraphs, inner_html,
                      plain_len, section_ranges, VOID)

VOIDP = VOID | {'p'}


def balance_check(raw, label):
    """全文档标签栈平衡检查（忽略 void 与自闭合）"""
    toks = tokenize(raw)
    prot = protected_mask(toks)
    stack = []
    for k, (t, s) in enumerate(toks):
        if t != 'tag' or prot[k]:
            continue
        low = s.strip().lower()
        m = re.match(r'</\s*([a-z0-9]+)', low)
        if m:
            name = m.group(1)
            if not stack or stack[-1] != name:
                return '%s: 标签不匹配 </%s> at tok %d, stack tail=%s' % (label, name, k, stack[-3:])
            stack.pop()
        else:
            m2 = re.match(r'<\s*([a-z0-9]+)', low)
            if m2 and m2.group(1) not in VOID and not low.endswith('/>'):
                stack.append(m2.group(1))
    return None if not stack else '%s: 未闭合 %s' % (label, stack)


def para_balance(raw, label):
    """每个 <p> 内部的内联标签必须自平衡"""
    toks = tokenize(raw)
    prot = protected_mask(toks)
    for o, c in find_paragraphs(toks):
        if any(prot[j] for j in range(o, c + 1)):
            continue
        stack = []
        for j in range(o + 1, c):
            t, s = toks[j]
            if t != 'tag':
                continue
            low = s.strip().lower()
            m = re.match(r'</\s*([a-z0-9]+)', low)
            if m:
                if not stack or stack[-1] != m.group(1):
                    return '%s: <p>@%d 内联标签不匹配' % (label, o)
                stack.pop()
            else:
                m2 = re.match(r'<\s*([a-z0-9]+)', low)
                if m2 and m2.group(1) not in VOID and not low.endswith('/>'):
                    stack.append(m2.group(1))
        if stack:
            return '%s: <p>@%d 未闭合 %s' % (label, o, stack)
    return None


def audit(pid):
    old = open('11-运营/tmp-fix/raw-%d.html' % pid, encoding='utf-8').read()
    new = open('11-运营/tmp-fix/new-%d.html' % pid, encoding='utf-8').read()
    errs = []
    # 1. 字符级 diff：只允许引号替换 / 插入 </p><p>
    sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
    nq = ns = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        a, b = old[i1:i2], new[j1:j2]
        if b == '</p><p>' and a == '':
            ns += 1
        elif tag == 'replace' and len(a) == len(b) and set(a) == {'"'} and set(b) <= {'\u201c', '\u201d'}:
            nq += len(a)
        else:
            errs.append('非法改动 %s old=%r new=%r' % (tag, a[:50], b[:50]))
    # 2. 分片合并验证（把新文里的 </p><p> 去掉、弯引号还原，必须逐字等于旧文）
    merged = new.replace('</p><p>', '')
    # 只在“新产生的”弯引号处还原：用 diff 已知 nq 个，逐个还原为 "
    # 简化：把所有弯引号还原后与旧文把所有弯引号还原后比较
    norm = lambda s: s.replace('\u201c', '"').replace('\u201d', '"')
    if norm(merged) != norm(old):
        errs.append('合并后正文不一致')
    # 3. 去标签纯文本长度
    ot = re.sub(r'<[^>]*>', '', old)
    nt = re.sub(r'<[^>]*>', '', new)
    nt_nospace = re.sub(r'<[^>]*>', '', new)
    if len(ot) != len(nt):
        errs.append('纯文本长度不一致 %d -> %d' % (len(ot), len(nt)))
    # 4. 引号计数
    left, right = new.count('\u201c'), new.count('\u201d')
    if not (left >= right - 1):
        errs.append('引号失衡 L=%d R=%d' % (left, right))
    # 5. 残留直引号（正文）
    toks = tokenize(new)
    prot = protected_mask(toks)
    straight = sum(s.count('"') for k, (t, s) in enumerate(toks) if t == 'text' and not prot[k])
    if straight:
        errs.append('正文残留直引号 %d' % straight)
    # 6. 超长非 verse 段落
    verse = section_ranges(toks)
    over = []
    for o, c in find_paragraphs(toks):
        if any(a <= o < b for a, b in verse):
            continue
        if any(prot[j] for j in range(o, c + 1)):
            continue
        L = plain_len(inner_html(toks, o, c))
        if L > 180:
            over.append(L)
    # 7. 段落数 / 单段最长
    if any(a <= o < b for a, b in verse):
        pass
    # 8. 结构
    for f in (balance_check(new, 'new-%d' % pid), para_balance(new, 'new-%d' % pid)):
        if f:
            errs.append(f)
    return dict(pid=pid, quotes_left=left, quotes_right=right, splits=ns, quote_repl=nq,
                text_len_before=len(ot), text_len_after=len(nt), over=over, errs=errs)


if __name__ == '__main__':
    allok = True
    for pid in (98, 99, 100, 101):
        r = audit(pid)
        ok = not r['errs'] and not r['over']
        allok &= ok
        print('PAGE %d  引号 %d/%d  拆分段 %d  引号改写 %d  文本长度 %d->%d  超长段落 %s  %s'
              % (r['pid'], r['quotes_left'], r['quotes_right'], r['splits'], r['quote_repl'],
                 r['text_len_before'], r['text_len_after'], r['over'] or '无',
                 'OK' if not r['errs'] else '错误: ' + '; '.join(r['errs'])))
    print('ALL CLEAN' if allok else 'HAS ISSUES')
