#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型性价比闸门 · 每日晨检第一步

判定当前会话所用模型的「积分消耗倍数」，超过阈值即 STOP（不跑晨检，去找用户换模型）。

零联网、零积分、只读本机文件。

数据源：
  ① 当前会话模型：从 ~/.workbuddy/projects/<工作区slug>/*.jsonl 里取最近一条 "model":"xxx"
  ② 积分倍率表  ：~/.workbuddy/cache/acc-product-config-v3.json → models[].credits（如 "x0.08"）

判定：
  倍率 ≤ 阈值(默认 0.30)         → PASS，退出码 0，继续晨检
  倍率 > 阈值                     → STOP，退出码 3，简报只报「需要换模型」，不跑晨检
  模型/倍率表取不到                → SKIP（降级），退出码 0，简报写「本次未取到」，不阻塞晨检

用法：
  python3 11-运营/scripts/model-cost-gate.py                # 默认阈值 0.30
  python3 11-运营/scripts/model-cost-gate.py --max 0.20      # 临时收紧
  python3 11-运营/scripts/model-cost-gate.py --json          # 机器可读输出
"""
import argparse
import glob
import json
import os
import re
import sys
import time

WORKSPACE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
PROJECTS = os.path.expanduser("~/.workbuddy/projects")
CONFIG_GLOB = os.path.expanduser("~/.workbuddy/cache/acc-product-config-v3*.json")
THRESHOLD_FILE = os.path.join(WORKSPACE, "11-运营/data/model-cost-threshold.json")

DEFAULT_MAX = 0.30
# 晨检是「脚本化例行任务」，不需要旗舰推理能力；这些模型足以胜任且倍数低
RECOMMENDED = [
    ("space-bunny", "Space-Bunny", 0.08),
    ("glm-5.3-flash", "GLM-5.3-Flash", 0.08),
    ("minimax-m3.1-flash", "MiniMax-M3.1-Flash", 0.08),
    ("deepseek-v4.1-flash", "DeepSeek-V4.1-Flash", 0.11),
    ("deepseek-v4-flash", "DeepSeek-V4-Flash", 0.17),
    ("fast-model", "快速", 0.21),
]


def load_threshold(cli_max):
    if cli_max is not None:
        return float(cli_max), "命令行指定"
    try:
        with open(THRESHOLD_FILE) as f:
            d = json.load(f)
        return float(d.get("max_multiplier", DEFAULT_MAX)), d.get("source", "配置文件")
    except Exception:
        return DEFAULT_MAX, "脚本默认值"


def find_current_model():
    """取最近一次会话里实际使用的模型 id。返回 (model_id, session_file) 或 (None, None)。"""
    slug = WORKSPACE.strip("/").replace("/", "-")
    files = sorted(glob.glob(os.path.join(PROJECTS, slug, "*.jsonl")), key=os.path.getmtime, reverse=True)
    if not files:
        # 退化：目录名可能不是简单 slug 化，用通配
        files = sorted(glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")), key=os.path.getmtime, reverse=True)
    pat = re.compile(r'"model"\s*:\s*"([^"]+)"')
    for f in files[:5]:  # 最近 5 个会话里找第一个能取到 model 的
        try:
            with open(f, errors="ignore") as fh:
                tail = fh.read()[-400000:]  # 只看尾部，避免大文件
        except Exception:
            continue
        found = pat.findall(tail)
        if found:
            return found[-1], f
    return None, (files[0] if files else None)


def load_multipliers():
    """返回 {model_id: (name, multiplier)}"""
    out = {}
    cands = sorted(glob.glob(CONFIG_GLOB), key=os.path.getmtime, reverse=True)
    for p in cands:
        try:
            with open(p) as f:
                d = json.load(f)
        except Exception:
            continue
        models = d.get("models") or []
        if not models:
            continue
        for m in models:
            mid = m.get("id")
            if not mid:
                continue
            raw = str(m.get("credits", "") or "")
            mm = re.search(r"x\s*([0-9.]+)", raw)
            mult = float(mm.group(1)) if mm else None
            out[mid] = (m.get("name") or mid, mult, raw)
        if out:
            return out, p
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", dest="max", type=float, default=None, help="倍率阈值")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    max_mult, thr_src = load_threshold(args.max)
    model, session_file = find_current_model()
    table, cfg_path = load_multipliers()

    info = table.get(model) if model else None
    mult = info[1] if info else None
    name = info[0] if info else (model or "未知")

    if model is None:
        verdict, note = "SKIP", "本次未取到当前会话模型，不阻塞晨检"
    elif mult is None:
        verdict, note = "SKIP", f"倍率表里没有 {model}（可能是自定义模型），不阻塞晨检"
    elif mult <= max_mult:
        verdict = "PASS"
        note = f"{name} x{mult:.2f} ≤ 阈值 x{max_mult:.2f}，性价比合格，继续晨检"
    else:
        verdict = "STOP"
        note = f"{name} x{mult:.2f} > 阈值 x{max_mult:.2f}，性价比不合格 ⇒ 停止晨检，去找用户换模型"

    alts = []
    if verdict == "STOP":
        for mid, mname, m in RECOMMENDED:
            if m <= max_mult and mid != model:
                alts.append({"id": mid, "name": mname, "multiplier": m})
        alts.sort(key=lambda x: x["multiplier"])

    result = {
        "verdict": verdict,
        "note": note,
        "model": model,
        "model_name": name,
        "multiplier": mult,
        "max_multiplier": max_mult,
        "threshold_source": thr_src,
        "session_file": session_file,
        "config_file": cfg_path,
        "alternatives": alts,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("—— 模型性价比闸门 · " + result["checked_at"] + " ——")
        print(f"当前模型：{name}（{model}）")
        print(f"积分倍率：{('x%.2f' % mult) if mult is not None else '未取到'}　阈值：x{max_mult:.2f}（来源：{thr_src}）")
        print(f"判定　　：{verdict} —— {note}")
        if alts:
            print("建议切换（低成本、够跑晨检）：")
            for a in alts[:4]:
                print(f"  · {a['name']}（{a['id']}）x{a['multiplier']:.2f}")

    sys.exit(3 if verdict == "STOP" else 0)


if __name__ == "__main__":
    main()
