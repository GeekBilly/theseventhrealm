#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 水墨主题 B 版（连奏 / 悠扬 / 空灵 / 大气）

v1（gen-theme-A.py）的问题，来自用户听感反馈：
    「一个音一个音顿开的吹的」「每个音孤立」「要更悠扬空灵、大气一些」

根因与对策：
   ① 断音   前音 release 34% 就走完，且音符零重叠
            ⇒ 音符重叠 0.32s、release 0.55、attack 0.06
   ② 干、不空灵   v1 完全没有混响
            ⇒ 自写 FFT 卷积混响（指数衰减噪声 IR，2.8s 尾巴）+ 40ms 预延迟
   ③ 不够大气   单声部、音域窄
            ⇒ 低八度长音垫铺底 + 旋律音域拉开 + 结尾长音 8s
   ④ 不够悠扬   跳进偏多
            ⇒ 旋律重写为【级进为主、长音更多】

用法  python3 08-音频/gen-theme-B.py
输出  08-音频/候选曲/第七境-水墨主题-B版.wav / .mp3
"""
import subprocess, numpy as np, pathlib

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
OUT = pathlib.Path(__file__).resolve().parent / "候选曲"
OUT.mkdir(parents=True, exist_ok=True)
SR = 48000

A3, C4, D4, E4, G4 = 57, 60, 62, 64, 67
A4, C5, D5, E5, G5, A5 = 69, 72, 74, 76, 79, 81

# (起始秒, MIDI, 时长秒, 力度)  —— v2 旋律：级进为主、音更长
MEL = [
    # 起 —— 从最低处缓缓升起，气若游丝
    (0.0,  A3, 4.0, .52), (3.4,  C4, 3.4, .50), (6.6,  D4, 3.2, .50),
    (9.6,  E4, 4.2, .52), (13.4, D4, 3.6, .48),
    # 承 —— 级进上行，一句一句推进
    (16.6, E4, 3.0, .54), (19.4, G4, 3.4, .56), (22.6, A4, 4.0, .58),
    (26.2, G4, 2.8, .54), (28.8, E4, 3.0, .52), (31.6, G4, 3.2, .56),
    (34.6, A4, 3.6, .58), (38.0, C5, 4.2, .60),
    # 转 —— 升到高处，开阔
    (41.6, D5, 3.4, .66), (44.8, E5, 4.0, .70), (48.4, D5, 3.0, .64),
    (51.2, C5, 3.4, .62), (54.4, A4, 3.8, .60), (57.8, C5, 4.6, .64),
    # 合 —— 缓缓落下，长音铺开收尾
    (61.6, A4, 4.0, .58), (65.2, G4, 4.4, .54), (69.2, E4, 5.0, .50),
    (73.6, D4, 5.0, .46), (78.0, A3, 9.5, .42),
]
TOTAL = 88.0
OVERLAP = 0.32          # 音符重叠（连奏的关键）
LOW_GAIN = 0.22         # 低八度垫的音量


def adsr(n, a=0.06, d=0.16, s=0.86, r=0.55):
    """起音快、尾巴长 —— 连奏的关键不是"不断"，是"音头清晰、尾巴相连"。"""
    ai, di, ri = int(a * n), int(d * n), int(r * n)
    si = max(0, n - ai - di - ri)
    return np.concatenate([
        np.linspace(0, 1, ai), np.linspace(1, s, di),
        np.full(si, s), np.linspace(s, 0, ri),
    ])[:n]


def voice(midi, dur, vel, rng, sr=SR):
    """加法合成箫音（沿用 synth.py 的配方），起音更快、颤音更晚更柔。"""
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
    """自制混响脉冲响应：指数衰减噪声 + 预延迟 + 简易低通（让它温暖不刺）。"""
    n = int(decay * sr)
    t = np.arange(n) / sr
    ir = np.random.default_rng(23).normal(0, 1, n) * np.exp(-t * (5.0 / decay))
    # 一阶低通（越往后越暗，像真实空间）
    a = lp + (1 - lp) * (t / decay)
    out = np.empty(n); acc = 0.0
    for i in range(n):
        acc += a[i] * (ir[i] - acc); out[i] = acc
    out = np.concatenate([np.zeros(int(pre * sr)), out])
    return out / (np.sqrt(np.sum(out ** 2)) + 1e-9)


def fft_convolve(x, ir):
    """FFT 卷积（直接 convolve 在 88s×48k 上太慢）。"""
    n = len(x) + len(ir) - 1
    N = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]
    return y


def main():
    y = np.zeros(int(TOTAL * SR))
    rng = np.random.default_rng(11)
    for t0, midi, dur, vel in MEL:
        # 主声部：时长 + 重叠量（连奏）
        seg = voice(midi, dur + OVERLAP, vel, rng)
        st = int(t0 * SR)
        y[st:st + len(seg)] += seg[:max(0, len(y) - st)]
        # 低八度垫：更长、更轻，铺出"大气"
        seg2 = voice(midi - 12, dur + 1.6, vel * LOW_GAIN, rng)
        y[st:st + len(seg2)] += seg2[:max(0, len(y) - st)]

    dry = y / (np.max(np.abs(y)) + 1e-9) * 0.72
    ir = make_ir()
    wet = fft_convolve(dry, ir)
    wet = wet / (np.max(np.abs(wet)) + 1e-9) * 0.72
    # 干湿比：混响为主但不糊（0.42 干 / 0.58 湿）
    mix = 0.42 * dry + 0.58 * wet
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.75

    wav = OUT / "第七境-水墨主题-B版.wav"
    mp3 = OUT / "第七境-水墨主题-B版.mp3"
    subprocess.run([FF, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-i", "-",
                    "-af", "highpass=f=90,"
                           "acompressor=threshold=-20dB:ratio=2:attack=30:release=400,"
                           "loudnorm=I=-12:TP=-1.5:LRA=11:linear=true,alimiter=limit=0.96",
                    "-c:a", "pcm_s24le", "-ar", "48000", str(wav), "-y"],
                   input=mix.astype(np.float32).tobytes(), capture_output=True)
    subprocess.run([FF, "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "320k", str(mp3), "-y"],
                   capture_output=True)
    print(f"  ✓ {len(MEL)} 个音 · 总长 {TOTAL:.0f}s · 重叠 {OVERLAP}s · 混响 2.8s")
    print(f"  ✓ {wav.name}  {wav.stat().st_size//1024} KB")
    print(f"  ✓ {mp3.name}  {mp3.stat().st_size//1024} KB")


if __name__ == "__main__":
    main()
