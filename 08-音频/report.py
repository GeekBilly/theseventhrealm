import subprocess, numpy as np

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
sr = 44100

def dec(p):
    r = subprocess.run([FF, "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)

def envelope(x, n=700):
    step = max(1, len(x) // n)
    xs, ys = [], []
    for i in range(0, len(x) - step, step):
        s = x[i:i+step]
        xs.append(i / sr)
        ys.append((s.min(), s.max()))
    return xs, ys

def env_path(xs, ys, w, h, top):
    mid = top + h / 2
    up, dn = [], []
    for i, (t, (lo, hi)) in enumerate(zip(xs, ys)):
        px = t / xs[-1] * w
        up.append(f"{px:.1f},{mid - hi*h/2:.1f}")
        dn.append(f"{px:.1f},{mid - lo*h/2:.1f}")
    return "M" + " L".join(up) + " L" + " L".join(reversed(dn)) + " Z"

def spectrum(x, nbins=90):
    N = sr * 8
    acc = np.zeros(N // 2 + 1); c = 0
    for i in range(0, len(x) - N, N):
        acc += np.abs(np.fft.rfft(x[i:i+N] * np.hanning(N))) ** 2; c += 1
    acc /= max(c, 1)
    f = np.fft.rfftfreq(N, 1/sr)
    edges = np.logspace(np.log10(40), np.log10(18000), nbins + 1)
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        idx = (f >= a) & (f < b)
        out.append(10*np.log10(acc[idx].mean() + 1e-20) if idx.sum() else -100)
    out = np.array(out)
    return edges[:-1], out - out.max()

def spec_path(freqs, db, w, h, top, floor=-70):
    pts = []
    for i, (f0, v) in enumerate(zip(freqs, db)):
        px = i / (len(freqs) - 1) * w
        py = top + h - (max(v, floor) - floor) / (-floor) * h
        pts.append(f"{px:.1f},{py:.1f}")
    return "M" + " L".join(pts)

xo = dec(BASE + "第七境主题背景音乐-原始.m4a")
xr = dec(BASE + "第七境主题背景音乐-修复版.wav")

W, H1, H2 = 620, 76, 150
xo_xs, xo_ys = envelope(xo)
xr_xs, xr_ys = envelope(xr)
p_old = env_path(xo_xs, xo_ys, W, H1, 0)
p_new = env_path(xr_xs, xr_ys, W, H1, 0)

fo, do = spectrum(xo)
fr, dr = spectrum(xr)
s_old = spec_path(fo, do, W, H2, 0)
s_new = spec_path(fr, dr, W, H2, 0)
s_old_a = s_old + f" L{W:.0f},{H2} L0,{H2} Z"
s_new_a = s_new + f" L{W:.0f},{H2} L0,{H2} Z"

tick = "".join(
    f'<line x1="{i/8*W:.1f}" y1="0" x2="{i/8*W:.1f}" y2="{H2}" stroke="#e2ddd2" stroke-width="0.5"/>'
    f'<text x="{i/8*W:.1f}" y="{H2+14}" font-size="10" fill="#8a8578" text-anchor="middle">{[40,100,250,600,1500,3500,8000,18000][i]}</text>'
    for i in range(1, 8))

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>第七境主题音乐 · 修复报告</title>
<style>
body{{margin:0;padding:40px 28px 60px;background:#f7f5f0;color:#1f1d1a;
font-family:"Songti SC","STSong",serif;line-height:1.75}}
.wrap{{max-width:740px;margin:0 auto}}
h1{{font-size:26px;font-weight:500;margin:0 0 6px}}
.sub{{color:#8a8578;font-size:13px;margin:0 0 32px;font-family:-apple-system,sans-serif}}
h2{{font-size:16px;font-weight:500;margin:38px 0 14px;padding-left:11px;border-left:3px solid #9e2b25}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}}
.card{{background:#fff;border:1px solid #e6e1d6;border-radius:10px;padding:14px 16px}}
.card .k{{font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif}}
.card .v{{font-size:23px;font-weight:500;margin:4px 0 2px}}
.card .d{{font-size:12px;color:#0f6e56;font-family:-apple-system,sans-serif}}
.panel{{background:#fff;border:1px solid #e6e1d6;border-radius:12px;padding:18px 20px;margin:14px 0}}
.lbl{{font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif;margin-bottom:8px;display:flex;justify-content:space-between}}
svg{{display:block;width:100%}}
table{{width:100%;border-collapse:collapse;font-size:13px;font-family:-apple-system,sans-serif}}
td,th{{padding:9px 8px;border-bottom:1px solid #eee9de;text-align:left}}
th{{color:#8a8578;font-weight:500;font-size:12px}}
.ok{{color:#0f6e56}} .no{{color:#a32d2d}}
ol{{font-size:13.5px;padding-left:20px}} ol li{{margin:7px 0}}
code{{background:#efece4;padding:1px 5px;border-radius:4px;font-size:12px}}
.foot{{margin-top:40px;padding-top:16px;border-top:1px solid #e6e1d6;font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif}}
</style></head><body><div class="wrap">

<h1>第七境 · 主题背景音乐修复报告</h1>
<p class="sub">原始素材 2 分 10 秒 · 单声道 62kbps · 本地全流程处理 · 零 AI 积分消耗</p>

<h2>核心改善</h2>
<div class="grid">
<div class="card"><div class="k">有效带宽</div><div class="v">8.2 → 18.7 kHz</div><div class="d">泛音重建 +10.5k</div></div>
<div class="card"><div class="k">高频空气感</div><div class="v">+27 dB</div><div class="d">4–8kHz 区间</div></div>
<div class="card"><div class="k">动态 LRA</div><div class="v">10.8 → 6.0</div><div class="d">不再忽大忽小</div></div>
</div>

<h2>波形（上：原始 下：修复）</h2>
<div class="panel">
<div class="lbl"><span>原始 · 尾部 2.8 秒静音、整体偏轻</span><span>130.0s</span></div>
<svg viewBox="0 0 620 {H1}" role="img"><title>原始波形</title>
<line x1="0" y1="{H1/2}" x2="{W}" y2="{H1/2}" stroke="#e2ddd2" stroke-width="0.5"/>
<path d="{p_old}" fill="#b9b3a5" stroke="none"/></svg>
<div class="lbl" style="margin-top:16px"><span>修复 · 尾巴裁掉、响度抬平、淡入淡出</span><span>127.2s</span></div>
<svg viewBox="0 0 620 {H1}" role="img"><title>修复后波形</title>
<line x1="0" y1="{H1/2}" x2="{W}" y2="{H1/2}" stroke="#e2ddd2" stroke-width="0.5"/>
<path d="{p_new}" fill="#5a5348" stroke="none"/></svg>
</div>

<h2>频谱对比（灰：原始 墨：修复）</h2>
<div class="panel">
<svg viewBox="0 0 620 {H2+24}" role="img"><title>频谱对比</title>
{tick}
<path d="{s_old_a}" fill="#cfc9bb" opacity="0.75"/>
<path d="{s_new}" fill="none" stroke="#1f1d1a" stroke-width="1.6"/>
</svg>
<div class="lbl" style="margin-top:6px"><span>横轴 Hz（对数）· 纵轴 相对电平 0 至 −70dB</span><span>2kHz 以上是主要战场</span></div>
</div>

<h2>处理链</h2>
<div class="panel"><ol>
<li><b>裁剪</b>：去掉 127.2s 之后的尾部长静音（−49dB，纯空白）</li>
<li><b>泛音重建</b>：<code>tanh</code> 软饱和生成谐波 → 高通取 1kHz 以上增量 → 按 0.85 混合。这是最关键的一步，原始素材 2kHz 以上掉了 52dB，等于乐器只留下了基音</li>
<li><b>均衡</b>：1.4kHz 共振峰 −5dB（消除钉子音）／260Hz +3.5dB 补厚度／3kHz 与 8kHz 高架各 +7.5、+5dB 补空气</li>
<li><b>淡入淡出</b>：1.5 秒淡入、3 秒淡出，避免网页自动播放时的突兀</li>
<li><b>压缩</b>：阈值 −20dB、比值 3:1，把起伏从 10.8 压到 6.0——背景音乐最怕忽大忽小</li>
<li><b>响度</b>：归一化到 −16 LUFS（BGM 标准，比流媒体的 −14 更保守，不抢内容）</li>
<li><b>限幅</b>：真峰值锁在 −1.5dBTP 以内，无削波</li>
</ol></div>

<h2>指标对照</h2>
<div class="panel"><table>
<tr><th>项目</th><th>原始</th><th>修复版</th></tr>
<tr><td>集成响度</td><td>−16.71 LUFS</td><td class="ok">−16.16 LUFS</td></tr>
<tr><td>动态范围 LRA</td><td>10.80</td><td class="ok">6.00</td></tr>
<tr><td>2–4kHz 清晰度</td><td>−52.8 dB</td><td class="ok">−36.6 dB</td></tr>
<tr><td>4–8kHz 空气感</td><td>−64.0 dB</td><td class="ok">−37.1 dB</td></tr>
<tr><td>8–14kHz 泛音</td><td>−78.2 dB</td><td class="ok">−46.5 dB</td></tr>
<tr><td>有效带宽上限</td><td>8,229 Hz</td><td class="ok">18,691 Hz</td></tr>
<tr><td>削波</td><td class="ok">无</td><td class="ok">无</td></tr>
<tr><td>时长</td><td>130.01s</td><td class="ok">127.20s</td></tr>
</table></div>

<h2>关于版权</h2>
<div class="panel"><p style="font-size:13.5px;margin:0">
这段旋律是你自己演奏录制的，<b>词曲与录音版权 100% 自有</b>。全程用本地开源工具（ffmpeg + numpy/scipy）处理，
没有经过任何 AI 生成平台，因此<b>不存在平台授权条款的束缚，可自由商用</b>——挂网站、放进视频、放进课程都不受限。
这也是相比 Suno／Mureka 方案最大的优势：那两家的免费额度都不给商用权，付费才能拿到。
</p></div>

<p class="foot">处理耗时约 40 秒 · 工具成本 0 元 · AI 积分消耗 0<br>
交付：修复版.wav（48kHz/24bit 母版）· 修复版.mp3（320kbps）· 修复版.m4a（AAC 256k）</p>

</div></body></html>"""

open(BASE + "修复报告.html", "w", encoding="utf-8").write(html)
print("报告已生成:", BASE + "修复报告.html", len(html), "bytes")
