import subprocess, re, numpy as np

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
OUT = BASE + "第七境主题背景音乐-修复版.wav"
SRC = BASE + "第七境主题背景音乐-原始.m4a"
sr = 44100

def loudness(p):
    r = subprocess.run([FF, "-i", p, "-af", "loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[\s\S]*?\}', r.stdout + r.stderr)
    return eval(m.group(0).replace("true", "True").replace("false", "False").replace("null", "None")) if m else {}

def dec(p):
    r = subprocess.run([FF, "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)

def bands(x, label):
    N = sr * 8
    acc = np.zeros(N // 2 + 1); c = 0
    for i in range(0, len(x) - N, N):
        w = np.hanning(N)
        acc += np.abs(np.fft.rfft(x[i:i+N] * w)) ** 2; c += 1
    acc /= max(c, 1)
    f = np.fft.rfftfreq(N, 1/sr)
    db = 10 * np.log10(acc / np.max(acc) + 1e-20)
    print(f"\n  [{label}]")
    for lo, hi, nm in [(100,500,"低/厚度   "),(500,2000,"中/主体   "),(2000,4000,"中高/清晰 "),
                       (4000,8000,"高/空气感 "),(8000,14000,"极高/泛音 ")]:
        i = (f >= lo) & (f < hi)
        print(f"    {nm} {lo:5d}-{hi:5d}Hz: {db[i].mean():7.1f} dB")
    above = np.where(db > -60)[0]
    print(f"    有效带宽上限: {f[above.max()]:.0f} Hz")
    rms = 20*np.log10(np.sqrt(np.mean(x**2))+1e-12)
    print(f"    RMS: {rms:.2f} dBFS   峰值: {20*np.log10(np.max(np.abs(x))+1e-12):.2f} dBFS")

print("=== 响度对比 ===")
for p, nm in [(SRC, "原始"), (OUT, "修复版")]:
    d = loudness(p)
    print(f"  {nm:4s}: 集成响度 {d.get('input_i')} LUFS | 真峰值 {d.get('input_tp')} dBTP | 动态 LRA {d.get('input_lra')}")

xo, xr = dec(SRC), dec(OUT)
print(f"\n=== 时长 ===\n  原始 {len(xo)/sr:.2f}s -> 修复版 {len(xr)/sr:.2f}s")
bands(xo, "原始")
bands(xr, "修复版")
