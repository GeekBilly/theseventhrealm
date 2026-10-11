import json, subprocess, numpy as np

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
notes = json.load(open(BASE + "melody-quantized.json", encoding="utf-8"))
sr = 48000
BPM = 72
grid = (60.0 / BPM) / 2

total = max(n["t"] + n["dur"] for n in notes) + 3.0
y = np.zeros(int(total * sr))
rng = np.random.default_rng(7)

def adsr(n, a=0.09, d=0.12, s=0.82, r=0.30):
    return np.clip(np.concatenate([
        np.linspace(0, 1, int(a*n)),
        np.linspace(1, s, int(d*n)),
        np.full(max(0, int(n - (a+d+r)*n)), s),
        np.linspace(s, 0, int(r*n)),
    ]), 0, 1)

print(f"合成 {len(notes)} 个音符，总长 {total:.1f}s")
for i, nt in enumerate(notes):
    f0 = 440 * 2 ** ((nt["q"] - 69) / 12)
    dur = max(1, round(nt["dur"] / grid)) * grid
    n = int(dur * sr)
    if n <= 0: continue
    t = np.arange(n) / sr
    vib = 1 + 0.004 * np.sin(2*np.pi*5.1*t) * np.clip((t - 0.25)/0.3, 0, 1)
    ph = 2 * np.pi * f0 * np.cumsum(vib) / sr
    tone = (np.sin(ph)
            + 0.16 * np.sin(2*ph)
            + 0.07 * np.sin(3*ph)
            + 0.03 * np.sin(4*ph))
    breath = rng.normal(0, 1, n)
    b = np.convolve(breath, np.ones(64)/64, mode="same")
    b = b / (np.max(np.abs(b)) + 1e-9) * 0.018
    b *= np.clip((0.4 - t) / 0.4, 0, 1)
    env = adsr(n)
    if len(env) < n: env = np.pad(env, (0, n - len(env)), constant_values=env[-1] if len(env) else 0)
    seg = (tone * env * 0.30 + b)
    st = int(nt["t"] * sr)
    y[st:st+n] += seg[:len(y)-st] if st + n > len(y) else seg
    if (i+1) % 30 == 0: print(f"  {i+1}/{len(notes)}")

y = y / (np.max(np.abs(y)) + 1e-9) * 0.72
print("导出 ...")
subprocess.run([FF, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-i", "-",
                "-af", "highpass=f=120,acompressor=threshold=-22dB:ratio=2.5:attack=20:release=250,"
                       "loudnorm=I=-16:TP=-1.5:LRA=9:linear=true,alimiter=limit=0.96",
                "-c:a", "pcm_s24le", "-ar", "48000",
                BASE + "第七境主题旋律-箫音版.wav", "-y"],
               input=y.astype(np.float32).tobytes(), capture_output=True)
subprocess.run([FF, "-i", BASE + "第七境主题旋律-箫音版.wav",
                "-c:a", "libmp3lame", "-b:a", "320k", BASE + "第七境主题旋律-箫音版.mp3", "-y"],
               capture_output=True)
print("完成")
