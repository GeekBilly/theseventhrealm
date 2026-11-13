#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · Agent 治理裁判（只读）

设计（对应 11-运营/data/agent-授权表.md）：
  - 零 LLM、零积分、零联网、不写任何文件：只解析授权表 + 本地文件 stat。
  - 只输出提案，绝不执行：不修表、不重启任务、不新建调度、不动线上。
  - 失败一次即降级：读不到就写「本次未取到」并退出，不重试、不排障。
  - 递归终止：裁判自己登记在授权表 G-01，受同一份表约束，不能自我提权。

用法：
  python3 11-运营/scripts/agent-governor.py --check
  python3 11-运营/scripts/agent-governor.py --check --json

退出码：
  0 = GOVERN_GATE=PASS（无提案）
  1 = GOVERN_GATE=REVIEW（有提案，只报不修）
  2 = 读表失败（降级，本次未取到）
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime

ROOT_MARK = "README-总原则.md"
TABLE_REL = "11-运营/data/agent-授权表.md"
TODAY = date.today()

VALID_DOMAIN = re.compile(r"L[0-3]|停")
SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._-]{8,}|sk-[A-Za-z0-9]{12,}"
    r"|(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{6,}['\"])"
)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
PLACEHOLDER = {
    "MMDD": TODAY.strftime("%m%d"),
    "YYYY-MM-DD": TODAY.isoformat(),
    "YYYYMMDD": TODAY.strftime("%Y%m%d"),
    "YYYYMM": TODAY.strftime("%Y%m"),
}
STALE_DAYS = 3


def locate_root():
    """从脚本位置向上找空间根，避免依赖调用时的工作目录。"""
    p = os.path.abspath(__file__)
    for _ in range(6):
        p = os.path.dirname(p)
        if os.path.exists(os.path.join(p, ROOT_MARK)):
            return p
    return None


SECTION_START = "## 二、授权表"


def parse_table(path):
    """只解析「## 二、授权表」区块内的 7 列登记行。

    区块外的说明表格（能力域定义、变更记录等）是文档，不是登记行，
    一律忽略，不计入格式异常。
    """
    rows, skipped, inside = [], 0, False
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            line = raw.strip()
            if line.startswith("## "):
                inside = line.startswith(SECTION_START)
                continue
            if not inside or not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != 7:
                skipped += 1
                continue
            if cells[0] in ("id", "") or set(cells[0]) <= set("-: "):
                continue
            if not re.match(r"^[HGALSX]-\d{2}$", cells[0]):
                skipped += 1
                continue
            rows.append({"line": ln, "cells": cells})
    return rows, skipped


NO_LOG = {"-", "不适用", "stdout", "stdout（不落盘）", "本文件变更记录", "11-运营/logs/"}


def stale_limit(rid):
    """心跳阈值按调度频率给；事件驱动/默认未授权的工具不做心跳。"""
    if rid.startswith("X-"):
        return None          # 默认未授权，文件长期不动是正确的
    if rid in ("S-04", "S-20"):
        return None          # 事件驱动：无待推 URL 时本来就不写文件
    if rid in ("A-04", "A-05", "A-06"):
        return 40            # 月度任务
    if rid.startswith("A-02") or rid.startswith("A-03"):
        return 10            # 周任务
    return STALE_DAYS        # 日任务 / 常驻


def resolve_log_path(root, spec):
    """第 7 列第三段可能是目录/带占位符路径/外部临时路径。"""
    spec = spec.strip()
    for k, v in PLACEHOLDER.items():
        spec = spec.replace(k, v)
    if spec in NO_LOG or spec.startswith("/tmp/"):
        return None
    return spec


def onfail_ok(text):
    return any(k in text for k in ("降级", "不重试", "不适用", "不复活", "只提醒", "只出申请单", "STOP", "不再重试", "不代装"))


