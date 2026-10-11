import subprocess
import numpy as np

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
SRC = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/第七境主题背景音乐-原始.m4a"
sr = 44100
pcm = subprocess.run([FF, "-i", SRC, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
x = np.frombuffer(pcm.stdout, dtype=np.float32)
print(f"总样本 {len(x)}  时长 {len(x)/sr:.2f}s")

def spec(sig):
    w = np.hanning(len(sig))
    X = np.abs(np.fft.rfft(sig * w))
    f = np.fft.rfftfreq(len(sig), 1/sr)
    return f, X

print("\n=== 细粒度频谱 (整段平均, 每 250Hz) ===")
N = sr * 8
acc = np.zeros(N // 2 + 1)
cnt = 0
for i in range(0, len(x) - N, N):
    f, X = spec(x[i:i+N])
    acc += X ** 2
    cnt += 1
f = np.fft.rfftfreq(N, 1/sr)
acc /= max(cnt, 1)
acc_db = 10 * np.log10(acc / (np.max(acc) + 1e-20) + 1e-20)
for lo in range(0, 22050, 250):
    idx = (f >= lo) & (f < lo + 250)
    v = acc_db[idx].mean()
    bar = "#" * max(0, int((v + 90) / 2))
    print(f"  {lo:5d}-{lo+250:5d}Hz: {v:7.1f}dB {bar}")

print("\n=== 有效带宽上限 (低于峰值 -60dB 的频率) ===")
peak_i = np.argmax(acc)
above = np.where(acc_db > -60)[0]
print(f"  峰值频率: {f[peak_i]:.0f} Hz")
print(f"  有效带宽上限: {f[above.max()]:.0f} Hz  <-- 超过此频率基本无声")

print("\n=== 分时段主频 (前 12 个 2 秒窗) ===")
for i in range(12):
    s = x[int(i*2*sr):int((i+1)*2*sr)]
    if len(s) < sr: break
    fq, X = spec(s[:sr*2])
    top = np.argsort(X)[-5:][::-1]
    rms = 20*np.log10(np.sqrt(np.mean(s**2))+1e-10)
    print(f"  {i*2:3d}-{(i+1)*2:3d}s RMS {rms:6.1f}dB | 主频: " + ", ".join(f"{fq[t]:.0f}Hz" for t in top))

print("\n=== 基音周期检测 (自相关, 判断是否有明确音高) ===")
for t in [10, 30, 60, 90, 115]:
    s = x[int(t*sr):int((t+2)*sr)]
    s = s - np.mean(s)
    if len(s) < sr: continue
    c = np.correlate(s[:sr], s[:sr], mode="full")[sr-1:]
    c = c / (c[0] + 1e-20)
    lo, hi = int(sr/800), int(sr/70)
    seg = c[lo:hi]
    pi = np.argmax(seg) + lo
    conf = c[pi]
    print(f"  {t:3d}s 处基频 ≈ {sr/pi:6.1f} Hz  (相关度 {conf:.2f})" + ("  <- 音高明确" if conf > 0.5 else "  <- 无明显音高"))

print("\n=== 高频噪声底 vs 信号 (判断是否被低通/窄带编码) ===")
for band in [(100, 500), (500, 2000), (2000, 4000), (4000, 8000), (8000, 12000), (12000, 16000), (16000, 22000)]:
    idx = (f >= band[0]) & (f < band[1])
    print(f"  {band[0]:5d}-{band[1]:5d}Hz: 相对峰值 {acc_db[idx].mean():7.1f} dB")
