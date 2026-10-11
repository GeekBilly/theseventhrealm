import subprocess, json, sys, re, os
import numpy as np

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
SRC = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/第七境主题背景音乐-原始.m4a"

def run(args):
    r = subprocess.run([FF] + args, capture_output=True, text=True)
    return r.stdout + r.stderr

info = run(["-i", SRC])
print("=== 元信息 ===")
for line in info.splitlines():
    if any(k in line for k in ["Duration", "Stream", "Audio:", "Input"]):
        print(line.strip())

print("\n=== 响度分析 (loudnorm) ===")
ln = run(["-i", SRC, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
m = re.search(r"\{[^{}]*\"input_i\"[\s\S]*?\}", ln)
if m:
    d = json.loads(m.group(0))
    for k in ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"]:
        print(f"  {k}: {d.get(k)}")
else:
    print("  解析失败", ln[-800:])

print("\n=== 静音段 (silencedetect, -40dB) ===")
sd = run(["-i", SRC, "-af", "silencedetect=noise=-40dB:d=0.3", "-f", "null", "-"])
hits = re.findall(r"silence_(start|end): ([\d.\-]+)", sd)
print(f"  静音事件数: {len(hits)//2}")
for k, v in hits[:20]:
    print(f"  {k}: {v}")

print("\n=== 波形解码 ===")
pcm = subprocess.run([FF, "-i", SRC, "-f", "f32le", "-ac", "1", "-ar", "44100", "-"],
                     capture_output=True)
x = np.frombuffer(pcm.stdout, dtype=np.float32)
sr = 44100
dur = len(x) / sr
print(f"  时长: {dur:.2f}s  样本数: {len(x)}")

def db(v):
    return 20 * np.log10(max(v, 1e-10))

peak = np.max(np.abs(x))
rms = np.sqrt(np.mean(x ** 2))
print(f"  峰值: {db(peak):.2f} dBFS")
print(f"  整体 RMS: {db(rms):.2f} dBFS")
print(f"  峰均比 (crest): {db(peak) - db(rms):.2f} dB")

win = int(sr * 0.05)
n = len(x) // win
seg = np.sqrt(np.array([np.mean(x[i*win:(i+1)*win] ** 2) for i in range(n)]))
segdb = np.array([db(s) for s in seg])
floor = np.percentile(segdb, 5)
top = np.percentile(segdb, 95)
print(f"  前 5% 低电平(噪底参考): {floor:.2f} dBFS")
print(f"  前 95% 高电平: {top:.2f} dBFS")
print(f"  电平动态: {top - floor:.2f} dB")

print("\n=== 逐秒电平轮廓 ===")
for i in range(int(dur)):
    s = x[int(i*sr):int((i+1)*sr)]
    if len(s) == 0: break
    r = db(np.sqrt(np.mean(s ** 2)))
    bar = "#" * max(0, int((r + 70) * 1.2))
    print(f"  {i:3d}s | {r:7.2f}dB {bar}")

print("\n=== 频段能量分布 (FFT) ===")
X = np.abs(np.fft.rfft(x[: min(len(x), sr*30)]))
freqs = np.fft.rfftfreq(min(len(x), sr*30), 1/sr)
bands = [(20,80,"超低频/隆隆"),(80,250,"低频/底鼓厚度"),(250,500,"中低/人声胸腔"),
         (500,2000,"中频/人声主体"),(2000,4000,"中高/清晰度"),(4000,8000,"高频/空气感"),
         (8000,16000,"极高频/泛音"),(16000,22050,"超高频")]
tot = np.sum(X ** 2)
for lo, hi, name in bands:
    idx = (freqs >= lo) & (freqs < hi)
    e = np.sum(X[idx] ** 2) / tot * 100
    print(f"  {lo:5d}-{hi:5d}Hz {name:14s}: {e:5.2f}%  {'|' * int(e/1.5)}")

print("\n=== 削波检测 ===")
clip = np.sum(np.abs(x) > 0.999)
print(f"  接近满刻度样本: {clip} ({clip/len(x)*100:.4f}%)")
