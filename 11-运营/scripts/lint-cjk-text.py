#!/usr/bin/env python3
"""中文文档交付前的字符体检：拦截「生成过程混入」的字符残渣。

起因（务必记住）：
2026-09-30 一次会话里，同一批文件先后混进了这些肉眼极难发现的东西——
    非中文语系字符、孤立英文短语、HTML 实体、LaTeX 残渣。
（本段是说明用的样例，故意触发全部检查，故整段豁免）  lint-ignore

用法：
    python3 11-运营/scripts/lint-cjk-text.py <文件...>
    python3 11-运营/scripts/lint-cjk-text.py --recent 5
    python3 11-运营/scripts/lint-cjk-text.py --strict <文件...>   # 加查英文混排

默认只查三项「高信噪比」的（正常中文文档里不该出现）：
    ① 非中文语系字符（阿拉伯/西里尔/希腊/希伯来/天城体/泰文）
    ② HTML 实体残渣
    ③ LaTeX 残渣（形如 $x^{2}$）

--strict 追加两项「低信噪比」检查（技术文档里英文本就满天飞，误报多）：
    ④ 两侧被中文夹住的孤立拉丁词
    ⑤ 中文后紧跟的英文短语

退出码：0=干净 / 1=发现可疑
原则：只报位置与原文，**绝不自动修改**——批量替换盲改会把正常的也改坏。
单行豁免：在该行任意位置写 lint-ignore 即可跳过该行。
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CJ = '\u4e00-\u9fff'
CJK_PUNCT = '，。、；：！？（）'
CJK_QUOTE = '\u201c\u201d\u2018\u2019'
BOUNDARY = CJ + CJK_PUNCT + CJK_QUOTE

# ① 非中文语系字符（正常中文文档里绝不该出现）
FOREIGN = re.compile(
    '[\u0400-\u04ff]'                  # 西里尔
    '|[\u0600-\u06ff\u0700-\u074f]'    # 阿拉伯语 / 叙利亚语
    '|[\u0370-\u03ff\u1f00-\u1fff]'    # 希腊语
    '|[\u0590-\u05ff]'                 # 希伯来语
    '|[\u0900-\u097f]'                 # 天城体
    '|[\u0e00-\u0e7f]'                 # 泰文
)

# ② HTML 实体残渣（正文里出现基本都是误转义）
ENTITY = re.compile(r'&(amp|lt|gt|quot|nbsp|#39);')

# ③ LaTeX 残渣：要求两个 $ 之间含 \ ^ _ 才算公式，避免误伤 JS 模板串 ${x}px
LATEX = re.compile(r'\$(?=[^$\n]{0,25}[\\^_])[^$\n]{1,25}\$')

# ④ 两侧被中文夹住的孤立拉丁单词（--strict）
LATIN = re.compile('[' + BOUNDARY + r']\s*'
                   r'([A-Za-z][A-Za-z\-]{2,})\s*'
                   '[' + BOUNDARY + ']')

# ⑤ 中文后紧跟多个连续英文字的短语（--strict）
PHRASE = re.compile('[' + BOUNDARY + r']\s+'
                    r'([A-Za-z]{3,}(?:\s+[A-Za-z]{2,}){1,3})'
                    r'(?=[\s' + CJK_PUNCT + ']|$)')

ALLOW = {
    'SQL', 'SEO', 'JSON', 'XML', 'CSV', 'HTML', 'CSS', 'JS', 'API', 'REST',
    'URL', 'HTTP', 'HTTPS', 'CDN', 'DNS', 'SSL', 'TLS', 'FAQ', 'SSH', 'App',
    'macOS', 'Linux', 'Android', 'WP', 'PHP', 'ID', 'IDs', 'UID', 'OK', 'OFL',
    'WordPress', 'Gumroad', 'Cloudflare', 'Stripe', 'PayPal', 'MailerLite',
    'Etsy', 'Wayback', 'GitHub', 'Python', 'ImageGen', 'VideoGen',
    'excerpt', 'slug', 'status', 'content', 'title', 'sitemap', 'trackback',
    'publish', 'parent', 'delete', 'link', 'code', 'message', 'apex', 'closed',
    'meta', 'Yoast', 'FAQPage', 'Google', 'Baidu', 'description',
    'ops', 'README', 'BOM', 'body', 'anchor', 'GDPR', 'GSC', 'IndexNow',
    'Bing', 'DuckDuckGo', 'token', 'automation', 'prompt', 'list', 'launchd',
    'plist', 'multipart', 'raw', 'zip', 'mailto', 'privacy',
}


def lint(path: Path, strict: bool = False):
    """按文件类型分流：代码里英文与 $VAR 是常态，别拿正文标准去卡它。"""
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        return [(0, '无法读取', str(e))]

    is_code = path.suffix in {'.sh', '.py', '.js', '.css'}
    issues = []
    in_style = False

    for i, line in enumerate(text.splitlines(), 1):
        if 'lint-ignore' in line:
            continue

        if re.search(r'<style[\s>]', line, re.I):
            in_style = True
        if re.search(r'</style>', line, re.I):
            in_style = False
            continue

        # 三项高信噪比检查：任何文件、任何语言都不该出现
        for m in FOREIGN.finditer(line):
            issues.append((i, '非中文语系字符', repr(m.group(0))))
        # 属性行里的实体常是 URL 参数分隔符的正确转义  lint-ignore
        # 不是残渣 —— 跳过，否则每次都会刷一条假警报。
        if not re.search(r'(href|src)\s*=\s*["\']', line):
            for m in ENTITY.finditer(line):
                issues.append((i, 'HTML 实体残渣', m.group(0)))
        if not is_code:
            # 代码文件里 $ 是变量，不查 LaTeX
            for m in LATEX.finditer(line):
                issues.append((i, 'LaTeX 残渣', m.group(0)[:40]))

        if not strict or is_code or in_style:
            continue
        # CSS 声明行与 HTML 标签行：类名属性不是正文
        if re.search(r'<[a-zA-Z/!]|\{|\}', line):
            continue

        for m in LATIN.finditer(line):
            w = m.group(1)
            if w not in ALLOW and w.lower() not in {a.lower() for a in ALLOW}:
                issues.append((i, '中文中孤立拉丁词', w))
        for m in PHRASE.finditer(line):
            if m.group(1).strip() not in ALLOW:
                issues.append((i, '中文中英文短语混入', m.group(1).strip()))
    return issues


def recent_files(n: int):
    """最近 2 小时改动的文件。不用 find -newermt：本机 BSD find 行为不可靠。"""
    import time
    cutoff = time.time() - 2 * 3600
    exts = {'.md', '.html', '.sh', '.py'}
    skip_dirs = {'.git', 'node_modules', '__pycache__', '99-归档', '.workbuddy'}
    found = []
    for f in ROOT.rglob('*'):
        if not f.is_file() or f.suffix not in exts:
            continue
        if any(part in skip_dirs for part in f.relative_to(ROOT).parts):
            continue
        try:
            if f.stat().st_mtime >= cutoff:
                found.append(f)
        except OSError:
            continue
    found.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return found[:n]


def main():
    args = sys.argv[1:]
    strict = '--strict' in args
    args = [a for a in args if a != '--strict']

    if args and args[0] == '--recent':
        files = recent_files(int(args[1]) if len(args) > 1 else 5)
        if not files:
            print('近 2 小时无改动的 md|html|sh|py 文件。')
            return 0
    elif args:
        files = [Path(a) for a in args]
    else:
        print(__doc__)
        return 0

    print('检查模式：' + ('严格（含英文混排）' if strict else '默认（三项高信噪比）'))
    total = 0
    for f in files:
        p = f if f.is_absolute() else ROOT / f
        if not p.exists():
            print('\n  文件不存在：' + str(f))
            continue
        issues = lint(p, strict)
        rel = p.relative_to(ROOT) if str(p).startswith(str(ROOT)) else p
        if not issues:
            print('  通过：' + str(rel))
            continue
        print('\n  可疑：' + str(rel) + '  （' + str(len(issues)) + ' 处）')
        for line_no, kind, detail in issues[:12]:
            print('      L' + str(line_no) + '  [' + kind + ']  ' + detail)
        if len(issues) > 12:
            print('      ... 另有 ' + str(len(issues) - 12) + ' 处')
        total += len(issues)

    print('\n===== 可疑字符合计：' + str(total) + ' =====')
    if total:
        print('提示：逐条人工确认后修正；需要单行豁免时在该行写 lint-ignore。')
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())
