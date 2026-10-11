#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 gen-theme-C.py 的旋律导出成【简谱】（文本 + 图片 + MIDI），供用户自己哼唱校验。

记谱法：
    1 = C（宫 = C）→ A 羽调式记作 6 1 2 3 5（羽调式，无 4、7）
    速度 ♩ = 60（一拍一秒）→ 音符时值直接按秒数换算成拍数
    低八度加下点（6̣），高八度加上点（1̇）

用法  python3 08-音频/make-jianpu.py
输出  08-音频/候选曲/简谱-C版.txt / 简谱-C版.png / 简谱-C版.mid
"""
import pathlib, struct

# ── 与 gen-theme-C.py 保持一致的旋律 ─────────────
MEL = [
    (0.0,  57, 2.8, .50), (2.0,  60, 2.6, .50), (4.0,  62, 2.6, .50),
    (6.0,  64, 2.8, .52), (8.0,  62, 2.6, .50), (10.0, 60, 2.6, .48),
    (12.0, 62, 2.8, .50), (14.0, 64, 3.0, .52),
    (16.0, 67, 2.4, .55), (18.0, 69, 2.6, .57), (20.0, 67, 2.4, .55),
    (22.0, 64, 2.4, .53), (24.0, 67, 2.6, .55), (26.0, 69, 2.6, .57),
    (28.0, 72, 2.8, .59), (30.0, 69, 2.4, .57), (32.0, 67, 2.4, .55),
    (34.0, 69, 2.6, .57), (36.0, 72, 2.8, .60), (38.0, 74, 3.0, .62),
    (40.0, 72, 2.6, .60),
    (42.0, 76, 2.8, .68), (44.0, 74, 2.6, .66), (46.0, 72, 2.6, .64),
    (48.0, 74, 2.8, .66), (50.0, 76, 3.0, .70), (52.0, 74, 2.6, .66),
    (54.0, 72, 2.6, .64), (56.0, 69, 2.8, .62), (58.0, 72, 3.0, .64),
    (60.0, 74, 3.2, .66),
    (62.5, 69, 3.2, .60), (65.0, 67, 3.4, .56), (67.5, 64, 3.6, .52),
    (70.5, 62, 3.8, .48), (74.0, 60, 3.8, .46), (77.5, 57, 4.0, .44),
    (81.0, 57, 8.0, .40),
]
SECTIONS = [(0, "起 · 从最低处缓缓升起"), (16, "承 · 级进上行，一句一句"),
            (42, "转 · 升到高处，开阔"), (62.5, "合 · 缓缓落下，长音收尾")]
BPM = 60
OUT = pathlib.Path(__file__).resolve().parent / "候选曲"
OUT.mkdir(parents=True, exist_ok=True)

# 1 = C：C=1 D=2 E=3 G=5 A=6
DEG = {0: "1", 2: "2", 4: "3", 5: "4", 7: "5", 9: "6", 11: "7"}


def jianpu(midi):
    pc = midi % 12
    d = DEG.get(pc, "?")
    octv = midi // 12 - 1          # C4 = 第 4 八度
    if octv < 4:
        return d + "\u0323"        # 下点 = 低八度
    if octv > 4:
        return d + "\u0307"        # 上点 = 高八度
    return d


def beats(dur):
    return max(1, int(round(dur / (60.0 / BPM))))


def line_text(notes, max_units=8):
    """按拍数折行，每行约 max_units 拍"""
    out, cur, units = [], [], 0
    for midi, u in notes:
        if units + u > max_units and cur:
            out.append(cur); cur, units = [], 0
        cur.append((jianpu(midi), u)); units += u
    if cur:
        out.append(cur)
    return out


def txt():
    L = []
    L.append("第七境 · 水墨主题 C 版 · 简谱")
    L.append("=" * 46)
    L.append("")
    L.append("  1 = C    4/4    ♩ = 60（一拍一秒）")
    L.append("  羽调式：只用 6 1 2 3 5，没有 4 和 7")
    L.append("  记法：6̣ = 低八度 · 6 = 中音 · 1̇ = 高八度")
    L.append("  「—」＝延音一拍（把前一个音再拖一秒）")
    L.append("")
    sec_idx = {}
    for st, name in SECTIONS:
        sec_idx[round(st, 1)] = name
    # 分组
    groups, cur, curname = [], [], SECTIONS[0][1]
    bounds = [s for s, _ in SECTIONS] + [1e9]
    for i, (t0, midi, dur, vel) in enumerate(MEL):
        for k in range(len(SECTIONS)):
            if bounds[k] <= t0 < bounds[k + 1]:
                nm = SECTIONS[k][1]
                break
        else:
            nm = ""
        if nm != curname and cur:
            groups.append((curname, cur)); cur, curname = [], nm
        cur.append((midi, beats(dur)))
    if cur:
        groups.append((curname, cur))

    for name, notes in groups:
        L.append(f"【{name}】")
        for ln in line_text(notes, 8):
            parts = []
            for d, u in ln:
                parts.append(d + " " + ("— " * (u - 1)).strip() if u > 1 else d)
            L.append("   " + "  |  ".join(parts))
        L.append("")
    L.append("提示：哼的时候气息要连，别一个音一个音断开；")
    L.append("      句尾那几个长音（尤其最后 8 拍）尽量拖住。")
    return "\n".join(L)


def png(text, path):
    from PIL import Image, ImageDraw, ImageFont
    try:
        f  = ImageFont.truetype("/System/Library/Fonts/Supplemental/Songti.ttc", 26, index=6)
        fb = ImageFont.truetype("/System/Library/Fonts/Supplemental/Songti.ttc", 30, index=3)
    except Exception:
        f = fb = ImageFont.load_default()
    lines = text.split("\n")
    W, LH = 1180, 44
    img = Image.new("RGB", (W, LH * len(lines) + 60), (250, 249, 247))
    d = ImageDraw.Draw(img)
    y = 26
    for ln in lines:
        big = ln.startswith("【") or ln.startswith("第七境")
        d.text((46, y), ln, font=(fb if big else f), fill=((176, 56, 38) if big else (40, 38, 34)))
        y += LH if not big else LH + 8
    img.save(path, "PNG", optimize=True)
    return img.size


def midi_file(path):
    tpq = 480; bpm = BPM
    tr = bytearray()
    def vlq(v):
        b = [v & 0x7F]; v >>= 7
        while v: b.insert(0, (v & 0x7F) | 0x80); v >>= 7
        return bytes(b)
    evs = []
    for t0, midi, dur, vel in MEL:
        tick = int(t0 * bpm / 60 * tpq)
        evs.append((tick, 0x90, midi, int(vel * 100)))
        evs.append((tick + int(dur * bpm / 60 * tpq), 0x80, midi, 0))
    evs.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for tick, st, a, b in evs:
        tr += vlq(tick - last) + bytes([st, a, b]); last = tick
    tr += vlq(0) + b"\xff\x2f\x00"
    with open(path, "wb") as fh:
        fh.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq))
        fh.write(b"MTrk" + struct.pack(">I", len(tr)) + bytes(tr))
    return pathlib.Path(path).stat().st_size


if __name__ == "__main__":
    t = txt()
    (OUT / "简谱-C版.txt").write_text(t, encoding="utf-8")
    print(t)
    print()
    print("  ✓ 简谱-C版.txt")
    print("  ✓ 简谱-C版.png ", png(t, OUT / "简谱-C版.png"))
    print(f"  ✓ 简谱-C版.mid  {midi_file(OUT/'简谱-C版.mid')} bytes")
