#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 · 朝代页纯排版修正（引号方向 + 长段落拆分）
铁律：不增删改任何一个汉字/标点。
  ① 直引号 " -> “ ”（按文本片段内出现顺序交替）
  ② 非 verse 段落 >180 字时，在 。！？ 处插入 </p>\n<p>，最多拆成 3 段
"""
import re, sys, json

PAGES = {98: '秦', 99: '汉', 100: '三国', 101: '两晋'}


def tokenize(raw):
    """-> [(kind, text)]  kind in {'text','tag','comment'}"""
    toks = []
    i, n = 0, len(raw)
    while i < n:
        if raw.startswith('<!--', i):
            j = raw.find('-->', i + 4)
            j = n if j < 0 else j + 3
            toks.append(['comment', raw[i:j]])
            i = j
        elif raw[i] == '<':
            j = raw.find('>', i)
            if j < 0:
                toks.append(['text', raw[i:]])
                break
            toks.append(['tag', raw[i:j + 1]])
            i = j + 1
        else:
            j = raw.find('<', i)
            j = n if j < 0 else j
            toks.append(['text', raw[i:j]])
            i = j
    return toks


def protected_mask(toks):
    """注释 / <style> / <script>（含其标签本身）标记为受保护"""
    prot = [False] * len(toks)
    mode = None
    for k, (t, s) in enumerate(toks):
        if t == 'comment':
            prot[k] = True
            continue
        if mode is not None:
            prot[k] = True
        if t == 'tag':
            low = s.lower()
            if mode is None:
                m = re.match(r'<(style|script)\b', low)
                if m:
                    mode = m.group(1)
                    prot[k] = True
            elif re.match(r'</' + mode + r'\b', low):
                mode = None
    return prot


def convert_quotes(toks, prot):
    """每个未受保护的文本片段内，第 1/3/5… 个 " -> “，第 2/4/6… -> ”"""
    changed = 0
    for k, tok in enumerate(toks):
        if tok[0] != 'text' or prot[k]:
            continue
        s = tok[1]
        if '"' not in s:
            continue
        out = []
        flip = True
        for ch in s:
            if ch == '"':
                out.append('\u201c' if flip else '\u201d')
                flip = not flip
                changed += 1
            else:
                out.append(ch)
        tok[1] = ''.join(out)
    return changed


def section_ranges(toks):
    """返回 verse 区块的 token 下标区间 [start,end) 列表"""
    ranges = []
    i = 0
    while i < len(toks):
        t, s = toks[i]
        if t == 'tag' and re.match(r'<section\b', s, re.I) and re.search(r'class="[^"]*\bverse\b', s):
            depth = 1
            j = i + 1
            while j < len(toks) and depth:
                if toks[j][0] == 'tag':
                    low = toks[j][1].lower()
                    if re.match(r'<section\b', low):
                        depth += 1
                    elif re.match(r'</section\b', low):
                        depth -= 1
                j += 1
            ranges.append((i, j))
            i = j
        else:
            i += 1
    return ranges


def find_paragraphs(toks):
    """返回 [(open_idx, close_idx)]，跳过注释/样式/脚本区（其文本已被标记，但这里按标签本身判断）"""
    paras = []
    open_i = None
    for k, (t, s) in enumerate(toks):
        if t != 'tag':
            continue
        low = s.lower()
        if re.match(r'<p(\s|>)', low):
            if open_i is not None:
                raise SystemExit('错误：发现未闭合/嵌套 <p> @ %d' % k)
            open_i = k
        elif re.match(r'</p\s*>', low):
            if open_i is None:
                raise SystemExit('错误：孤立 </p> @ %d' % k)
            paras.append((open_i, k))
            open_i = None
    if open_i is not None:
        raise SystemExit('错误：文件末尾有未闭合 <p>')
    return paras


def inner_html(toks, o, c):
    return ''.join(toks[j][1] for j in range(o + 1, c))


def plain_len(html):
    return len(re.sub(r'<[^>]*>', '', html))


def choose_splits(txt, limit=180, max_seg=3, allowed=None):
    """在 。！？ 处选择最平衡的拆点；返回 plain 下标列表（升序），失败返回 None"""
    L = len(txt)
    if L <= limit:
        return []
    pool = allowed if allowed is not None else [i for i in range(1, L) if txt[i - 1] in '。！？']
    if not pool:
        return None
    best = None
    for nseg in range(2, max_seg + 1):
        import itertools
        for combo in itertools.combinations(pool, nseg - 1):
            pts = (0,) + combo + (L,)
            segs = [pts[i + 1] - pts[i] for i in range(len(pts) - 1)]
            if max(segs) > limit:
                continue
            target = L / nseg
            score = sum(abs(s - target) for s in segs)
            if best is None or score < best[0]:
                best = (score, list(combo))
        if best is not None:
            return best[1]
    return None


VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'wbr', 'area', 'base', 'col', 'embed', 'track', 'param'}


