#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 水墨主题 A 版（新旋律）

⚠️ 与用户原有的 `第七境主题旋律` **完全不同**：
   那条是用户自己哼的原素材加工而成；这条是**按五声音阶新写的**，
   两者互不影响，可分别用于宣传片 / 商品。

设计：
  调式  A 羽调式（五声音阶：羽 A — 宫 C — 商 D — 角 E — 徵 G），去 4、7 两声
        幽远清冷，贴水墨气质
  速度  60 BPM（一拍 1 秒）
  结构  起承转合（画卷展开 → 叙述 → 推进 → 收）
  音色  复用 synth.py 的加法合成箫音
  力度  每个音单独给幅度，做出"起轻、转满、收长"的强弱曲线

输出  08-音频/候选曲/第七境-水墨主题-A版.wav / .mp3
用法  python3 08-音频/gen-theme-A.py
"""
import subprocess, numpy as np, pathlib

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
OUT = pathlib.Path(__file__).resolve().parent / "候选曲"
OUT.mkdir(parents=True, exist_ok=True)
SR = 48000

# ── 音高（MIDI）──────────────────────────────
A3, C4, D4, E4, G4 = 57, 60, 62, 64, 67
A4, C5, D5, E5, G5 = 69, 72, 74, 76, 79

# ── 旋律：(起始秒, MIDI, 时长秒, 力度 0–1) ────
# 起（画卷慢慢展开，稀疏、轻）
MEL = [
    (0.0,  A4, 3.2, .58), (3.6,  C5, 2.0, .52), (6.0,  A4, 2.6, .55),
    (9.0,  G4, 3.0, .50), (12.4, E4, 3.2, .46),
    # 承（线条出现，叙述）
    (16.0, A4, 1.6, .62), (18.0, C5, 1.5, .64), (20.0, D5, 2.1, .68),
    (22.6, C5, 1.1, .60), (24.0, A4, 1.6, .62), (26.0, G4, 1.1, .56),
    (27.5, A4, 2.1, .64), (30.3, C5, 1.5, .66), (32.4, D5, 1.1, .68),
    (34.0, E5, 2.1, .72), (36.6, D5, 1.5, .68), (38.6, C5, 2.0, .66),
    # 转（音区上移，情绪推进）
    (41.2, E5, 1.6, .78), (43.2, D5, 1.1, .74), (44.8, C5, 1.6, .72),
    (46.8, A4, 2.0, .74), (49.2, G4, 1.1, .66), (50.8, A4, 1.6, .72),
    (52.8, C5, 1.5, .76), (54.8, D5, 2.1, .80), (57.2, E5, 3.0, .82),
    # 合（回落、收束）
    (60.6, D5, 2.0, .70), (63.0, C5, 2.0, .64), (65.4, A4, 2.6, .58),
    (68.4, G4, 2.0, .50), (70.8, A4, 4.4, .46),
]
TOTAL = 76.0


def adsr(n, a=0.11, d=0.14, s=0.80, r=0.34):
    return np.clip(np.concatenate([
        np.linspace(0, 1, int(a * n)),
        np.linspace(1, s, int(d * n)),
        np.full(max(0, int(n - (a + d + r) * n)), s),
        np.linspace(s, 0, int(r * n)),
    ]), 0, 1)


def main():
    y = np.zeros(int(TOTAL * SR))
    rng = np.random.default_rng(11)
    for i, (t0, midi, dur, vel) in enumerate(MEL):
        n = int(dur * SR)
        t = np.arange(n) / SR
        f0 = 440 * 2 ** ((midi - 69) / 12)
        # 颤音：延迟进入，越到后面越明显
        vib = 1 + 0.0045 * np.sin(2 * np.pi * 5.0 * t) * np.clip((t - 0.30) / 0.35, 0, 1)
        ph = 2 * np.pi * f0 * np.cumsum(vib) / SR
        tone = (np.sin(ph) + 0.17 * np.sin(2 * ph) + 0.075 * np.sin(3 * ph) + 0.03 * np.sin(4 * ph))
        # 气息噪声：只在音头
        br = np.convolve(rng.normal(0, 1, n), np.ones(64) / 64, mode="same")
        br = br / (np.max(np.abs(br)) + 1e-9) * 0.022 * np.clip((0.45 - t) / 0.45, 0, 1)
        env = adsr(n)
        if len(env) < n:
            env = np.pad(env, (0, n - len(env)), constant_values=env[-1] if len(env) else 0)
        seg = (tone * env * 0.30 + br) * vel
        st = int(t0 * SR)
        y[st:st + n] += seg[:max(0, len(y) - st)]
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.72

    wav = OUT / "第七境-水墨主题-A版.wav"
    mp3 = OUT / "第七境-水墨主题-A版.mp3"
    subprocess.run([FF, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-i", "-",
                    "-af", "highpass=f=120,acompressor=threshold=-22dB:ratio=2.5:attack=20:release=250,"
                           "loudnorm=I=-16:TP=-1.5:LRA=9:linear=true,alimiter=limit=0.96",
                    "-c:a", "pcm_s24le", "-ar", "48000", str(wav), "-y"],
                   input=y.astype(np.float32).tobytes(), capture_output=True)
    subprocess.run([FF, "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "320k", str(mp3), "-y"],
                   capture_output=True)
    print(f"  ✓ {len(MEL)} 个音，总长 {TOTAL:.0f}s")
    print(f"  ✓ {wav.name}  {wav.stat().st_size//1024} KB")
    print(f"  ✓ {mp3.name}  {mp3.stat().st_size//1024} KB")


if __name__ == "__main__":
    main()
