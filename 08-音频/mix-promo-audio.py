#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宣传片配乐：削顶修整 + 段落能量图（2026-10-09，0 积分，全本地 ffmpeg）。

⭐ 用途：把用户选定的配乐（joyvideo123《The Eternal Ascension》· Pixabay）
   处理成可直接喂给成片的音轨，并输出「16 段画面 ↔ 音乐能量」对照图。

为什么必须有这一步：
  · 原曲**真峰值 +0.12 dBTP（本身削顶）**，直接合进视频会 digital clip；
    衰减 1.5 dB 后峰值落到 −1.38 dBFS，既去削顶又不引入 limiter 的呼吸失真。
  · 16 段画面各 15 s，但音乐有强弱结构（25–35 s 有个 −31 dB 的塌陷、
    185–230 s 是全曲最响区）⇒ 排段时间轴必须看着能量图定，不能平均分。

用法：
    python3 mix-promo-audio.py                     # 出修整版 wav + 能量图（默认参数）
    python3 mix-promo-audio.py --headroom 2.0      # 留 2 dB 余量
    python3 mix-promo-audio.py --fade-in 2 --fade-out 5
    python3 mix-promo-audio.py --curve-only        # 只出能量图，不出音轨
    python3 mix-promo-audio.py --head 5 --seg 15   # 改时间轴起点／段长，重排段落表

输出：
    08-音频/成片音轨/宣传片01-配乐-4m10s-<headroom>dB.wav   （48 kHz 立体声）
    08-音频/成片音轨/_配乐能量与16段分界.png                （排段用）