def safe_text_tokens(toks, o, c):
    """段落内每个文本 token 起始处的内联标签栈；返回 {tok_idx: stack_list}"""
    stack = []
    info = {}
    for j in range(o + 1, c):
        t, s = toks[j]
        if t == 'text':
            info[j] = list(stack)
        elif t == 'tag':
            low = s.strip().lower()
            m = re.match(r'</\s*([a-z0-9]+)', low)
            if m:
                name = m.group(1)
                if name in stack:
                    while stack and stack.pop() != name:
                        pass
            else:
                m2 = re.match(r'<\s*([a-z0-9]+)', low)
                if m2 and m2.group(1) not in VOID and not low.endswith('/>'):
                    stack.append(m2.group(1))
    return info


def split_paragraph(toks, o, c, limit=180):
    """就地记录插入点；返回插入点列表 [(tok_idx, offset)]，失败返回 None"""
    ih = inner_html(toks, o, c)
    txt = re.sub(r'<[^>]*>', '', ih)
    if len(txt) <= limit:
        return []
    info = safe_text_tokens(toks, o, c)
    # plain 下标 -> (token, offset, 是否处于内联元素内部)
    loc = {}          # p -> (j, off, safe)
    plain_pos = 0
    for j in range(o + 1, c):
        t, s = toks[j]
        if t == 'text':
            for p in range(plain_pos + 1, plain_pos + len(s) + 1):
                loc[p] = (j, p - plain_pos, len(info.get(j, [])) == 0)
            plain_pos += len(s)
    allowed = [p for p in range(1, len(txt)) if txt[p - 1] in '。！？' and loc.get(p, (0, 0, False))[2]]
    pts = choose_splits(txt, limit, allowed=allowed)
    if pts is None:
        return None
    inserts = []
    for p in pts:
        j, off, safe = loc[p]
        assert safe
        inserts.append((j, off))
    return inserts


def process(raw):
    toks = tokenize(raw)
    prot = protected_mask(toks)
    q_changed = convert_quotes(toks, prot)

    verse = section_ranges(toks)
    def in_verse(idx):
        return any(a <= idx < b for a, b in verse)

    paras = find_paragraphs(toks)
    # 段落范围内若含受保护的注释/样式标签，则跳过（保守）
    inserts = []          # (tok_idx, offset)
    skipped = []
    for o, c in paras:
        if in_verse(o):
            continue
        if any(prot[j] for j in range(o, c + 1)):
            continue
        r = split_paragraph(toks, o, c)
        if r is None:
            ih = inner_html(toks, o, c)
            skipped.append(plain_len(ih))
            continue
        inserts.extend(r)

    # 组装输出
    by_tok = {}
    for j, off in inserts:
        by_tok.setdefault(j, []).append(off)
    out = []
    for k, (t, s) in enumerate(toks):
        if k in by_tok:
            offs = sorted(set(by_tok[k]), reverse=True)
            for off in offs:
                s = s[:off] + '</p><p>' + s[off:]
        out.append(s)
    new_raw = ''.join(out)
    return new_raw, q_changed, skipped


def stats(raw):
    txt = re.sub(r'<[^>]*>', '', raw)
    toks = tokenize(raw)
    prot = protected_mask(toks)
    verse = section_ranges(toks)
    paras = find_paragraphs(toks)
    long_nonverse = 0
    long_list = []
    for o, c in paras:
        if any(a <= o < b for a, b in verse):
            continue
        if any(prot[j] for j in range(o, c + 1)):
            continue
        L = plain_len(inner_html(toks, o, c))
        if L > 180:
            long_nonverse += 1
            long_list.append((o, L, re.sub(r'<[^>]*>', '', inner_html(toks, o, c))[:40]))
    return {
        'text_len': len(txt),
        'left': raw.count('\u201c'),
        'right': raw.count('\u201d'),
        'long_nonverse': long_nonverse,
        'long_list': long_list,
        'straight_in_text': sum(s.count('"') for k, (t, s) in enumerate(toks) if t == 'text' and not prot[k]),
    }


if __name__ == '__main__':
    pid = int(sys.argv[1])
    src = '11-运营/tmp-fix/raw-%d.html' % pid
    raw = open(src, encoding='utf-8').read()
    before = stats(raw)
    new, qc, skipped = process(raw)
    after = stats(new)
    open('11-运营/tmp-fix/new-%d.html' % pid, 'w', encoding='utf-8').write(new)
    print('page', pid, PAGES[pid])
    print('  引号替换个数:', qc)
    print('  before:', before['left'], before['right'], 'long=', before['long_nonverse'], 'text=', before['text_len'], 'straight_in_text=', before['straight_in_text'])
    print('  after :', after['left'], after['right'], 'long=', after['long_nonverse'], 'text=', after['text_len'], 'straight_in_text=', after['straight_in_text'])
    print('  text preserved:', before['text_len'] == after['text_len'])
    print('  skipped(un-splittable) lens:', skipped)
    for x in after['long_list']:
        print('  REMAIN LONG:', x)
