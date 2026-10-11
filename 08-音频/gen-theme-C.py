#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 水墨主题 C 版（音距更紧 · 连绵）

在 B 版基础上的唯一改动，来自用户反馈：
    「每个音之间间隔的时间短一些可以不」

⇒ 不是把音变短，而是【让后一个音来得更早、叠得更深】：
   · 起点间隔：3.0–3.5s → 2.0s（起）／1.5–2.0s（承转）
   · 重叠量  ：0.32s → 0.60s（叠得深，连绵不断）
   · 音符时长：仍保持 2.2–3.2s（长音感不丢）
   · 混响干湿：42:58 → 52:48（音密了，混响收一点免得糊）

其余（音色、低八度垫、混响 IR、母带链）与 B 版一致。

用法  python3 08-音频/gen-theme-C.py
输出  08-音频/候选曲/第七境-水墨主题-C版.wav / .mp3
"""
import subprocess, numpy as np, pathlib

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
OUT = pathlib.Path(__file__).resolve().parent / "候选曲"
OUT.mkdir(parents=True, exist_ok=True)
SR = 48000

A3, C4, D4, E4, G4 = 57, 60, 62, 64, 67
A4, C5, D5, E5, G5 = 69, 72, 74, 76, 79

# (起始秒, MIDI, 时长秒, 力度) —— 起点更密，级进为主
MEL = [
    # 起（间隔 2.0s）
    (0.0,  A3, 2.8, .50), (2.0,  C4, 2.6, .50), (4.0,  D4, 2.6, .50),
    (6.0,  E4, 2.8, .52), (8.0,  D4, 2.6, .50), (10.0, C4, 2.6, .48),
    (12.0, D4, 2.8, .50), (14.0, E4, 3.0, .52),
    # 承（间隔 2.0s，起伏）
    (16.0, G4, 2.4, .55), (18.0, A4, 2.6, .57), (20.0, G4, 2.4, .55),
    (22.0, E4, 2.4, .53), (24.0, G4, 2.6, .55), (26.0, A4, 2.6, .57),
    (28.0, C5, 2.8, .59), (30.0, A4, 2.4, .57), (32.0, G4, 2.4, .55),
    (34.0, A4, 2.6, .57), (36.0, C5, 2.8, .60), (38.0, D5, 3.0, .62),
    (40.0, C5, 2.6, .60),
    # 转（间隔 2.0s，开阔）
    (42.0, E5, 2.8, .68), (44.0, D5, 2.6, .66), (46.0, C5, 2.6, .64),
    (48.0, D5, 2.8, .66), (50.0, E5, 3.0, .70), (52.0, D5, 2.6, .66),
    (54.0, C5, 2.6, .64), (56.0, A4, 2.8, .62), (58.0, C5, 3.0, .64),
    (60.0, D5, 3.2, .66),
    # 合（间隔拉大，缓缓收）
    (62.5, A4, 3.2, .60), (65.0, G4, 3.4, .56), (67.5, E4, 3.6, .52),
    (70.5, D4, 3.8, .48), (74.0, C4, 3.8, .46), (77.5, A3, 4.0, .44),
    (81.0, A3, 8.0, .40),                      # 长尾
]
TOTAL = 90.0
OVERLAP = 0.60      # ← 比 B 版深一倍（0.32 → 0.60）
LOW_GAIN = 0.20
DRY, WET = 0.52, 0.48


def adsr(n, a=0.06, d=0.16, s=0.86, r=0.55):
    ai, di, ri = int(a * n), int(d * n), int(r * n)
    si = max(0, n - ai - di - ri)
    return np.concatenate([
        np.linspace(0, 1, ai), np.linspace(1, s, di),
        np.full(si, s), np.linspace(s, 0, ri),
    ])[:n]


def voice(midi, dur, vel, rng, sr=SR):
    n = int(dur * sr)
    t = np.arange(n) / sr
    f0 = 440 * 2 ** ((midi - 69) / 12)
    vib = 1 + 0.0055 * np.sin(2 * np.pi * 4.6 * t) * np.clip((t - 0.45) / 0.5, 0, 1)
    ph = 2 * np.pi * f0 * np.cumsum(vib) / sr
    tone = (np.sin(ph) + 0.17 * np.sin(2 * ph) + 0.075 * np.sin(3 * ph) + 0.03 * np.sin(4 * ph))
    br = np.convolve(rng.normal(0, 1, n), np.ones(96) / 96, mode="same")
    br = br / (np.max(np.abs(br)) + 1e-9) * 0.020 * np.clip((0.55 - t) / 0.55, 0, 1)
    return (tone * adsr(n) * 0.30 + br) * vel


def make_ir(sr=SR, decay=2.8, pre=0.040, lp=0.35):
    n = int(decay * sr)
    t = np.arange(n) / sr
    ir = np.random.default_rng(23).normal(0, 1, n) * np.exp(-t * (5.0 / decay))
    a = lp + (1 - lp) * (t / decay)
    out = np.empty(n); acc = 0.0
    for i in range(n):
        acc += a[i] * (ir[i] - acc); out[i] = acc
    out = np.concatenate([np.zeros(int(pre * sr)), out])
    return out / (np.sqrt(np.sum(out ** 2)) + 1e-9)


def fft_convolve(x, ir):
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]


def main():
    y = np.zeros(int(TOTAL * SR))
    rng = np.random.default_rng(11)
    for t0, midi, dur, vel in MEL:
        seg = voice(midi, dur + OVERLAP, vel, rng)          # ← 叠深
        st = int(t0 * SR)
        y[st:st + len(seg)] += seg[:max(0, len(y) - st)]
        seg2 = voice(midi - 12, dur + 1.4, vel * LOW_GAIN, rng)
        y[st:st + len(seg2)] += seg2[:max(0, len(y) - st)]

    dry = y / (np.max(np.abs(y)) + 1e-9) * 0.72
    wet = fft_convolve(dry, make_ir())
    wet = wet / (np.max(np.abs(wet)) + 1e-9) * 0.72
    mix = DRY * dry + WET * wet
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.75

    wav = OUT / "第七境-水墨主题-C版.wav"
    mp3 = OUT / "第七境-水墨主题-C版.mp3"
    subprocess.run([FF, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-i", "-",
                    "-af", "highpass=f=90,"
                           "acompressor=threshold=-20dB:ratio=2:attack=30:release=400,"
                           "loudnorm=I=-12:TP=-1.5:LRA=11:linear=true,alimiter=limit=0.96",
                    "-c:a", "pcm_s24le", "-ar", "48000", str(wav), "-y"],
                   input=mix.astype(np.float32).tobytes(), capture_output=True)
    subprocess.run([FF, "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "320k", str(mp3), "-y"],
                   capture_output=True)
    print(f"  ✓ {len(MEL)} 个音 · 总长 {TOTAL:.0f}s · 重叠 {OVERLAP}s · 干湿 {int(DRY*100)}:{int(WET*100)}")
    print(f"  ✓ {wav.name}  {wav.stat().st_size//1024} KB")
    print(f"  ✓ {mp3.name}  {mp3.stat().st_size//1024} KB")


if __name__ == "__main__":
    main()
