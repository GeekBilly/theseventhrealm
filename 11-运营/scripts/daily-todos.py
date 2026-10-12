#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日待办优先级 —— 只读本地待办池，零联网零积分。

为什么要脚本算而不是每天让模型编：
  优先级如果只是"今早灵光一现"，那它每天会漂，且不可复现。
  这里把排序规则写死（逾期 > 今天到期 > P0 > P1 > P2，阻塞沉底），
  模型只负责在叠加当日信号（爬虫被拦 / 证书告急 / 积分收紧）时插队。

用法：
  daily-todos.py            # 人读格式，Top 5
  daily-todos.py --top 8    # 改条数
  daily-todos.py --json     # 给 build-morning-board.py 用
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POOL = os.path.join(ROOT, "11-运营", "data", "每日待办池.md")

PRIO = {"P0": 0, "P1": 1, "P2": 2}
DONE = {"完成", "done"}
BLOCKED = {"阻塞", "blocked"}


def load_pool():
    """从 markdown 抓 ``` 代码块里的管道分隔行。表头行自动跳过。"""
    if not os.path.exists(POOL):
        return [], "待办池不存在：" + POOL
    items = []
    for line in open(POOL, encoding="utf-8"):
        line = line.strip()
        if line.startswith("#") or line.startswith("- [") or line.startswith(">"):
            continue
        parts = [x.strip() for x in line.split("|")] if "|" in line else None
        if not parts or len(parts) != 7:
            continue
        tid, prio, title, due, status, dep, src = parts
        if not re.match(r"^[TP]?-?\d+", tid):      # 跳过「id | 优先级 | …」表头
            continue
        items.append({
            "id": tid, "prio": prio.upper(), "title": title, "due": due,
            "status": status, "dep": dep, "src": src,
        })
    return items, None


def due_days(due):
    """剩余天数。'-' 或解析失败返回 None（＝无截止，不催）。"""
    try:
        return (datetime.strptime(due, "%Y-%m-%d").date() - date.today()).days
    except Exception:
        return None


def rank(items):
    """
    排序键，越小越先做：
      0 段＝已完成（其实已被过滤）…不，这里直接丢掉
      1 段＝逾期（days < 0，越久越前）
      2 段＝今天/明天到期
      3 段＝阻塞（沉到最后，等外部解锁，催也没用）
      其余按 P0>P1>P2
    """
    live = [x for x in items if x["status"] not in DONE]
    for x in live:
        d = due_days(x["due"])
        x["_days"] = d
        if x["status"] in BLOCKED:
            x["_tier"], x["_k"] = 9, 0
        elif d is not None and d < 0:
            x["_tier"], x["_k"] = 0, d          # 逾期越久越靠前
        elif d is not None and d <= 1:
            x["_tier"], x["_k"] = 1, d
        else:
            x["_tier"], x["_k"] = 2, d if d is not None else 9999
    live.sort(key=lambda x: (x["_tier"], PRIO.get(x["prio"], 3), x["_k"]))
    return live


def flag(x):
    if x["status"] in BLOCKED:
        return "⏸ 阻塞"
    if x["_days"] is None:
        return ""
    if x["_days"] < 0:
        return f"🔴 逾期 {abs(x['_days'])} 天"
    if x["_days"] == 0:
        return "🔴 今天到期"
    if x["_days"] == 1:
        return "⚠️ 明天到期"
    return f"余 {x['_days']} 天"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    items, err = load_pool()
    if err:
        print("本次未能自动获取：" + err, file=sys.stderr)
        print(json.dumps({"ok": False, "error": err}, ensure_ascii=False))
        return 1

    ordered = rank(items)
    top = ordered[:a.top]

    if a.json:
        print(json.dumps({
            "ok": True,
            "date": str(date.today()),
            "total_open": len(ordered),
            "top": [{
                "id": x["id"], "prio": x["prio"], "title": x["title"],
                "due": x["due"], "status": x["status"], "flag": flag(x),
            } for x in top],
        }, ensure_ascii=False))
        return 0

    if not ordered:
        print("待办池里没有未完成的事项。")
        return 0

    print(f"今日优先级 · {date.today()}（未完成共 {len(ordered)} 项，以下 Top {len(top)}）")
    print("─" * 62)
    for i, x in enumerate(top, 1):
        tail = "　".join(t for t in [flag(x), x["status"]] if t)
        print(f"{i}. [{x['prio']}] {x['title']}")
        if tail:
            print(f"   {tail}")
        if x["dep"] and x["dep"] != "-":
            print(f"   依赖：{x['dep']}")
    rest = len(ordered) - len(top)
    if rest > 0:
        print("─" * 62)
        print(f"（其余 {rest} 项见 11-运营/data/每日待办池.md）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