def check(root, rows, skipped):
    proposals = []
    seen = {}

    def add(kind, rid, detail):
        proposals.append({"kind": kind, "id": rid, "detail": detail})

    if skipped:
        add("格式异常", "-", f"有 {skipped} 行不符合 7 列格式或 id 规范，被跳过（只报不修）")

    for r in rows:
        rid, task, domain, cred, budget, onfail, meta = r["cells"]
        rid = rid.replace("**", "")
        if rid in seen:
            add("id 重复", rid, f"与第 {seen[rid]} 行重复，单一真源不允许重复登记")
        seen[rid] = r["line"]

        if not VALID_DOMAIN.search(domain):
            add("能力域非法", rid, f"能力域列「{domain}」未含 L0-L3 或 停")

        if SECRET_VALUE.search(cred):
            add("疑似凭据明文", rid, "凭据列出现疑似值形态，违反「凭据绝不写进文件」")

        if "⚠️" in cred:
            add("凭据文件待核实", rid, "凭据位置标了 ⚠️，需用户确认迁移到钥匙串（属涉安全改动，需申请单）")

        if rid.startswith("X-"):
            if "L2" not in domain and "L3" not in domain:
                add("受控工具疑似解禁", rid, "X 组能力域必须保持 L2/L3（默认未授权）")
            if "禁止" not in budget and "永不" not in budget:
                add("受控工具疑似解禁", rid, "X 组预算必须保持 禁止/永不")
        if rid == "L-05" and "停" not in domain:
            add("废弃任务疑似复活", rid, "gitsync 已并入晨检，不得复活")

        dm = DATE_RE.search(meta)
        if dm:
            try:
                due = date.fromisoformat(dm.group(1))
                if due < TODAY:
                    add("复核逾期", rid, f"复核到期 {due.isoformat()}，已逾期 {(TODAY - due).days} 天")
            except ValueError:
                add("日期异常", rid, f"到期字段解析失败：{dm.group(1)}")

        if not onfail_ok(onfail):
            add("失败策略缺失", rid, f"第 6 列未明确降级口径：{onfail}")

        p = resolve_log_path(root, meta.split("·")[-1])
        if p and not os.path.exists(os.path.join(root, p)):
            add("日志路径缺失", rid, f"登记路径不存在（仅提示，不创建）：{p}")
        elif p:
            full = os.path.join(root, p)
            limit = stale_limit(rid)
            if limit is not None and os.path.isfile(full):
                age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(full))).days
                if age > limit:
                    add("心跳缺失", rid, f"日志/数据文件 {age} 天未更新（阈值 {limit} 天）：{p}")
    return proposals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只读校验（默认）")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    root = locate_root()
    if not root:
        print("本次未取到：未定位到空间根（README-总原则.md 未找到），按降级口径停止")
        return 2
    table = os.path.join(root, TABLE_REL)
    if not os.path.exists(table):
        print(f"本次未取到：授权表不存在（{TABLE_REL}），按降级口径停止")
        return 2
    try:
        rows, skipped = parse_table(table)
    except Exception as e:
        print(f"本次未取到：读表失败（{type(e).__name__}），按降级口径不重试")
        return 2

    proposals = check(root, rows, skipped)
    gate = "REVIEW" if proposals else "PASS"
    counts = {}
    for p in proposals:
        counts[p["kind"]] = counts.get(p["kind"], 0) + 1

    if args.json:
        print(json.dumps({"gate": gate, "total": len(rows),
                          "proposals": proposals, "counts": counts,
                          "date": TODAY.isoformat()}, ensure_ascii=False, indent=2))
    else:
        print(f"—— Agent 治理裁判 · {TODAY.isoformat()}（只读，零积分，只出提案不执行）——")
        print(f"表：{TABLE_REL}｜登记 {len(rows)} 行｜跳过 {skipped} 行")
        print("────────────────────────────────────────────────────────────────")
        if proposals:
            for i, p in enumerate(proposals, 1):
                print(f"  提案 {i:02d}｜[{p['kind']}] {p['id']}｜{p['detail']}")
        else:
            print("  无提案：格式、能力域、凭据、预算、复核到期、心跳全部在口径内。")
        print("────────────────────────────────────────────────────────────────")
        print(f"GOVERN_GATE={gate} total={len(rows)} proposals={len(proposals)} "
              + " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print("裁判自身登记为 G-01，受同一份表约束：不写表、不提权、不新增调度。")
    return 1 if proposals else 0


if __name__ == "__main__":
    sys.exit(main())
