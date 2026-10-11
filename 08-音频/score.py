import json, numpy as np, struct

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
notes = json.load(open(BASE + "melody.json", encoding="utf-8"))
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

dev = np.array([n["cents"] for n in notes])
print(f"=== 音准分析 ===")
print(f"  有符号平均偏差: {dev.mean():+.1f} 音分  (正=整体偏高)")
print(f"  标准差: {dev.std():.1f} 音分")
print(f"  偏高 (>15音分) 的音符: {(dev > 15).sum()} / {len(dev)}")
print(f"  偏低 (<-15音分) 的音符: {(dev < -15).sum()} / {len(dev)}")

offset = dev.mean()
print(f"\n  校正策略: 整体下移 {offset:.1f} 音分后重新量化")

for n in notes:
    n["midi_c"] = n["midi"] - offset / 100.0

clean = []
for n in notes:
    if clean and n["dur"] < 0.16 and abs(n["midi_c"] - clean[-1]["midi_c"]) < 2.0:
        clean[-1]["dur"] = round(n["t"] + n["dur"] - clean[-1]["t"], 2)
        continue
    clean.append(dict(n))
print(f"  合并滑音碎片后: {len(clean)} 个音符")

for n in clean:
    q = int(round(n["midi_c"]))
    n["q"] = q
    n["name"] = NAMES[q % 12] + str(q // 12 - 1)
    n["cents2"] = round((n["midi_c"] - q) * 100, 1)

TONIC_PC = 10
DEG = {10: "1", 0: "2", 2: "3", 3: "4", 5: "5", 7: "6", 9: "7"}
def jianpu(n):
    q = n["q"]
    d = DEG.get(q % 12)
    if d is None:
        near = min(DEG.keys(), key=lambda p: min(abs(q % 12 - p), 12 - abs(q % 12 - p)))
        d = DEG[near] + "?"
    oct_ = q // 12 - 1
    if oct_ < 5: return d + "̣"
    if oct_ > 5: return d + "˙"
    return d

BPM = 72
beat = 60.0 / BPM
grid = beat / 2

def quant_dur(d):
    u = max(1, int(round(d / grid)))
    return u, u * grid

lines, cur, i = [], [], 0
while i < len(clean):
    n = clean[i]
    u, qd = quant_dur(n["dur"])
    cur.append((jianpu(n), u))
    if len(cur) == 8:
        lines.append(cur); cur = []
    i += 1
if cur: lines.append(cur)

print(f"\n=== 简谱（1=B♭ 降B大调 · {BPM}BPM · 4/4）===")
for li, ln in enumerate(lines, 1):
    print(f"  {li:>2}| " + " ".join(f"{d:<3}" for d, u in ln) + " |")

print(f"\n=== 前 32 个音符对照 ===")
print(f"{'#':>3} {'起始':>7} {'时长':>6} {'量化':>6} {'音名':>5} {'简谱':>5} {'音分':>7}")
for i, n in enumerate(clean[:32], 1):
    u, qd = quant_dur(n["dur"])
    print(f"{i:>3} {n['t']:>6.2f}s {n['dur']:>5.2f}s {qd:>5.2f}s {n['name']:>5} {jianpu(n):>5} {n['cents2']:+6.1f}")

def write_midi(path, ns, bpm=BPM):
    tpq = 480
    ev = []
    ev.append(struct.pack(">4sI", b"MThd", 6))
    ev.append(struct.pack(">HHH", 0, 1, tpq))
    tr = bytearray()
    tr += b"\x00\xff\x51\x03" + struct.pack(">I", int(60000000/bpm))[1:]
    tr += b"\x00\xff\x58\x04\x04\x02\x18\x08"
    prev = 0.0
    for n in ns:
        u, qd = quant_dur(n["dur"])
        st = round(n["t"] / (60.0/bpm) * tpq)
        du = round(qd / (60.0/bpm) * tpq)
        d = st - int(prev)
        d = max(0, d)
        tr += vlq(d) + bytes([0x90, n["q"], 80])
        tr += vlq(du) + bytes([0x80, n["q"], 64])
        prev = st + du
    tr += b"\x00\xff\x2f\x00"
    ev.append(struct.pack(">4sI", b"MTrk", len(tr)) + bytes(tr))
    open(path, "wb").write(b"".join(ev))

def vlq(v):
    out = bytearray([v & 0x7F]); v >>= 7
    while v:
        out.insert(0, (v & 0x7F) | 0x80); v >>= 7
    return bytes(out)

write_midi(BASE + "第七境主题旋律.mid", clean)
write_midi(BASE + "第七境主题旋律-未校正音准.mid", [
    dict(n, q=int(round(n["midi"])), ) for n in clean])
print("\nMIDI 已生成")

json.dump(clean, open(BASE + "melody_quantized.json", "w"), ensure_ascii=False, indent=1)

from collections import Counter
c = Counter(n["name"][:-1] for n in clean)
print("\n=== 量化后音阶统计 ===")
for k, v in sorted(c.items(), key=lambda a: -a[1]):
    mark = " <- 降B大调调内" if k in ["A#", "C", "D", "D#", "F", "G", "A"] else ""
    print(f"  {k:>3}: {v:>3} 次{mark}")
