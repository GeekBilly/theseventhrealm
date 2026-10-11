import json, numpy as np

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/08-音频/"
notes = json.load(open(BASE + "melody-quantized.json", encoding="utf-8"))
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
IN_KEY = {10, 0, 2, 3, 5, 7, 9}
DEG = {10: "1", 0: "2", 2: "3", 3: "4", 5: "5", 7: "6", 9: "7"}

def jianpu(q):
    d = DEG.get(q % 12, "?")
    if q % 12 not in DEG:
        near = min(DEG.keys(), key=lambda p: min(abs(q % 12 - p), 12 - abs(q % 12 - p)))
        d = DEG[near] + "?"
    o = q // 12 - 1
    return d + ("̣" if o < 5 else "˙" if o > 5 else "")

qs = [n["q"] for n in notes]
lo, hi = min(qs), max(qs)
T = max(n["t"] + n["dur"] for n in notes)
W, H = 620, 210
pad_l = 46
rowH = (H - 16) / (hi - lo + 1)

def px(t): return pad_l + t / T * (W - pad_l)
def py(q): return 8 + (hi - q) * rowH

rows = ""
for q in range(hi, lo - 1, -1):
    nm = NAMES[q % 12] + str(q // 12 - 1)
    ink = q % 12 in IN_KEY
    y = py(q) + rowH / 2
    rows += (f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W}" y2="{y:.1f}" '
             f'stroke="{"#e8e3d8" if ink else "#f2eee5"}" stroke-width="0.5"/>'
             f'<text x="{pad_l-8}" y="{y+3.5:.1f}" font-size="10" '
             f'fill="{"#5a5348" if ink else "#b0aa9c"}" text-anchor="end">{nm}</text>')

blocks = ""
for n in notes:
    x0, x1 = px(n["t"]), px(n["t"] + n["dur"])
    w = max(1.6, x1 - x0)
    ink = n["q"] % 12 in IN_KEY
    blocks += (f'<rect x="{x0:.1f}" y="{py(n["q"])+1:.1f}" width="{w:.1f}" '
               f'height="{rowH-2:.1f}" rx="1.5" fill="{"#3c3489" if ink else "#c9c2b2"}"/>')

ticks = ""
for s in range(0, int(T) + 1, 15):
    ticks += (f'<line x1="{px(s):.1f}" y1="8" x2="{px(s):.1f}" y2="{H-4}" stroke="#eae5da" stroke-width="0.5"/>'
              f'<text x="{px(s):.1f}" y="{H+12}" font-size="10" fill="#8a8578" text-anchor="middle">{s}s</text>')

lines, cur = [], []
for n in notes:
    cur.append(jianpu(n["q"]))
    if len(cur) == 8:
        lines.append(cur); cur = []
if cur: lines.append(cur)
jp = ""
for li, ln in enumerate(lines, 1):
    cells = "".join(f'<span class="n{" x" if "?" in d else ""}">{d}</span>' for d in ln)
    jp += f'<div class="bar"><span class="no">{li}</span>{cells}</div>'

dev = [n["cents2"] for n in notes]
dev = np.array(dev)
ink_n = sum(1 for n in notes if n["q"] % 12 in IN_KEY)

