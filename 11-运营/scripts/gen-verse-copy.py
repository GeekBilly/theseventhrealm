# -*- coding: utf-8 -*-
"""第七境 · 每日一句金句 · 小红书文案生成器（幂等）

读 04-市场/03-推广获客/金句日更-202611/金句库-30条.csv，
为每条生成 D01–D30 文案 md，格式继承百家姓 v2 的验证结论：
  ① 开头共鸣问句钩子（非陈述句）
  ② 单一 CTA（评论区互动），不用私信引流话术
  ③ 写明"长按保存，无水印"
  ④ 话题 ≤10（平台硬上限）
  ⑤ 中文引号全角铁律：生成物中不出现半角 "

用法：
  python3 gen-verse-copy.py            # dry-run
  python3 gen-verse-copy.py --apply     # 真正写入
"""
import csv
import pathlib
import re
import sys

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
SRC = ROOT / '04-市场/03-推广获客/金句日更-202611/金句库-30条.csv'
OUT = ROOT / '04-市场/03-推广获客/金句日更-202611'

# 实测高流量基底话题（xhs-topics.json，2026-10-22 抓自平台下拉）
BASE_TOPICS = ['#传统文化', '#国风', '#书法', '#东方美学', '#国学智慧', '#汉字']
EXTRA_TOPICS = ['#金句', '#诗词', '#读书', '#国学']


def full_quote(s: str) -> str:
    """半角直引号 → 中文全角弯引号，顺序配对，遵守引号铁律。"""
    out, open_q = [], True
    for ch in s:
        if ch == '"':
            out.append('\u201c' if open_q else '\u201d')
            open_q = not open_q
        else:
            out.append(ch)
    return ''.join(out)


def title(row):
    # 含"壁纸"搜索词 + 关键词区分（朝代重复太多不能用）+ 不剧透 + 有动作
    return f'金句壁纸｜{row["关键词"]}，长按保存'


def body(row):
    q = full_quote(row['原句'])
    src = f'{row["朝代"]}·{row["作者"]}　《{row["出处"]}》'
    hk = full_quote(row['共鸣问句'])
    lines = [
        '一句话，今天读还是会被击中：',
        '',
        f'「{q}」',
        '',
        f'—— {src}',
        '',
        hk,
        '',
        '一句一图，做了 30 张系列壁纸。',
        '长按保存，无水印。',
        '',
        '哪一句最戳你？评论区告诉我。',
        '想看哪句没收录的，也评论区报一句。',
    ]
    return '\n'.join(lines)


def topics(row):
    return ' '.join((BASE_TOPICS + EXTRA_TOPICS)[:10])


def note(i, row):
    return f'''# D{i:02d} · {row['关键词']}

**标题**：{title(row)}

**配图**：金句线手机竖版（1179×2556 / 1080×2400），竖排金句＋出处落款。
　　　　文件名见同目录 `配图对照表.csv`。

---

**正文**（直接粘贴）

```
{body(row)}
```

**话题**：{topics(row)}

---

**溯源**：{row['溯源状态']}｜原文见 `01-内容/典籍库/原文/{row['源文件']}`
**备注**：原句、出处均据典籍库已校对原文；带异文/真伪讨论的已按本站口径在出处栏标明。
'''


def main():
    apply = '--apply' in sys.argv
    rows = list(csv.DictReader(SRC.open(encoding='utf-8')))
    assert len(rows) == 30, f'金句应为 30 条，实为 {len(rows)}'
    seen = set()
    for i, r in enumerate(rows, 1):
        t = title(r)
        assert len(t) <= 22, f'D{i:02d} 标题超长 {len(t)}: {t}'
        assert len(topics(r).split()) <= 10, f'D{i:02d} 话题超 10'
        assert '"' not in body(r), f'D{i:02d} 正文含半角引号'
        assert t not in seen, f'标题撞车: {t}'
        seen.add(t)
    if not apply:
        print(f'[dry-run] {len(rows)} 篇，标题≤22/话题≤10/全角引号/不撞车 校验通过')
        for i, r in enumerate(rows[:6], 1):
            print(f'  D{i:02d} {title(r)}  ({len(title(r))}字)')
        print('  ...')
        print('加 --apply 写入')
        return
    for i, r in enumerate(rows, 1):
        (OUT / f'D{i:02d}-{r["关键词"]}.md').write_text(note(i, r), encoding='utf-8')
    print(f'[apply] 已写入 {len(rows)} 篇文案到 {OUT}')


if __name__ == '__main__':
    main()
