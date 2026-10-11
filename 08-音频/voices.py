import json, subprocess, numpy as np
from scipy.signal import fftconvolve

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
notes_all = json.load(open(BASE + "melody-quantized.json", encoding="utf-8"))
sr = 48000
BPM = 72
grid = (60.0 / BPM) / 2
rng = np.random.default_rng(11)

VOICES = {
    "埙": dict(tp=-12, harm=[(1,1.0),(2,0.055),(3,0.022),(4,0.008)],
               breath=0.055, atk=0.19, rel=0.55, lp=2400, tail=0.40, wet=0.20, gain=0.30),
    "柔箫": dict(tp=-12, harm=[(1,1.0),(2,0.085),(3,0.030),(4,0.010)],
               breath=0.022, atk=0.15, rel=0.45, lp=3300, tail=0.36, wet=0.17, gain=0.30),
    "弦乐垫": dict(tp=-12, harm=[(1,1.0),(2,0.13),(3,0.055),(4,0.020),(5,0.008)],
               breath=0.004, atk=0.42, rel=0.70, lp=2900, tail=0.50, wet=0.24, gain=0.26, detune=4.5),
}

def render(notes, v, t_end):
    TAIL = v["tail"]
    total = t_end + TAIL + 2.2
    y = np.zeros(int(total * sr))
    prev_f, prev_end = None, -9.0
    for nt in notes:
        if nt["t"] > t_end: break
        q = nt["q"] + v["tp"]
        f0 = 440 * 2 ** ((q - 69) / 12)
        dur = max(1, round(nt["dur"] / grid)) * grid
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
        vib = 1 + 0.0055 * np.sin(2 * np.pi * 4.7 * t) * np.clip((t - 0.32) / 0.4, 0, 1)
        ph = 2 * np.pi * np.cumsum(fe * vib) / sr
        tone = np.zeros(n)
        det = v.get("detune", 0)
        if det:
            for c in (-det, 0, det):
                p2 = ph * (1 + c / 1200.0 / 8.33)
                for m, a in v["harm"]:
                    tone += a / 3 * np.sin(m * p2)
        else:
            for m, a in v["harm"]:
                tone += a * np.sin(m * ph)
        nz = rng.normal(0, 1, n)
        b = np.convolve(nz, np.ones(int(sr*0.002)) / max(1,int(sr*0.002)), mode="same")
        b /= (np.max(np.abs(b)) + 1e-9)
        b *= v["breath"] * np.clip((0.65 - t) / 0.65, 0, 1)
        a, r = v["atk"], min(v["rel"], dur * 0.6)
        na, nr = max(1, int(a*sr)), max(1, int(r*sr))
        e = np.ones(n)
        if na < n: e[:na] = np.sin(np.linspace(0, np.pi/2, na)) ** 0.7
        bn = max(0, n - na - nr)
        if bn > 0:
            body = np.linspace(0, 1, bn)
            amp = min(0.24, 0.07 + dur * 0.045)
            e[na:na+bn] = (0.58 + 0.46*np.sin(np.pi*body**0.80)) * (1 + amp*np.sin(2*np.pi*0.58*t[na:na+bn]+0.6))
        if nr*2 < n: e[-nr:] = np.cos(np.linspace(0, np.pi/2, nr)) ** 1.25
        seg = (tone * v["gain"] + b) * np.clip(e, 0, 1.4)
        if st >= 0 and st + len(seg) <= len(y):
            y[st:st+len(seg)] += seg
        prev_f, prev_end = f0, nt["t"] + dur
    y /= (np.max(np.abs(y)) + 1e-9)
    rt = np.arange(int(2.2*sr))/sr
    ir = rng.normal(0, 1, len(rt)) * np.exp(-rt * 2.6)
    ir /= (np.sum(ir**2) ** 0.5 + 1e-9)
    wet = fftconvolve(y, ir, mode="full")[:len(y)]
    wet /= (np.max(np.abs(wet)) + 1e-9)
    y = y * (1 - v["wet"]*0.5) + wet * v["wet"]
    y /= (np.max(np.abs(y)) + 1e-9)
    return y * 0.78

T_END = 32.0
print(f"生成 3 个音色片段（0–{T_END:.0f}s）")
for name, v in VOICES.items():
    y = render(notes_all, v, T_END)
    out = BASE + f"音色对比-{name}.wav"
    subprocess.run([FF, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-i", "-",
                    "-af", f"highpass=f=90,lowpass=f={v['lp']},"
                           f"acompressor=threshold=-26dB:ratio=1.5:attack=35:release=340,"
                           f"loudnorm=I=-17:TP=-1.5:LRA=8:linear=true,alimiter=limit=0.95",
                    "-c:a", "pcm_s24le", "-ar", "48000", out, "-y"],
                   input=y.astype(np.float32).tobytes(), capture_output=True)
    subprocess.run([FF, "-i", out, "-c:a", "libmp3lame", "-b:a", "320k",
                    BASE + f"音色对比-{name}.mp3", "-y"], capture_output=True)
    print(f"  {name} 完成")
print("done")