html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>第七境主题旋律 · 提取报告</title>
<style>
body{{margin:0;padding:40px 28px 60px;background:#f7f5f0;color:#1f1d1a;
font-family:"Songti SC","STSong",serif;line-height:1.75}}
.wrap{{max-width:760px;margin:0 auto}}
h1{{font-size:26px;font-weight:500;margin:0 0 6px}}
.sub{{color:#8a8578;font-size:13px;margin:0 0 30px;font-family:-apple-system,sans-serif}}
h2{{font-size:16px;font-weight:500;margin:36px 0 13px;padding-left:11px;border-left:3px solid #9e2b25}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin:16px 0}}
.card{{background:#fff;border:1px solid #e6e1d6;border-radius:10px;padding:13px 15px}}
.card .k{{font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif}}
.card .v{{font-size:21px;font-weight:500;margin:3px 0 0}}
.panel{{background:#fff;border:1px solid #e6e1d6;border-radius:12px;padding:18px 20px;margin:14px 0}}
svg{{display:block;width:100%}}
.legend{{font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif;margin-top:10px;display:flex;gap:18px}}
.sw{{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;margin-right:5px}}
.bar{{display:flex;align-items:center;gap:4px;padding:5px 0;border-bottom:1px solid #f2eee5;font-family:"Songti SC",serif}}
.bar .no{{width:26px;font-size:11px;color:#b0aa9c;font-family:-apple-system,sans-serif}}
.n{{min-width:30px;text-align:center;font-size:17px}}
.n.x{{color:#a8a292}}
table{{width:100%;border-collapse:collapse;font-size:13px;font-family:-apple-system,sans-serif}}
td,th{{padding:8px;border-bottom:1px solid #eee9de;text-align:left}}
th{{color:#8a8578;font-weight:500;font-size:12px}}
p.note{{font-size:13.5px;margin:0 0 12px}}
.foot{{margin-top:38px;padding-top:16px;border-top:1px solid #e6e1d6;font-size:12px;color:#8a8578;font-family:-apple-system,sans-serif}}
</style></head><body><div class="wrap">

<h1>第七境 · 主题旋律提取报告</h1>
<p class="sub">素材：口哨哼录 2 分 07 秒 · 逐帧基频追踪 + 音符切分 + 量化 · 本地处理，零积分</p>

<h2>旋律概览</h2>
<div class="grid">
<div class="card"><div class="k">音符数</div><div class="v">{len(notes)}</div></div>
<div class="card"><div class="k">调性</div><div class="v">降 B 大调</div></div>
<div class="card"><div class="k">速度</div><div class="v">72 BPM</div></div>
<div class="card"><div class="k">音域跨度</div><div class="v">{hi-lo+1} 半音</div></div>
</div>

<h2>旋律走向（钢琴卷帘）</h2>
<div class="panel">
<svg viewBox="0 0 {W} {H+22}" role="img"><title>旋律钢琴卷帘</title>
{rows}{ticks}{blocks}</svg>
<div class="legend">
<span><i class="sw" style="background:#3c3489"></i>降 B 大调调内音（{ink_n} 个）</span>
<span><i class="sw" style="background:#c9c2b2"></i>调外音／游移音（{len(notes)-ink_n} 个）</span>
</div>
</div>

<h2>简谱（1 = B♭ · 4/4 · 72 BPM）</h2>
<div class="panel">
<p class="note">高八度记 <b>5˙</b>，低八度记 <b>7̣</b>。灰色音符表示落在调外，是口哨音准游移所致。</p>
{jp}
</div>

<h2>音准体检</h2>
<div class="panel"><table>
<tr><th>项目</th><th>结果</th><th>说明</th></tr>
<tr><td>平均绝对偏差</td><td>{np.abs(dev).mean():.1f} 音分</td><td>口哨的正常水平，人耳能听出轻微不准</td></tr>
<tr><td>最大偏差</td><td>{np.abs(dev).max():.1f} 音分</td><td>接近半个半音，个别长音明显偏高</td></tr>
<tr><td>偏高音符</td><td>{(dev>15).sum()} 个</td><td>高音区普遍偏高，口哨气息越紧越容易冲</td></tr>
<tr><td>偏低音符</td><td>{(dev<-15).sum()} 个</td><td>多出现在下行乐句</td></tr>
<tr><td>调内音占比</td><td>{ink_n/len(notes)*100:.0f}%</td><td>旋律骨架清晰，主体成立</td></tr>
</table></div>

<h2>骨架分析</h2>
<div class="panel"><p class="note">
旋律围绕 <b>5（F）</b> 展开，与 <b>1（B♭）</b>、<b>4（E♭）</b> 构成骨干，
结尾落在主音 1 上并持续约 5 秒——收束明确，是一段完整的乐句而非随手哼的片段。
音域集中在 A5–A#6 这一个八度出头，符合口哨的自然音区。
</p><p class="note" style="margin:0">
调外音主要集中在 <b>2</b> 与 <b>4</b> 附近的游移（C♯／E／B／G♯），
这些基本是音准问题而非真实的半音进行——箫音版已全部校正到标准音高。
</p></div>

<h2>交付物</h2>
<div class="panel"><table>
<tr><th>文件</th><th>用途</th></tr>
<tr><td>第七境主题旋律.mid</td><td>校正音准版，可直接导入库乐队／FL Studio／任何 DAW 编曲</td></tr>
<tr><td>第七境主题旋律-未校正音准.mid</td><td>保留原始音准，用于对照听辨</td></tr>
<tr><td>第七境主题旋律-箫音版.wav / .mp3</td><td>按提取音符合成的箫音色演奏，可作为 BGM 直接使用</td></tr>
<tr><td>melody-quantized.json</td><td>音符原始数据（时间／时值／音高／音分）</td></tr>
</table></div>

<p class="foot">提取耗时约 90 秒 · AI 积分消耗 0 · 版权：旋律由你口哨创作，100% 自有<br>
算法：4096 点 FFT + 抛物线插值测基频 → 中值滤波 → 音符切分 → 半音量化 → 简谱与 MIDI 生成</p>

</div></body></html>"""

open(BASE + "旋律报告.html", "w", encoding="utf-8").write(html)
print("报告已生成:", len(html), "bytes")
print(f"音符 {len(notes)} | 调内 {ink_n} | 音域 {NAMES[lo%12]}{lo//12-1}-{NAMES[hi%12]}{hi//12-1}")
