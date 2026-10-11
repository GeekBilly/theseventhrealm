#!/usr/bin/env python3
"""扫项目里「引用了但已不存在」的本地路径（文档/脚本里的死链）+ 命名规范体检。

用法：
    python3 11-运营/scripts/path-links-check.py                 # 全量：断链 + 命名
    python3 11-运营/scripts/path-links-check.py --links-only    # 只查断链
    python3 11-运营/scripts/path-links-check.py --json          # JSON 输出（供其他脚本用）
    python3 11-运营/scripts/path-links-check.py --show-skipped  # 连被豁免的留痕一起列出

判定规则：
- 只认「像项目路径」的串：以已知顶层目录名开头，或带项目相关扩展名，或绝对路径
- 排除 http(s)://、email、CSS 变量、纯文件名、/wp-content 等站上路径
- 相对路径按项目根解析；绝对路径按原样检查

豁免机制（2026-09-30 加）：历史叙述里的旧路径是**有意保留**的（改了反而失真），
用三种方式让体检只报「真会出错」的：
    1. 行级：该行任意位置含  deadlinks-ignore
    2. 文件级：文件前 30 行任意位置含  deadlinks-ignore-file
    3. 文件名前缀：每日改动评审- / 迁移清单- / 清理清单- / 记忆整理-
       （脚本产物，天然在记录"当时有哪些文件、叫什么名"）
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOPS = ['01-内容', '02-商品', '03-页面', '04-市场', '11-运营', '10-规划', '07-课程',
        '08-音频', '09-社区', '06-品牌', '05-发布包', 'seventhrealm-child', '99-归档']
EXTS = r'(?:md|py|sh|html|png|jpg|jpeg|svg|csv|json|ttf|woff2|css|txt|zip|mp3)'
ABS_ROOT = str(ROOT)

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.workbuddy', '99-归档'}
SKIP_SUFFIX = {'.bak'}
# 这两个脚本的「旧目录名」是规则数据本身，不是失效引用，跳过避免噪音
SKIP_FILES = {'11-运营/scripts/path-links-check.py', '11-运营/scripts/fix-deadlinks.py'}

# 脚本产物 / 一次性清单：内容天生是历史路径记录，不参与断链判定
SKIP_NAME_PREFIX = ('每日改动评审-', '迁移清单-', '清理清单-', '记忆整理-', '积分仪表盘-', '舆情周报-')
# 备份 / 校样 / 归档类目录里的旧路径是"当时快照"，天然不该修
SKIP_PATH_PARTS = {'备份', '校样归档', '06-归档', '02-素材'}

IGNORE_LINE = 'deadlinks-ignore'
IGNORE_FILE = 'deadlinks-ignore-file'

# 形如 02-商品/05-承接站/样张/xxx.png 或 /Users/.../02-商品/...
REL = re.compile(rf'(?<![\w/])({"|".join(map(re.escape, TOPS))})/[\w\u4e00-\u9fff\-. /]+?\.{EXTS}')
ABSO = re.compile(rf'(?<![\w/]){re.escape(ABS_ROOT)}/[\w\u4e00-\u9fff\-. /]+?\.{EXTS}')

# Markdown 内部的相对引用（2026-09-30 补）：`../04-史部别体/xx.md`、[x](xx.md) 这类
# 不以顶层目录名开头，REL 抓不到 —— 典籍库录文曾因此潜伏 7 处死链。
MD_REF_BT = re.compile(r'`([^`\n]*?\.md)`')          # 反引号里的 .md
MD_REF_LK = re.compile(r'\]\(([^)\n]+\.md)\)')       # markdown 链接里的 .md
# 裸文件名引用的「已废弃目录名」——2026-09-29/30 两次改名前的旧貌
# 英文旧目录名：宽松匹配（wallpapers/xxx 一定是路径）
BARE_DIR = re.compile(
    r'(?<![\w/./-])(wallpapers|shop|ops|course|audio|community|plans|_archive'
    r'|era-pages|02-商品/名录|02-商品/承接站|03-页面/_backup|03-页面/dynasty)'
    r'/[\w\u4e00-\u9fff\-.]+'
)
# 中文旧目录名：必须后接"像文件名的串"，否则「品牌/网站」这类并列词组会被误判
BARE_DIR_CN = re.compile(
    r'(?<![\w/./-])(品牌|发布包|在先使用证据|01-内容/长卷)'
    r'/[\w\u4e00-\u9fff\-.]+?\.(?:md|py|sh|html|png|jpg|jpeg|svg|csv|json|txt|zip|css)'
)

# ---------- 命名规范 ----------
L1_OK = re.compile(r'^\d{2}-[\u4e00-\u9fff]{2,4}$')          # NN-中文名
L1_EXCEPT = {'seventhrealm-child'}                            # WP 主题 slug，唯一例外
L2_EN_OK = {'scripts', 'reports', 'data', 'backup'}           # 11-运营 下保留的四个英文目录
L2_NUM = re.compile(r'^\d{2}-[\u4e00-\u9fff]{2,6}$')          # 二级也允许 NN-中文名（分段编号）
BAD_NAME_WORDS = ('最终', '最新', 'final', 'FINAL', '副本', '旧版', '新建')
DATE_COMPACT = re.compile(r'(?<!\d)20\d{6}(?!\d)')            # 20260930 → 建议 2026-09-30
DATETIME_COMPACT = re.compile(r'(?<!\d)20\d{6}-\d{6}(?!\d)')  # 20260930-113655 合法，不报
SPACE_OK = ('THE SEVENTH REALM',)                             # 品牌英文名固定写法，商标证据链需保持一致


def scan_md_refs(path: Path, lines):
    """扫 .md 里的相对引用（REL 抓不到的那些），返回 {lineno: [(raw, kind)]}。

    只报「带目录层级」的相对引用（作者显然在指某个具体位置）；
    纯裸文件名不报——那多半是叙述性提及，报了全是噪音。
    """
    out = {}
    in_fence = False
    for lineno, line in enumerate(lines, 1):
        if line.lstrip().startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:            # 代码块里的路径是命令示例，不是链接
            continue
        raws = [m.group(1).strip() for m in MD_REF_BT.finditer(line)]
        raws += [m.group(1).strip() for m in MD_REF_LK.finditer(line)]
        for raw in raws:
            if raw.startswith(('http', '#', '/')) or '<' in raw:
                continue                                  # 外链 / 锚点 / 绝对路径 / <slug> 占位
            if any(raw.startswith(t + '/') for t in TOPS):
                continue                                  # 顶层相对路径由 REL 负责，避免重复
            if '/' not in raw:
                continue                                  # 裸文件名：叙述性提及，不报
            # 相对引用要「两种基准都试」：作者可能按引用文件所在目录写，也可能按项目根写。
            # ⚠️ 2026-10-04 修：原来只试 path.parent → 根目录里的 research/、bjx/ 这类
            #    非 TOPS 目录被这种方式引用时全被误报成死链（文件其实存在）。
            #    ⇒ 先所在目录、后项目根，**两处都不存在才报**。
            if not (path.parent / raw).exists() and not (ROOT / raw).exists():
                out.setdefault(lineno, []).append((raw, '相对引用'))
    return out


def scan_file(path: Path):
    """返回 (hits, skipped)；hits 为待处理，skipped 为被豁免的留痕。"""
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return [], []
    lines = text.splitlines()
    head = '\n'.join(lines[:30])
    if IGNORE_FILE in head:
        return [], []
    hits, skipped = [], []
    md_refs = scan_md_refs(path, lines) if path.suffix == '.md' else {}
    for lineno, line in enumerate(lines, 1):
        if 'http://' in line or 'https://' in line and re.search(r'https?://\S*?#', line):
            line2 = re.sub(r'https?://\S+', '', line)
        else:
            line2 = line
        row_hits = []
        bare = [m.group(0) for m in BARE_DIR.finditer(line2)]
        bare += [m.group(0) for m in BARE_DIR_CN.finditer(line2)]
        for b in bare:
            row_hits.append((lineno, b, '已知废弃目录名'))
        for pat, is_abs in ((ABSO, True), (REL, False)):
            for m in pat.finditer(line2):
                raw = m.group(0).strip()
                if any(raw.startswith(b) for b in bare):
                    continue                      # 已被废弃目录名捕获，去重
                target = Path(raw) if is_abs else (ROOT / raw)
                if not target.exists():
                    row_hits.append((lineno, raw, '绝对路径' if is_abs else '相对路径'))
        for raw, kind in md_refs.get(lineno, []):
            if not any(r == raw for _, r, _ in row_hits):
                row_hits.append((lineno, raw, kind))
        if not row_hits:
            continue
        if IGNORE_LINE in line:
            skipped.extend(row_hits)
        else:
            hits.extend(row_hits)
    return hits, skipped


def check_naming():
    """目录 / 文件名规范体检，返回 (issues, hints)。

    issues = 违反 README-空间结构.md「文件命名规范」的硬伤；
    hints  = 规范里允许的写法，只是可以更统一（如一次性清单用紧凑日期）。
    """
    issues, hints = [], []
    for path in sorted(ROOT.iterdir()):
        if not path.is_dir() or path.name.startswith('.'):
            continue
        if path.name in L1_EXCEPT:
            continue
        if not L1_OK.match(path.name):
            issues.append({'kind': '一级目录', 'path': path.name,
                           'hint': '应为 NN-中文名（如 12-某某），99 为归档'})
            continue
        if path.name == '99-归档':          # 归档只留痕，不参与规范检查
            continue
        for sub in sorted(path.iterdir()):
            if not sub.is_dir() or sub.name.startswith('.'):
                continue
            if sub.name in SKIP_DIRS:
                continue                              # __pycache__ / node_modules 等技术目录不谈中文命名
            if path.name == 'seventhrealm-child':
                continue
            if sub.name in L2_EN_OK and path.name == '11-运营':
                continue
            if re.match(r'^[\u4e00-\u9fff]{2,6}$', sub.name) or L2_NUM.match(sub.name):
                # 二级合规 → 顺带查三级（2026-09-30 补：典籍库 原文/ 下 11 个 NN-中文名此前无人查）
                for sub3 in sorted(sub.iterdir()):
                    if not sub3.is_dir() or sub3.name.startswith('.'):
                        continue
                    if sub3.name in SKIP_DIRS or sub3.name in L2_EN_OK:
                        continue
                    if SKIP_PATH_PARTS & set(sub3.relative_to(ROOT).parts):
                        continue                      # 归档/备份/素材：带日期的快照目录名天然不合"中文短名"
                    if (re.match(r'^[\u4e00-\u9fff]{2,6}$', sub3.name)
                            or re.match(r'^\d{2}-[\u4e00-\u9fff]{2,10}$', sub3.name)):
                        continue
                    issues.append({'kind': '三级目录', 'path': f'{path.name}/{sub.name}/{sub3.name}',
                                   'hint': '应为中文短名（2–6 字）或 NN-中文名（如 01-正史）'})
                continue
            issues.append({'kind': '二级目录', 'path': f'{path.name}/{sub.name}',
                           'hint': '应为中文短名（2–6 字）或 NN-中文名；仅 11-运营 下可保留 scripts/reports/data/backup'})
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix in SKIP_SUFFIX:
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        name = path.name
        if name in ('.DS_Store',) or name.startswith('.tmp'):
            continue                                  # 系统文件 / 脚本临时 payload
        if SKIP_PATH_PARTS & set(rel.parts):
            continue                                  # 备份·校样·归档·素材：只留痕，不谈规范
        if DATETIME_COMPACT.search(name):
            continue                                  # 精确到秒的时间戳文件名合法（备份快照）
        if ' ' in name and not any(s in name for s in SPACE_OK):
            issues.append({'kind': '文件名', 'path': str(rel), 'hint': '含空格，改用连字符'})
        elif name.startswith('_') or name.startswith('.'):
            issues.append({'kind': '文件名', 'path': str(rel), 'hint': '下划线/点号开头，归档请移入 99-归档/'})
        elif any(w in name for w in BAD_NAME_WORDS):
            issues.append({'kind': '文件名', 'path': str(rel), 'hint': '含"最终/最新/副本"等临时词，用版本号或日期'})
        elif DATE_COMPACT.search(name):
            hints.append({'kind': '文件名', 'path': str(rel),
                          'hint': '紧凑日期 20260930（规范允许用于一次性清单，周期性产出建议 2026-09-30）'})
    return issues, hints


def main():
    as_json = '--json' in sys.argv
    show_skipped = '--show-skipped' in sys.argv
    links_only = '--links-only' in sys.argv
    results, skipped = [], []
    for path in ROOT.rglob('*'):
        if not path.is_file() or path.suffix in SKIP_SUFFIX:
            continue
        rel = str(path.relative_to(ROOT))
        if rel in SKIP_FILES or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.startswith(SKIP_NAME_PREFIX):
            continue
        if SKIP_PATH_PARTS & set(path.parts):
            continue
        if path.suffix.lstrip('.') not in ('md', 'py', 'sh', 'html', 'csv', 'txt', 'css', 'json'):
            continue
        hits, skip = scan_file(path)
        for lineno, raw, kind in hits:
            results.append({'file': rel, 'line': lineno, 'ref': raw, 'kind': kind})
        for lineno, raw, kind in skip:
            skipped.append({'file': rel, 'line': lineno, 'ref': raw, 'kind': kind})

    naming, hints = ([], []) if links_only else check_naming()

    if as_json:
        print(json.dumps({'dead_links': results, 'skipped': skipped,
                          'naming': naming, 'hints': hints}, ensure_ascii=False, indent=2))
        return

    if not results and not naming and not hints:
        print('✅ 未发现失效引用，命名规范也全绿')
        return

    if results:
        print(f'⚠️  发现 {len(results)} 处失效引用：\n')
        by_file = {}
        for r in results:
            by_file.setdefault(r['file'], []).append(r)
        for f, items in sorted(by_file.items()):
            print(f'  {f}')
            for it in items[:8]:
                print(f'      L{it["line"]}  {it["ref"]}   [{it["kind"]}]')
            if len(items) > 8:
                print(f'      … 另有 {len(items) - 8} 处')
        print(f'\n涉及 {len(by_file)} 个文件。')
    else:
        print('✅ 未发现失效引用')

    if skipped and show_skipped:
        print(f'\n（已豁免 {len(skipped)} 处留痕引用，加 --show-skipped 才显示）')
        for s in skipped:
            print(f'      {s["file"]}:L{s["line"]}  {s["ref"]}')
    elif skipped:
        print(f'（另有 {len(skipped)} 处历史留痕引用已豁免，不计入上面）')

    if naming:
        print(f'\n📐 命名规范：{len(naming)} 处待改进')
        for n in naming[:20]:
            print(f'      [{n["kind"]}] {n["path"]} —— {n["hint"]}')
        if len(naming) > 20:
            print(f'      … 另有 {len(naming) - 20} 处')
    else:
        print('📐 命名规范：✅ 无硬伤')

    if hints:
        print(f'ℹ️  可选优化 {len(hints)} 处（规范允许，可不改）')
        for h in hints[:10]:
            print(f'      {h["path"]} —— {h["hint"]}')


if __name__ == '__main__':
    main()
