# -*- coding: utf-8 -*-
"""金句线 · 手机竖版 DOM 校验：金句不能压到落款/品牌、不能溢出视口。
用法：python3 verify-phone.py song juexing tang ming"""
import subprocess, os, sys

BASE = '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/05-承接站/样张'
env = dict(os.environ)
env["PATH"] = "/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:" + env["PATH"]
AB = "/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser"


def run(a, t=40):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception:
        return "TIMEOUT"


JS = """
(()=>{const R=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();
 return {t:Math.round(r.top),b:Math.round(r.bottom),l:Math.round(r.left),r:Math.round(r.right),
 w:Math.round(r.width),h:Math.round(r.height)};};
const q=R('.quote'),co=R('.colophon'),br=R('.brand'),he=R('.hero'),se=R('.series');
const ov=(a,b)=>a&&b&&a.t<b.b&&b.t<a.b;
const out=[];[['quote',q],['colophon',co],['brand',br],['hero',he],['series',se]]
  .forEach(([n,x])=>{if(!x){out.push(n+':missing');return;}
   if(x.t<0||x.b>innerHeight||x.l<0||x.r>innerWidth) out.push(n+':overflow');});
return JSON.stringify({vp:[innerWidth,innerHeight],quote:q,colophonTop:co?co.t:null,
 brandTop:br?br.t:null,gap_quote_colophon:(q&&co)?co.t-q.b:null,
 ov_quote_colophon:ov(q,co),ov_quote_brand:ov(q,br),ov_hero_quote:ov(he,q),
 out:out});})()
"""

slugs = sys.argv[1:] or ['shang']
for s in slugs:
    for tag, vp in [('iphone', ('1179', '2556')), ('android', ('1080', '2400'))]:
        f = f'{BASE}/{s}-phone-{tag}.html'
        if not os.path.exists(f):
            print(s, tag, 'MISSING'); continue
        run(['set', 'viewport', vp[0], vp[1]])
        run(['open', f'file://{f}'])
        run(['wait', '1800'])
        res = run(['eval', JS])
        print(f'{s:9s} {tag:8s} {res}')
run(['close'])