"""
import argparse
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent      # 根 = 08-音频 的上级
AUDIO = ROOT / '08-音频'
SRC = AUDIO / '候选曲/joyvideo123-the-eternal-ascension-568279.mp3'
OUT = AUDIO / '成片音轨'

# 视频里 16 段的排列＝客户交付包的时序（01-三皇五帝 … 16-觉醒年代）
ORDER = ['三皇五帝', '夏', '商', '周', '秦', '汉', '三国', '两晋南北朝',
         '隋', '唐', '五代十国', '宋', '元', '明', '清', '觉醒年代']

try:
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FF = 'ffmpeg'


def load_mono(path, sr=8000):
    """解码成单声道 8 kHz，只为做能量统计（不用于出音轨）。"""
    p = subprocess.run([FF, '-v', 'error', '-i', str(path),
                        '-ac', '1', '-ar', str(sr), '-f', 's16le', '-'],
                       capture_output=True)
    if p.returncode != 0 or not p.stdout:
        sys.exit(f'解码失败：{p.stderr.decode("utf-8", "ignore")[:300]}')
    return np.frombuffer(p.stdout, dtype='<i2').astype(float) / 32768.0, sr


def peak_db(path):
    """实测输出文件的真峰值（dBFS）。

    ⚠️ 不能用 `-v error`：astats 的结果打在 info 级别，压掉之后解析不到 ⇒ 会得到 nan。
    """
    p = subprocess.run([FF, '-hide_banner', '-i', str(path), '-af',
                        'astats=metadata=1:reset=0', '-f', 'null', '-'],
                       capture_output=True, text=True)
    for line in reversed(p.stderr.splitlines()):
        if 'Peak level dB' in line:
            return float(line.split(':')[-1].strip())
    return float('nan')


def make_track(src, out, headroom, fade_in, fade_out):
    af = [f'volume=-{headroom}dB']
    if fade_in:
        af.append(f'afade=t=in:st=0:d={fade_in}')
    if fade_out:
        af.append(f'afade=t=out:st={DUR - fade_out:.3f}:d={fade_out}')
    cmd = [FF, '-y', '-v', 'error', '-i', str(src), '-af', ','.join(af),
           '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f'音轨处理失败：{p.stderr[-400:]}')
    return out


def draw_curve(a, sr, head, seg, out_png):
    """能量曲线 + 16 段分界（PIL 手绘，不依赖 matplotlib）。"""
    from PIL import Image, ImageDraw, ImageFont

    def font(sz):
        for p in ('/System/Library/Fonts/PingFang.ttc',
                  '/System/Library/Fonts/STHeiti Medium.ttc',
                  '/System/Library/Fonts/Hiragino Sans GB.ttc'):
            if pathlib.Path(p).exists():
                try:
                    return ImageFont.truetype(p, sz)
                except Exception:
                    pass
        return ImageFont.load_default()

    W, H = 1680, 620
    L, R, T, B = 70, 40, 92, 60          # 画布边距
    pw, ph = W - L - R, H - T - B
    dur = len(a) / sr
    win = sr * 5
    n = max(1, len(a) // win)
    rms = np.array([np.sqrt((a[i * win:(i + 1) * win] ** 2).mean()) for i in range(n)])
    db = 20 * np.log10(rms + 1e-9)
    lo, hi = -34.0, -13.0

    def x_of(t):
        return L + t / dur * pw

    def y_of(v):
        return T + (hi - v) / (hi - lo) * ph

    im = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(im)
    f_t, f_s, f_x = font(24), font(16), font(15)

    d.text((L, 20), '宣传片 01 · 配乐能量与 16 段分界', font=f_t, fill=(20, 20, 20))
    d.text((L, 52), f'joyvideo123《The Eternal Ascension》· Pixabay License ｜ '
                    f'片头 {head:.0f}s + 16×{seg:.0f}s + 片尾 {dur - head - 16 * seg:.1f}s',
           font=f_s, fill=(90, 90, 90))

    # 纵轴刻度
    for v in range(int(hi), int(lo) - 1, -4):
        y = y_of(v)
        d.line([(L - 6, y), (L + pw, y)], fill=(232, 232, 232))
        d.text((12, y - 8), f'{v} dB', font=f_x, fill=(120, 120, 120))

    # 段底色（强=红/中=橙/弱=蓝）+ 分界线
    for i, name in enumerate(ORDER):
        s = head + i * seg
        e = s + seg
        seg_db = db[int(s / 5):max(int(s / 5) + 1, int(e / 5))].mean()
        col = ((250, 228, 228) if seg_db > -17 else
               (252, 240, 220) if seg_db > -20 else (226, 236, 250))
        d.rectangle([x_of(s), T, x_of(e), T + ph], fill=col)
        d.line([(x_of(s), T), (x_of(s), T + ph)], fill=(190, 190, 190))
        d.text(((x_of(s) + x_of(e)) / 2 - len(name) * 7, T + ph + 8),
               name, font=f_x, fill=(40, 40, 40))
    d.line([(x_of(head + 16 * seg), T), (x_of(head + 16 * seg), T + ph)], fill=(190, 190, 190))

    # 曲线
    pts = [(x_of(i * 5), y_of(v)) for i, v in enumerate(db)]
    d.line(pts, fill=(30, 110, 200), width=2)
    d.line([(x_of(0), y_of(0)), (x_of(dur), y_of(0))], fill=(200, 60, 60), width=1)

    # 标注塌陷段与最响段
    def mark(t0, t1, text, fill):
        y = T + 6
        d.rectangle([x_of(t0), y, x_of(t1), y + 4], fill=fill)
        d.text((x_of(t0) + 4, y + 8), text, font=f_x, fill=fill)

    mark(25, 35, '塌陷 −31dB', (200, 60, 60))
    mark(185, 230, '全曲最响', (40, 130, 60))
    mark(0, head, '片头', (120, 120, 120))
    mark(head + 16 * seg, dur, '片尾', (120, 120, 120))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_png)
    return out_png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=str(SRC))
    ap.add_argument('--headroom', type=float, default=1.5, help='削顶衰减量 dB（默认 1.5）')
    ap.add_argument('--fade-in', type=float, default=0)
    ap.add_argument('--fade-out', type=float, default=0)
    ap.add_argument('--head', type=float, default=5.0, help='画面起点（片头秒数）')
    ap.add_argument('--seg', type=float, default=15.0, help='每朝时长')
    ap.add_argument('--curve-only', action='store_true')
    ap.add_argument('--mp3', action='store_true', help='另存一份 256k mp3（便于上传／试听）')
    a = ap.parse_args()

    src = pathlib.Path(a.src)
    if not src.exists():
        sys.exit(f'找不到配乐：{src}')

    global DUR
    wav, sr = load_mono(src)
    DUR = len(wav) / sr
    print(f'源：{src.name}')
    print(f'时长 {DUR:.2f}s（{int(DUR // 60)}:{DUR % 60:04.1f}）')
    src_peak = peak_db(src)
    print(f'源真峰值 {src_peak:+.3f} dBFS' + ('  ⚠️ 削顶' if src_peak > -0.3 else '  ✅ 无削顶'))

    print(f'\n画面时间轴：片头 {a.head:.0f}s + 16 × {a.seg:.0f}s '
          f'= {a.head + 16 * a.seg:.0f}s，音乐余 {DUR - a.head - 16 * a.seg:.2f}s 作片尾')
    print(f'{"段":>2} {"朝代":<12} {"区间":>12} {"平均RMS":>9}  特征')
    win = sr * 5
    for i, name in enumerate(ORDER):
        s, e = a.head + i * a.seg, a.head + (i + 1) * a.seg
        x = wav[int(s * sr):int(e * sr)]
        r = 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)
        tag = '弱／留白' if r < -20 else ('强' if r > -17 else '中')
        flag = '  ⚠️ 落在音乐塌陷段' if r < -22 else ''
        print(f'{i + 1:>2} {name:<12} {s:5.0f}–{e:5.0f}s {r:8.2f}dB  {tag}{flag}')

    png = OUT / '_配乐能量与16段分界.png'
    print(f'\n能量图 → {draw_curve(wav, sr, a.head, a.seg, png)}')

    if a.curve_only:
        return

    OUT.mkdir(parents=True, exist_ok=True)
    tag = f'{int(DUR // 60)}m{round(DUR % 60):02d}s'
    out = OUT / f'宣传片01-配乐-{tag}-{a.headroom:g}dB.wav'
    make_track(src, out, a.headroom, a.fade_in, a.fade_out)
    pk = peak_db(out)
    print(f'\n音轨 → {out}  （{out.stat().st_size / 1024 / 1024:.1f} MB）')
    print(f'处理后真峰值 {pk:+.3f} dBFS  {"✅ 无削顶" if pk < -0.3 else "⚠️ 仍削顶"}')
    if a.mp3:
        mp3 = out.with_suffix('.mp3')
        subprocess.run([FF, '-y', '-v', 'error', '-i', str(out),
                        '-c:a', 'libmp3lame', '-b:a', '256k', str(mp3)], check=True)
        print(f'另存 → {mp3}  （{mp3.stat().st_size / 1024 / 1024:.1f} MB）')
    print('\n合成示例（视频拼好后）：')
    print(f'  ffmpeg -i 成片-无音轨.mp4 -i "{out.name}" -c:v copy -c:a aac -b:a 256k '
          f'-shortest 成片-{int(DUR // 60)}m{int(DUR % 60):02d}.mp4')


if __name__ == '__main__':
    main()
