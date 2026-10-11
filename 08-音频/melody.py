import subprocess, numpy as np, json
from scipy.signal import medfilt

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
SRC = BASE + "第七境主题背景音乐-原始.m4a"
sr = 48000
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

p = subprocess.run([FF, "-i", SRC, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
x = np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)
x = x[: int(127.2 * sr)]

FRAME, HOP = 4096, 512
dt = HOP / sr
times, freqs, proms, rmss = [], [], [], []
for i in range(0, len(x) - FRAME, HOP):
    s = x[i:i+FRAME]
    w = np.hanning(FRAME)
    X = np.abs(np.fft.rfft(s * w))
    f = np.fft.rfftfreq(FRAME, 1/sr)
    bd = (f >= 400) & (f <= 3000)
    fb, Xb = f[bd], X[bd]
    k = int(np.argmax(Xb))
    a, b, c = np.log(Xb[k-1]+1e-20), np.log(Xb[k]+1e-20), np.log(Xb[k+1]+1e-20)
    d = a - 2*b + c
    f0 = fb[k] + (0.5*(a-c)/d if d else 0) * (fb[1]-fb[0])
    times.append(i/sr + FRAME/2/sr)
    freqs.append(f0)
    proms.append(Xb[k] / (np.median(Xb) + 1e-20))
    rmss.append(np.sqrt(np.mean(s**2)))

times = np.array(times); freqs = np.array(freqs)
proms = np.array(proms); rmss = np.array(rmss)

ok = (proms > 40) & (rmss > 0.002)
midi = np.full(len(freqs), np.nan)
midi[ok] = 69 + 12*np.log2(freqs[ok]/440.0)
m = midi.copy()
v = ~np.isnan(m)
idx = np.where(v)[0]
if len(idx):
    sm = medfilt(m[idx], 5)
    m[idx] = sm

segs, cur = [], None
for i in range(len(m)):
    v0 = m[i]
    if np.isnan(v0):
        if cur and (i - cur["end_i"]) * dt > 0.12:
            segs.append(cur); cur = None
        continue
    if cur is None:
        cur = {"start_i": i, "end_i": i, "vals": [v0]}
    elif abs(v0 - np.median(cur["vals"])) <= 0.5:
        cur["end_i"] = i; cur["vals"].append(v0)
    else:
        segs.append(cur); cur = {"start_i": i, "end_i": i, "vals": [v0]}
if cur: segs.append(cur)

notes = []
for s in segs:
    dur = (s["end_i"] - s["start_i"] + 1) * dt
    if dur < 0.11: continue
    mv = float(np.median(s["vals"]))
    notes.append({"t": round(times[s["start_i"]], 2), "dur": round(dur, 2),
                  "midi": mv, "freq": round(440*2**((mv-69)/12), 1)})

merged = []
for n in notes:
    if merged and abs(n["midi"] - merged[-1]["midi"]) < 0.5 and n["t"] - (merged[-1]["t"]+merged[-1]["dur"]) < 0.12:
        merged[-1]["dur"] = round(n["t"] + n["dur"] - merged[-1]["t"], 2)
    else:
        merged.append(n)
notes = merged

print(f"识别到 {len(notes)} 个音符\n")
print(f"{'#':>3} {'起始':>7} {'时长':>6} {'音名':>5} {'频率':>8} {'音分':>6}")
print("-" * 46)
for i, n in enumerate(notes, 1):
    q = int(round(n["midi"]))
    cents = (n["midi"] - q) * 100
    nm = NAMES[q % 12] + str(q//12 - 1)
    n["name"] = nm; n["cents"] = round(cents, 1)
    print(f"{i:>3} {n['t']:>6.2f}s {n['dur']:>5.2f}s {nm:>5} {n['freq']:>7.1f}Hz {cents:+6.1f}")

print(f"\n=== 音阶使用统计 ===")
from collections import Counter
cnt = Counter(n["name"][:-1] if n["name"][-1].isdigit() else n["name"] for n in notes)
for k, v in sorted(cnt.items(), key=lambda a: -a[1]):
    print(f"  {k:>3}: {v:>3} 次  {'#'*min(50,v)}")

allm = np.array([n["midi"] for n in notes])
print(f"\n音域: {NAMES[int(round(allm.min()))%12]}{int(round(allm.min()))//12-1} "
      f"~ {NAMES[int(round(allm.max()))%12]}{int(round(allm.max()))//12-1}  "
      f"(MIDI {allm.min():.1f}-{allm.max():.1f}, 跨度 {allm.max()-allm.min():.1f} 半音)")
dev = np.array([abs(n["cents"]) for n in notes])
print(f"音准偏差: 平均 {dev.mean():.1f} 音分, 最大 {dev.max():.1f} 音分")

json.dump(notes, open(BASE + "melody.json", "w"), ensure_ascii=False, indent=1)
print("\n已保存 melody.json")
