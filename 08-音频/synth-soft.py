import json, subprocess, numpy as np
from scipy.signal import fftconvolve

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
notes = json.load(open(BASE + "melody-quantized.json", encoding="utf-8"))
sr = 48000
BPM = 72
grid = (60.0 / BPM) / 2
rng = np.random.default_rng(11)

TAIL = 0.34
total = max(n["t"] + n["dur"] for n in notes) + TAIL + 2.2
y = np.zeros(int(total * sr))

def env_curve(n, dur):
    """拱形呼吸包络：柔起音 -> 微落 -> 渐强到顶 -> 缓收 -> 长尾释放"""
    t = np.arange(n) / sr
    a, r = 0.14, min(0.48, dur * 0.55)
    na, nr = max(1, int(a * sr)), max(1, int(r * sr))
    e = np.ones(n)
    if na < n:
        e[:na] = np.sin(np.linspace(0, np.pi / 2, na)) ** 0.75
    body_n = max(0, n - na - nr)
    if body_n > 0:
        body = np.linspace(0, 1, body_n)
        arch = 0.58 + 0.46 * np.sin(np.pi * body ** 0.80)
        amp = min(0.24, 0.07 + dur * 0.045)
        breath = 1 + amp * np.sin(2 * np.pi * 0.58 * t[na:na + body_n] + 0.6)
        e[na:na + body_n] = arch * breath
    if nr * 2 < n:
        e[-nr:] = np.cos(np.linspace(0, np.pi / 2, nr)) ** 1.25
    return np.clip(e, 0, 1.4)

print(f"柔和版合成：{len(notes)} 个音符")
prev_f, prev_end = None, -9.0
for i, nt in enumerate(notes):
    f0 = 440 * 2 ** ((nt["q"] - 69) / 12)
    dur = max(1, round(nt["dur"] / grid)) * grid * float(rng.uniform(1.00, 1.03))
    n = int((dur + TAIL) * sr)
    t = np.arange(n) / sr
    st = int(nt["t"] * sr)

    gap = nt["t"] - prev_end
    glide = 0.0
    if prev_f and gap < 0.30:
        steps = abs(12 * np.log2(f0 / prev_f))
        glide = min(0.20, 0.055 + 0.020 * steps)

    fe = np.full(n, f0)
    if glide > 0:
        ng = max(1, int(glide * sr))
        fe[:ng] = prev_f * (f0 / prev_f) ** (np.arange(ng) / ng)

    vib = 1 + 0.0065 * np.sin(2 * np.pi * 5.0 * t) * np.clip((t - 0.28) / 0.35, 0, 1)
    ph = 2 * np.pi * np.cumsum(fe * vib) / sr

    tone = (np.sin(ph)
            + 0.105 * np.sin(2 * ph)
            + 0.042 * np.sin(3 * ph)
            + 0.014 * np.sin(4 * ph)
            + 0.006 * np.sin(5 * ph))

    nz = rng.normal(0, 1, n)
    b = np.convolve(nz, np.ones(96) / 96, mode="same")
    b /= (np.max(np.abs(b)) + 1e-9)
    b *= 0.016 * np.clip((0.55 - t) / 0.55, 0, 1)

    seg = (tone * 0.30 + b) * env_curve(n, dur)
    if st + len(seg) > len(y):
        seg = seg[:len(y) - st]
    if st >= 0:
        y[st:st + len(seg)] += seg

    prev_f = f0
    prev_end = nt["t"] + dur
    if (i + 1) % 40 == 0:
        print(f"  {i+1}/{len(notes)}")

y /= (np.max(np.abs(y)) + 1e-9)

print("加混响（2.2s 指数衰减）...")
rt = np.arange(int(2.2 * sr)) / sr
ir = rng.normal(0, 1, len(rt)) * np.exp(-rt * 2.6)
ir /= (np.sum(ir ** 2) ** 0.5 + 1e-9)
wet = fftconvolve(y, ir, mode="full")[:len(y)]
wet /= (np.max(np.abs(wet)) + 1e-9)
y = (y * 0.86 + wet * 0.17)
y /= (np.max(np.abs(y)) + 1e-9)
y *= 0.78

print("母带处理 ...")
subprocess.run([FF, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-i", "-",
                "-af", "highpass=f=110,lowpass=f=6500,"
                       "acompressor=threshold=-26dB:ratio=1.5:attack=35:release=340,"
                       "loudnorm=I=-17:TP=-1.5:LRA=8:linear=true,alimiter=limit=0.95",
                "-c:a", "pcm_s24le", "-ar", "48000",
                BASE + "第七境主题旋律-箫音柔版.wav", "-y"],
               input=y.astype(np.float32).tobytes(), capture_output=True)
subprocess.run([FF, "-i", BASE + "第七境主题旋律-箫音柔版.wav",
                "-c:a", "libmp3lame", "-b:a", "320k",
                BASE + "第七境主题旋律-箫音柔版.mp3", "-y"], capture_output=True)
print("完成")
