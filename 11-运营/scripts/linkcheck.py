#!/usr/bin/env python3
"""全量断链体检：扫项目内「引用了但解析不到」的本地路径。

比 path-links-check.py 覆盖更全：Markdown 链接、HTML href/src、脚本里的
相对/绝对路径（含 ../ ）、项目外绝对路径（如 skill 资产），并抑制历史记述与示例的误报。

用法：
    python3 11-运营/scripts/linkcheck.py            # 只列真实断链
    python3 11-运营/scripts/linkcheck.py -v         # 附带被抑制项
    python3 11-运营/scripts/linkcheck.py --json     # JSON 输出

核心降噪规则：**引用必须带扩展名**（EXTS 白名单）。
因此 src="《诗经 · 商颂》" 这类出处字段、href="/novel" 这类站点路径都不会误报。
目录级引用只对「已知废弃目录名 wallpapers/ shop/」告警。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPS = ['01-内容', '02-商品', '03-页面', '04-市场', '11-运营', '10-规划', '07-课程',
        '08-音频', '09-社区', '06-品牌', '05-发布包', 'seventhrealm-child', '99-归档']
EXTS = ('(?:md|py|sh|html|png|jpg|jpeg|svg|csv|json|ttf|otf|woff2|css|txt|zip|mp3|wav|plist|pdf|epub)')

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.workbuddy', '99-归档', '05-发布包', '校样归档'}
# 历史档案与一次性脚本：其中的旧路径是「记述」而非「引用」，降级为提示不告警
ARCHIVE_PAT = re.compile(r'(?:执行申请单|REQ-|主题更新|站点补全|reports/|迁移清单|'
                         r'fix-paths\.sh|fix-deadlinks\.py|每日改动评审|README-空间结构)')
SCAN_SUFFIX = {'.md', '.py', '.sh', '.html', '.css', '.txt', '.json', '.csv', '.plist'}
ABS_ROOT = str(ROOT)

# ---- 引用提取：一律要求「带扩展名」，杜绝无扩展名串的误报 ----
# 路径 token：不含空白、不含引号，以 .ext 结尾
P = r'[\w\u4e00-\u9fff\-.%/]+?\.' + EXTS

MD_LINK = re.compile(r'!?\[[^\]]*\]\(\s*([^)\s]+)')
HTML_ATTR = re.compile(r'(?:href|src|data-src|poster)\s*=\s*["\']([^"\'\s]+)["\']')
TOP_REL = re.compile(rf'(?<![\w/])(?:{"|".join(map(re.escape, TOPS))})/(?:[\w\u4e00-\u9fff\-.%]+/)*[\w\u4e00-\u9fff\-.%]+\.{EXTS}')
DOT_REL = re.compile(rf'(?<![\w/])\.\.?/(?:[\w\u4e00-\u9fff\-.%]+/)*[\w\u4e00-\u9fff\-.%]+\.{EXTS}')
# 项目内绝对路径
ABS_IN = re.compile(rf'(?<![\w/]){re.escape(ABS_ROOT)}/(?:[\w\u4e00-\u9fff\-.%]+/)*[\w\u4e00-\u9fff\-.%]+\.{EXTS}')
# 项目外绝对路径（如 ~/.workbuddy/skills/... 的素材，被硬引用也算断链）
ABS_OUT = re.compile(r'(?<![\w/])/(?:Users|usr|Applications|private)/[\w\u4e00-\u9fff\-.%]+(?:/[\w\u4e00-\u9fff\-.%]+)*\.' + EXTS)
# 已知废弃目录名（目录级，无扩展名）
BARE_DIR = re.compile(r'(?<![\w/./-])(wallpapers|shop)(?=/[\w\u4e00-\u9fff\-.%])')

EXTERNAL = re.compile(r'^(?:https?:)?//|^https?:|^mailto:|^tel:|^data:|^javascript:|^file:|^#|^\{\{|^\$')
PLACEHOLDER = re.compile(r'[*?<>%s]|\$[A-Za-z_{]|\{[a-zA-Z_]+\}|__[A-Z_]+__|\b(?:xxx|foo|bar|example|sample)\b', re.I)
# 历史记述标记
NARRATIVE = re.compile(r'已(?:并入|归入|迁移|移除|改|废弃|删除|清空|收编)|归入|迁移到|迁移至|废弃|已不再|'
                       r'原\s|旧\s|曾经|此前|更名为|改名为|→|->|收编|合并到|不再使用|历史|存档|备份于|原为')
# 脚本自身在定义正则（不是引用）
SELF_REGEX_DEF = re.compile(r're\.compile|EXTS\s*=|TOPS\s*=|ABS_ROOT\s*=|BARE_DIR\s*=|\bP\s*=\s*r')


HAS_EXT = re.compile(r'\.' + EXTS + r'$', re.I)


def classify(raw: str) -> bool:
    """True = 需要检查存在性。"""
    if not raw:
        return False
    if EXTERNAL.search(raw):
        return False
    if PLACEHOLDER.search(raw):
        return False
    # 站点路径（以 / 开头但不属于本项目）→ 不是本地文件引用
    if raw.startswith('/') and not raw.startswith(ABS_ROOT + '/'):
        return False
    # 必须带扩展名，否则多半是路由或出处字段
    if not HAS_EXT.search(raw):
        return False
    return True


def resolve(raw: str, base: Path):
    raw = raw.split('#')[0].split('?')[0].strip()
    if not raw:
        return None
    if raw.startswith('/'):
        cands = [Path(raw)]
        # 项目外绝对路径也可能是相对 HOME 的简写
    else:
        cands = [base / raw, ROOT / raw]
    for c in cands:
        try:
            if c.exists():
                return c
        except OSError:
            continue
    return None


def scan_file(path: Path):
    rel0 = str(path.relative_to(ROOT))
    is_archive = bool(ARCHIVE_PAT.search(rel0))
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return [], []
    base, dead, supp = path.parent, [], []
    is_py = path.suffix == '.py'

    for lineno, line in enumerate(text.splitlines(), 1):
        line2 = re.sub(r'https?://\S+', '', line)
        line2 = re.sub(r'\bfile://\S+', '', line2)
        narrative = bool(NARRATIVE.search(line2))
        if is_py and SELF_REGEX_DEF.search(line2):
            continue

        cands = []
        for m in MD_LINK.finditer(line2):
            cands.append((m.group(1), 'Markdown链接'))
        for m in HTML_ATTR.finditer(line2):
            cands.append((m.group(1), 'HTML属性'))
        for pat, kind in ((ABS_IN, '项目内绝对路径'), (ABS_OUT, '项目外绝对路径'),
                          (DOT_REL, '相对路径'), (TOP_REL, '顶层目录路径')):
            for m in pat.finditer(line2):
                cands.append((m.group(0), kind))
        for m in BARE_DIR.finditer(line2):
            (supp if narrative else dead).append((lineno, m.group(0) + '/', '废弃目录名'))

        seen = set()
        for raw, kind in cands:
            if raw in seen:
                continue
            seen.add(raw)
            if not classify(raw):
                continue
            if resolve(raw, base) is None:
                (supp if narrative else dead).append((lineno, raw, kind))
    return dead, supp


def main():
    as_json = '--json' in sys.argv
    verbose = '-v' in sys.argv
    dead_all, supp_all = [], []
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix not in SCAN_SUFFIX:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        rel = str(path.relative_to(ROOT))
        d, s = scan_file(path)
        bucket = supp_all if ARCHIVE_PAT.search(rel) else dead_all
        for lineno, raw, kind in d:
            bucket.append({'file': rel, 'line': lineno, 'ref': raw, 'kind': kind})
        for lineno, raw, kind in s:
            supp_all.append({'file': rel, 'line': lineno, 'ref': raw, 'kind': kind})

    if as_json:
        print(json.dumps({'dead': dead_all, 'suppressed': supp_all}, ensure_ascii=False, indent=2))
        return

    print('扫描根：%s' % ROOT)
    print('真实断链 %d 处（涉及 %d 个文件）；抑制 %d 处\n'
          % (len(dead_all), len({x['file'] for x in dead_all}), len(supp_all)))
    if not dead_all:
        print('✅ 未发现真实断链')
        return
    by_file = {}
    for r in dead_all:
        by_file.setdefault(r['file'], []).append(r)
    for f, items in sorted(by_file.items()):
        print('  %s' % f)
        for it in items[:12]:
            print('      L%-4d %-60s [%s]' % (it['line'], it['ref'][:60], it['kind']))
        if len(items) > 12:
            print('      … 另有 %d 处' % (len(items) - 12))
    if verbose:
        print('\n--- 被抑制项前 30 条 ---')
        for it in supp_all[:30]:
            print('  %-38s L%-4d %-44s [%s]' % (it['file'][:38], it['line'], it['ref'][:44], it['kind']))


if __name__ == '__main__':
    main()
