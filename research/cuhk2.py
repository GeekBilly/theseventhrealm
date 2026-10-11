import re, html, time, urllib.parse, subprocess, json
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"
CHARS=['趙','錢','孫','李','周','吳','鄭','王','馮','陳','張','劉','楊','黃','林']
def fetch(ch):
    url="https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/search.php?word="+urllib.parse.quote(ch)
    return subprocess.run(["curl","-s","--max-time","45","-H",f"User-Agent: {UA}",url],capture_output=True).stdout.decode('utf-8','ignore')
def counts(raw):
    """Split page into <th>LABEL</th> sections, take first 字例 n/m after each."""
    out={}
    # only the char_anc_table blocks
    for m in re.finditer(r'<th[^>]*>\s*(小篆|金文|甲骨|簡帛文字|其他|甲骨文)\s*</th>(.*?)(?=<th[^>]*>|</table>\s*</div>\s*</div>|$)', raw, re.S):
        lbl=m.group(1); body=m.group(2)
        cm=re.search(r'字例[:：]\s*<[^>]*>\s*[:：]?\s*</font>\s*(\d+)\s*/\s*(\d+)', body)
        if not cm:
            cm=re.search(r'字例[:：][^0-9]{0,40}?(\d+)\s*/\s*(\d+)', body, re.S)
        if cm: out[lbl]=(int(cm.group(1)),int(cm.group(2)))
        else: out[lbl]=None
    return out
res={}
for ch in CHARS:
    raw=fetch(ch); c=counts(raw); res[ch]=c
    print(ch, json.dumps(c,ensure_ascii=False), flush=True)
    time.sleep(1.0)
json.dump(res,open('cuhk_counts.json','w'),ensure_ascii=False,indent=1)
