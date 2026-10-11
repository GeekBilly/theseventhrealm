import re, html, time, urllib.parse, subprocess, json, sys

CHARS = ['趙','錢','孫','李','周','吳','鄭','王','馮','陳','張','劉','楊','黃','林']
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

def fetch(ch):
    url = "https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word=" + urllib.parse.quote(ch)
    r = subprocess.run(["curl","-s","--max-time","40","-H",f"User-Agent: {UA}",url],capture_output=True)
    return r.stdout.decode('utf-8',errors='ignore')

def analyse(ch, raw):
    t = re.sub(r'<script.*?</script>','',raw,flags=re.S)
    t = re.sub(r'<style.*?</style>','',t,flags=re.S)
    txt = html.unescape(re.sub(r'<[^>]+>',' ',t))
    txt = re.sub(r'\s+',' ',txt)
    out = {}
    # counts like "字例: 1/2"
    for label, key in [('甲骨','jiagu'),('金文','jinwen'),('小篆','xiaozhuan'),('簡帛文字','jianbo')]:
        # find label then nearest 字例: n/m within 120 chars
        for m in re.finditer(re.escape(label), txt):
            seg = txt[m.start():m.start()+160]
            mm = re.search(r'字例[:：]\s*(\d+)\s*/\s*(\d+)', seg)
            if mm:
                out[key] = f"{mm.group(1)}/{mm.group(2)}"
                break
        out.setdefault(key, None)
    # does the page even resolve to this char?
    out['resolved'] = ch in txt
    return out

res={}
for ch in CHARS:
    raw = fetch(ch)
    a = analyse(ch, raw)
    a['bytes']=len(raw)
    res[ch]=a
    print(ch, json.dumps(a, ensure_ascii=False), flush=True)
    time.sleep(1.2)
json.dump(res, open('cuhk_coverage.json','w'), ensure_ascii=False, indent=1)
