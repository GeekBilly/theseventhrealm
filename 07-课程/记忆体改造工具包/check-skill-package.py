#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能包上架前自检（WorkBuddy 开放平台规则）
=================================================

为什么需要它：官方 `skill-creator/scripts/quick_validate.py` 只查 4 项
（SKILL.md 存在 / frontmatter 可解析 / name 为 hyphen-case / description 非空且无尖括号），
**不检查**开放平台实际要求的以下规则，踩过的坑都记在这儿：

  坑1 · 缺 5 个展示字段（2026-11-08）→ version / display_name / display_name_en /
         description_zh / description_en
  坑2 · 目录层级超限（2026-11-08）→ Skill 包只支持两级目录
         （根目录 / 二级目录 / 文件），即 zip 内路径最多 3 段；
         `assets/templates/x.md` 是三级，会被拒。
  坑3 · 展示名不能含空格与特殊字符（2026-11-08）→ display_name 不得有空白字符与
         ASCII 标点（中文全角括号可以）；display_name_en 只允许字母数字与连字符。

用法：
    python3 check-skill-package.py <zip 或 技能目录> [...]

退出码：0 = 全部通过；1 = 有 ERROR；2 = 用法错误。
"""

import re
import sys
import zipfile
from pathlib import Path

# 平台要求的字段（frontmatter 顶层 key）
REQUIRED_KEYS = [
    "name", "display_name", "display_name_en",
    "description", "description_zh", "description_en",
    "version", "agent_created",
]
MAX_PATH_SEGMENTS = 3          # 根目录 / 二级目录 / 文件
MAX_DESC_LEN = 1024


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).split("\n"):
        km = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if km:
            fm[km.group(1)] = km.group(2).strip()
    return fm


def check_skill_md(name, text, errors, warns):
    fm = parse_frontmatter(text)
    if fm is None:
        errors.append(f"{name}: 没有 YAML frontmatter")
        return
    for k in REQUIRED_KEYS:
        if not fm.get(k):
            errors.append(f"{name}: 缺少字段 {k}")
    nm = fm.get("name", "")
    if nm and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", nm):
        errors.append(f"{name}: name '{nm}' 不是 hyphen-case")
    if nm and nm != name:
        warns.append(f"{name}: name 与目录名不一致（目录 {name} / name {nm}）")
    d = fm.get("description", "")
    if "<" in d or ">" in d:
        errors.append(f"{name}: description 含尖括号（平台校验器会拒）")
    if len(d) > MAX_DESC_LEN:
        warns.append(f"{name}: description 过长（{len(d)} 字符）")
    dn = fm.get("display_name", "")
    if dn:
        if re.search(r"\s", dn):
            errors.append(f"{name}: display_name 含空格或空白字符（平台会拒）→ 「{dn}」")
        if re.search(r"""[!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]""", dn):
            errors.append(f"{name}: display_name 含 ASCII 特殊字符（平台会拒）→ 「{dn}」")
    dne = fm.get("display_name_en", "")
    if dne and not re.fullmatch(r"[A-Za-z0-9\-]+", dne):
        warns.append(f"{name}: display_name_en 含空格或特殊字符（实测可过审，"
                     f"但下次改版建议改成无空格）→ 「{dne}」")
    if fm.get("agent_created") != "true":
        warns.append(f"{name}: agent_created 不是 true（skill_manage 将无法管理它）")
    # YAML 隐患：值里出现 ": " 会被当成键值分隔
    for k, v in fm.items():
        if re.search(r":\s", v) and k != "description":
            warns.append(f"{name}: 字段 {k} 的值里含英文冒号+空格，YAML 可能解析异常")


def check_zip(zpath, errors, warns):
    with zipfile.ZipFile(zpath) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        for n in names:
            segs = n.split("/")
            if len(segs) > MAX_PATH_SEGMENTS:
                errors.append(
                    f"{zpath.name}: 目录层级超限（{len(segs)} 段）→ {n}"
                    f"　【Skill 包只支持两级目录：根目录/二级目录/文件】")
        skill_files = [n for n in names if n.endswith("SKILL.md")]
        if not skill_files:
            errors.append(f"{zpath.name}: 包内没有 SKILL.md")
            return
        for sf in skill_files:
            root = sf.split("/")[0]
            check_skill_md(root, zf.read(sf).decode("utf-8"), errors, warns)
        # python 脚本语法检查
        for n in names:
            if n.endswith(".py"):
                try:
                    compile(zf.read(n).decode("utf-8"), n, "exec")
                except SyntaxError as e:
                    errors.append(f"{zpath.name}: {n} 语法错误 → {e}")


def check_dir(dpath, errors, warns):
    skill_md = dpath / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"{dpath.name}: 缺少 SKILL.md")
        return
    check_skill_md(dpath.name, skill_md.read_text(encoding="utf-8"), errors, warns)
    for p in dpath.rglob("*"):
        if p.is_file():
            segs = len(p.relative_to(dpath).parts)
            if segs > 2:
                errors.append(f"{dpath.name}: 目录层级超限 → {p.relative_to(dpath)}")
            if p.suffix == ".py":
                try:
                    compile(p.read_text(encoding="utf-8"), str(p), "exec")
                except SyntaxError as e:
                    errors.append(f"{dpath.name}: {p.name} 语法错误 → {e}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 2
    errors, warns = [], []
    for a in args:
        p = Path(a)
        if p.is_dir():
            check_dir(p, errors, warns)
        elif p.is_file() and p.suffix == ".zip":
            check_zip(p, errors, warns)
        else:
            errors.append(f"{a}: 不是目录也不是 zip")
    for w in warns:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"🔴 {e}")
    if errors:
        print(f"\n❌ {len(errors)} 个错误，{len(warns)} 个提醒 —— 不要上传")
        return 1
    print(f"✅ 全部通过（{len(warns)} 个提醒）—— 可以上传")
    return 0


if __name__ == "__main__":
    sys.exit(main())
