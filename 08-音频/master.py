import subprocess, numpy as np
from scipy.signal import butter, sosfiltfilt

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
SRC = BASE + "第七境主题背景音乐-原始.m4a"
sr = 48000

def decode(path, srate=sr):
    p = subprocess.run([FF, "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(srate), "-"],
                       capture_output=True)
    return np.frombuffer(p.stdout, dtype=np.float32).astype(np.float64)

def encode_f32(x, srate, out, extra=None):
    cmd = [FF, "-f", "f32le", "-ac", "1", "-ar", str(srate), "-i", "-"]
    cmd += (extra or []) + [out, "-y"]
    subprocess.run(cmd, input=x.astype(np.float32).tobytes(), capture_output=True)

def peaking(x, sr, f0, gain_db, Q):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2 * Q)
    b0 = 1 + alpha * A; b1 = -2 * np.cos(w0); b2 = 1 - alpha * A
    a0 = 1 + alpha / A; a1 = -2 * np.cos(w0); a2 = 1 - alpha / A
    b = np.array([b0, b1, b2]) / a0
    a = np.array([a0, a1, a2]) / a0
    return sosfiltfilt(np.array([[b[0], b[1], b[2], 1.0, a[1], a[2]]]), x)

def highshelf(x, sr, f0, gain_db):
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * f0 / sr
    alpha = np.sin(w0) / 2 * np.sqrt(2)
    cw = np.cos(w0); sq = 2 * np.sqrt(A) * alpha
    b0 = A * ((A + 1) + (A - 1) * cw + sq)
    b1 = -2 * A * ((A - 1) + (A + 1) * cw)
    b2 = A * ((A + 1) + (A - 1) * cw - sq)
    a0 = (A + 1) - (A - 1) * cw + sq
    a1 = 2 * ((A - 1) - (A + 1) * cw)
    a2 = (A + 1) - (A - 1) * cw - sq
    b = np.array([b0, b1, b2]) / a0
    a = np.array([a0, a1, a2]) / a0
    return sosfiltfilt(np.array([[b[0], b[1], b[2], 1.0, a[1], a[2]]]), x)

def hp(x, sr, f0, order=2):
    sos = butter(order, f0 / (sr / 2), btype="high", output="sos")
    return sosfiltfilt(sos, x)

print("1/7 解码原始音频 ...")
x = decode(SRC)
print(f"    原始 {len(x)/sr:.2f}s")

print("2/7 裁剪尾部静音 (127.2s 之后) ...")
x = x[: int(127.2 * sr)]

print("3/7 重建泛音：软饱和谐波激励 ...")
drive = 1.9
sat = np.tanh(x * drive) / np.tanh(drive)
harm = sat - x
harm = hp(harm, sr, 1000)
harm = hp(harm, sr, 1000)
x = x + harm * 0.85
print(f"    谐波增益 RMS: {20*np.log10(np.sqrt(np.mean(harm**2))+1e-12):.1f} dB")

print("4/7 均衡：削 1.4k 共振峰 / 补低频厚度 / 提升空气感 ...")
x = peaking(x, sr, 1400, -5.0, 1.3)
x = peaking(x, sr, 260, 3.5, 0.8)
x = peaking(x, sr, 700, 2.0, 1.0)
x = highshelf(x, sr, 3000, 7.5)
x = highshelf(x, sr, 8000, 5.0)

print("5/7 淡入淡出 ...")
n = len(x)
fi, fo = int(1.5 * sr), int(3.0 * sr)
x[:fi] *= np.linspace(0, 1, fi)
x[-fo:] *= np.linspace(1, 0, fo)

print("6/7 压缩 + 响度归一化到 -16 LUFS (BGM 标准) ...")
af = ("acompressor=threshold=-20dB:ratio=3:attack=25:release=300:makeup=2,"
      "loudnorm=I=-16:TP=-1.5:LRA=9:linear=true,alimiter=limit=0.97")
encode_f32(x, sr, BASE + "第七境主题背景音乐-修复版.wav",
           ["-af", af, "-c:a", "pcm_s24le", "-ar", "48000"])

print("7/7 导出 MP3 320k / AAC 256k ...")
subprocess.run([FF, "-i", BASE + "第七境主题背景音乐-修复版.wav",
                "-c:a", "libmp3lame", "-b:a", "320k", "-ar", "44100",
                BASE + "第七境主题背景音乐-修复版.mp3", "-y"], capture_output=True)
subprocess.run([FF, "-i", BASE + "第七境主题背景音乐-修复版.wav",
                "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                BASE + "第七境主题背景音乐-修复版.m4a", "-y"], capture_output=True)

print("完成 -> 修复版.wav / .mp3 / .m4a")
