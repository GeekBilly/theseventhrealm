import subprocess, numpy as np

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
SRC = BASE + "第七境主题背景音乐-原始.m4a"
sr = 48000

p = subprocess.run([FF, "-i", SRC, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
x = np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)
x = x[: int(127.2 * sr)]
print(f"时长 {len(x)/sr:.2f}s")

FRAME, HOP = 4096, 512
FMIN, FMAX = 400, 3000
names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def fft_freq(sig):
    w = np.hanning(len(sig))
    X = np.abs(np.fft.rfft(sig * w))
    f = np.fft.rfftfreq(len(sig), 1 / sr)
    band = (f >= FMIN) & (f <= FMAX)
    fb, Xb = f[band], X[band]
    k = int(np.argmax(Xb))
    if k <= 0 or k >= len(Xb) - 1:
        return 0.0, 0.0
    a, b, c = np.log(Xb[k-1] + 1e-20), np.log(Xb[k] + 1e-20), np.log(Xb[k+1] + 1e-20)
    d = a - 2*b + c
    delta = 0.5 * (a - c) / d if d != 0 else 0.0
    f0 = fb[k] + delta * (fb[1] - fb[0])
    prom = Xb[k] / (np.median(Xb) + 1e-20)
    return f0, prom

rows = []
for i in range(0, len(x) - FRAME, HOP):
    s = x[i:i+FRAME]
    rms = np.sqrt(np.mean(s ** 2))
    f0, prom = fft_freq(s)
    rows.append((i / sr, rms, f0, prom))

print("\n=== 音高稳定性自查（前 40 帧）===")
for t, r, f, pr in rows[:40]:
    print(f"  {t:6.2f}s  RMS {20*np.log10(r+1e-12):6.1f}dB  f0 {f:7.1f}Hz  突出度 {pr:6.1f}")

f0s = np.array([r[2] for r in rows])
prs = np.array([r[3] for r in rows])
rms = np.array([r[1] for r in rows])
print(f"\n=== 分布 ===")
print(f"  突出度中位数 {np.median(prs):.1f} / 90分位 {np.percentile(prs,90):.1f}")
print(f"  RMS dBFS: 中位 {20*np.log10(np.median(rms)+1e-12):.1f}")
valid = f0s[(prs > 8) & (rms > 0.004)]
print(f"  有效音高帧 {len(valid)} / {len(f0s)}")
if len(valid):
    print(f"  音高范围 {np.percentile(valid,2):.0f} - {np.percentile(valid,98):.0f} Hz")
    print(f"  音高中位数 {np.median(valid):.0f} Hz")
    h, edges = np.histogram(valid, bins=24)
    print("\n  === 音高直方图（看用了哪些音）===")
    for i in range(24):
        if h[i] > 0:
            fmid = (edges[i] + edges[i+1]) / 2
            midi = 69 + 12*np.log2(fmid/440)
            nm = names[int(round(midi)) % 12] + str(int(round(midi))//12 - 1)
            print(f"    {edges[i]:6.0f}-{edges[i+1]:6.0f}Hz  {nm:>4s}  {'#'*min(60,int(h[i]/max(h.max(),1)*60))} {h[i]}")
