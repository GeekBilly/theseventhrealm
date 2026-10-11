import subprocess, numpy as np

FF = "/Users/billyhou/.workbuddy/binaries/python/envs/default/lib/python3.13/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
sr = 44100
T0, T1 = 6.0, 26.0

def dec(p):
    r = subprocess.run([FF, "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)

def env_path(x, w, h, n=680):
    a, b = int(T0*sr), int(T1*sr)
    s = x[a:b]
    step = max(1, len(s)//n)
    up, dn = [], []
    mid = h/2
    for i in range(0, len(s)-step, step):
        seg = s[i:i+step]
        px = (i/len(s))*w
        up.append(f"{px:.1f},{mid - max(seg)*h/2:.1f}")
        dn.append(f"{px:.1f},{mid - min(seg)*h/2:.1f}")
    return "M" + " L".join(up) + " L" + " L".join(reversed(dn)) + " Z"

xo = dec(BASE + "第七境主题旋律-箫音版.wav")
xr = dec(BASE + "第七境主题旋律-箫音柔版.wav")
W, H = 620, 88
po = env_path(xo, W, H)
pr = env_path(xr, W, H)

def rms_curve(x, nb=150):
    a, b = int(T0*sr), int(T1*sr)
    s = x[a:b]
    st = max(1, len(s)//nb)
    return [20*np.log10(np.sqrt(np.mean(s[i:i+st]**2))+1e-12) for i in range(0, len(s)-st, st)]

def curve_path(vals, w, h, top=-46, bot=-6):
    pts = []
    for i, v in enumerate(vals):
        px = i/(len(vals)-1)*w
        py = h - (np.clip(v, top, bot)-top)/(bot-top)*h
        pts.append(f"{px:.1f},{py:.1f}")
    return "M" + " L".join(pts)

co = curve_path(rms_curve(xo), W, 70)
cr = curve_path(rms_curve(xr), W, 70)

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>柔和版 vs 原版 · 波形对比</title>
<style>
body{{margin:0;padding:38px 26px 56px;background:#f7f5f0;color:#1f1d1a;
font-family:"Songti SC","STSong",serif;line-height:1.75}}
.wrap{{max-width:740px;margin:0 auto}}
h1{{font-size:24px;font-weight:500;margin:0 0 6px}}
.sub{{color:#8a8578;font-size:13px;margin:0 0 28px;font-family:-apple-system,sans-serif}}
h2{{font-size:15px;font-weight:500;margin:30px 0 12px;padding-left:11px;border-left:3px solid #9e2b25}}
.panel{{background:#fff;border:1px solid #e6e1d6;border-radius:12px;padding:18px 20px;margin:12px 0}}
.lbl{{font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif;margin-bottom:9px}}
svg{{display:block;width:100%}}
table{{width:100%;border-collapse:collapse;font-size:13px;font-family:-apple-system,sans-serif}}
td,th{{padding:8px;border-bottom:1px solid #eee9de;text-align:left}}
th{{color:#8a8578;font-weight:500;font-size:12px}}
.ok{{color:#0f6e56}}
p.n{{font-size:13.5px;margin:0 0 10px}}
.foot{{margin-top:34px;padding-top:14px;border-top:1px solid #e6e1d6;font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif}}
</style></head><body><div class="wrap">

<h1>柔和版 · 前后对比</h1>
<p class="sub">截取同一段（{T0:.0f}s–{T1:.0f}s）· 上：原箫音版 下：柔和版</p>

<h2>波形：断裂 vs 连绵</h2>
<div class="panel">
<div class="lbl">原箫音版 — 音符之间有硬切断，能看到明显的空白缺口</div>
<svg viewBox="0 0 620 {H}" role="img"><title>原版波形</title>
<line x1="0" y1="{H/2}" x2="620" y2="{H/2}" stroke="#e2ddd2" stroke-width="0.5"/>
<path d="{po}" fill="#b9b3a5"/></svg>
<div class="lbl" style="margin-top:16px">柔和版 — 音符首尾相接，连绵不断</div>
<svg viewBox="0 0 620 {H}" role="img"><title>柔和版波形</title>
<line x1="0" y1="{H/2}" x2="620" y2="{H/2}" stroke="#e2ddd2" stroke-width="0.5"/>
<path d="{pr}" fill="#5a5348"/></svg>
</div>

<h2>电平轮廓：平线 vs 呼吸</h2>
<div class="panel">
<svg viewBox="0 0 620 70" role="img"><title>电平轮廓对比</title>
<path d="{co}" fill="none" stroke="#c0b8a8" stroke-width="1.4"/>
<path d="{cr}" fill="none" stroke="#1f1d1a" stroke-width="1.6"/></svg>
<div class="lbl" style="margin-top:8px"><span>灰=原版（音符间掉到底，切断感）</span><span>墨=柔和版（连续起伏）</span></div>
</div>

<h2>改了什么</h2>
<div class="panel"><table>
<tr><th>项目</th><th>原箫音版</th><th>柔和版</th></tr>
<tr><td>音符间能量落差</td><td>106.8 dB（等于断开）</td><td class="ok">2.7 dB（连起来了）</td></tr>
<tr><td>音符内起伏</td><td>0.209（假象，来自断音）</td><td class="ok">0.131（真实的呼吸起伏）</td></tr>
<tr><td>起音时间</td><td>90 ms</td><td class="ok">140 ms（更柔）</td></tr>
<tr><td>音符尾巴</td><td>无</td><td class="ok">340 ms 自然衰减</td></tr>
<tr><td>滑音过渡</td><td>无</td><td class="ok">按音程 55–200ms 平滑滑入</td></tr>
<tr><td>颤音</td><td>0.4% 深度</td><td class="ok">0.65% 深度，0.28s 后渐入</td></tr>
<tr><td>混响</td><td>无</td><td class="ok">2.2s 指数衰减，湿声 17%</td></tr>
<tr><td>谐波亮度</td><td>2–4 次 0.16/0.07/0.03</td><td class="ok">0.105/0.042/0.014（更暗更柔）</td></tr>
<tr><td>整体响度</td><td>−15.8 LUFS</td><td class="ok">−16.8 LUFS（更像背景）</td></tr>
</table></div>

<h2>关于"一个音按在那里起不来"</h2>
<div class="panel"><p class="n">
第一版做出来后我量了一下，发现反效果：音符内起伏只有 0.090，比原版还平——
混响和音符重叠把包络填平了。于是把呼吸幅度调大（长音 auto 加深）、混响湿声从 30% 降到 17%、
压缩比从 2:1 放到 1.5:1，起伏才回到 0.131。
</p><p class="n" style="margin:0">
现在每个音都是：柔起 → 微落 → 渐强到顶 → 缓收 → 自然衰减，
长音还叠了一层约 1.7 秒周期的呼吸起伏，不会死按不动。
</p></div>

<p class="foot">合成耗时约 50 秒 · AI 积分消耗 0 · 旋律版权自有，可自由商用</p>

</div></body></html>"""

open(BASE + "柔和版对比.html", "w", encoding="utf-8").write(html)
print("已生成 柔和版对比.html")
