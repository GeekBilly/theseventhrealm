#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第七境 · 写作工作台核心（纯本地，不上线、不联网）

日常写入方式（2026-11-20 起）：浏览器直写。双击 写作工作台.html →
点「连接工作目录」授权 01-内容 → 保存/同步全库都由浏览器 File System Access
API 直接写磁盘。**不需要任何常驻服务**。

子命令（仍需 python3 执行，仅重建/兼容用）：
  init              首次从现有 HTML 剥离出模板，并重建一次
  rebuild           按模板 + 全部 md 重建 写作工作台.html 的内嵌快照（改模板后必用）
  serve --port 8899 兼容旧 API 服务（默认不再需要；仅当浏览器直写不可用时备用）

安全：rebuild 只写 BASE 下的 写作工作台.html；浏览器直写经用户显式授权目录。
"""
import os, sys, json, re, html, argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

BASE = "/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/01-内容"
HTML_PATH = os.path.join(BASE, "写作工作台.html")
TPL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "写作工作台.template.html")
BASE_REAL = os.path.realpath(BASE)

# ---------------- Markdown 渲染（与页内阅读器一致） ----------------
def esc(s):
    return html.escape(s, quote=False)

def inline(s):
    s = esc(s)
    s = re.sub(r'`([^`]+)`', lambda m: '<code>' + m.group(1) + '</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', lambda m: '<strong>' + m.group(1) + '</strong>', s)
    def link(m):
        text, url = m.group(1), m.group(2)
        if re.search(r'\.md($|\?|#)', url):
            return '<a class="doclink" href="' + html.escape(url, quote=True) + '">' + text + '</a>'
        return '<a href="' + html.escape(url, quote=True) + '" target="_blank" rel="noopener">' + text + '</a>'
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, s)
    return s

def render(md):
    lines = md.split('\n')
    out = []
    i, n = 0, len(lines)
    special = re.compile(r'^(#{1,6}\s|\||>|```|\s*[-*]\s|\s*\d+\.\s)')
    while i < n:
        line = lines[i]; st = line.strip()
        if st.startswith('```'):
            i += 1; buf = []
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(esc(lines[i])); i += 1
            i += 1
            out.append('<pre>' + '\n'.join(buf) + '</pre>'); continue
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', st):
            out.append('<hr>'); i += 1; continue
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            lvl = len(m.group(1))
            out.append('<h%d>%s</h%d>' % (lvl, inline(m.group(2)), lvl)); i += 1; continue
        if st.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(inline(lines[i].strip().lstrip('>').strip())); i += 1
            out.append('<blockquote>' + '<br>'.join(buf) + '</blockquote>'); continue
        if st.startswith('|') and i + 1 < n and re.match(r'^\|?[\s:\-|]+\|?$', lines[i+1].strip()) and '-' in lines[i+1]:
            header = [c.strip() for c in st.strip('|').split('|')]
            i += 2; rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
            th = ''.join('<th>' + inline(c) + '</th>' for c in header)
            trs = ''.join('<tr>' + ''.join('<td>' + inline(c) + '</td>' for c in r) + '</tr>' for r in rows)
            out.append('<table><thead><tr>' + th + '</tr></thead><tbody>' + trs + '</tbody></table>'); continue
        if re.match(r'^\s*[-*]\s+', line):
            items = []
            while i < n and re.match(r'^\s*[-*]\s+', lines[i]):
                items.append(inline(re.sub(r'^\s*[-*]\s+', '', lines[i]))); i += 1
            out.append('<ul>' + ''.join('<li>' + x + '</li>' for x in items) + '</ul>'); continue
        if re.match(r'^\s*\d+\.\s+', line):
            items = []
            while i < n and re.match(r'^\s*\d+\.\s+', lines[i]):
                items.append(inline(re.sub(r'^\s*\d+\.\s+', '', lines[i]))); i += 1
            out.append('<ol>' + ''.join('<li>' + x + '</li>' for x in items) + '</ol>'); continue
        if st == '':
            i += 1; continue
        buf = [inline(line)]; i += 1
        while i < n and lines[i].strip() and not special.match(lines[i]) and not re.match(r'^(-{3,}|\*{3,}|_{3,})$', lines[i].strip()):
            buf.append(inline(lines[i])); i += 1
        out.append('<p>' + '<br>'.join(buf) + '</p>')
    return '\n'.join(out)

def collect_docs():
    docs = {}
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, BASE).replace(os.sep, '/')
                try:
                    with open(full, encoding='utf-8') as fh:
                        docs[rel] = fh.read()
                except Exception as e:
                    print('SKIP', rel, e, file=sys.stderr)
    return docs

def safe_path(key):
    if not key or not key.endswith('.md') or '\x00' in key:
        return None
    full = os.path.realpath(os.path.join(BASE, key))
    if not full.startswith(BASE_REAL + os.sep):
        return None
    return full

# ---------------- 阅读器 CSS / DOM / JS（重建时注入） ----------------
READER_CSS = r'''
/* ===== 文档视图页（点击进入 · 非弹窗） ===== */
#docview{display:none;min-height:100vh}
body.in-doc .masthead,body.in-doc #svcbar,
body.in-doc .tabbar,body.in-doc .wrap,body.in-doc footer{display:none!important}
body.in-doc #docview{display:block}
.dvbar{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:10px;
  padding:10px 26px;border-bottom:1px solid var(--hair);background:rgba(255,255,255,.94);
  -webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);flex-wrap:wrap}
.dvback{font-size:14px;color:var(--cinnabar);border-bottom:1px solid rgba(176,56,38,.4)}
.dvpath{font-size:14px;color:var(--ink2);font-family:ui-monospace,Menlo,monospace;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:38%}
.dvspacer{flex:1}
.rbtn{font-size:14px;color:var(--ink2);border:1px solid var(--hair);border-radius:2px;background:var(--white);padding:5px 11px;cursor:pointer;font-family:var(--f)}
.rbtn:hover{color:var(--cinnabar);border-color:var(--cinnabar)}
.rbtn.act{color:#fff;background:var(--cinnabar);border-color:var(--cinnabar)}
.rraw{font-size:14px;color:var(--ink2);border-bottom:1px solid var(--hair)}
.dvbody{padding:32px 34px 70px;text-align:left;font-size:16px;line-height:1.85;color:var(--ink)}
.dvbody h1,.dvbody h2,.dvbody h3,.dvbody h4{font-weight:600;letter-spacing:2px;margin:22px 0 9px;line-height:1.4}
.dvbody h1,.dvbody h2{font-size:18px;border-bottom:1px solid var(--hair);padding-bottom:5px}
.dvbody h3,.dvbody h4{font-size:16px}
.dvbody p{margin:8px 0} .dvbody ul,.dvbody ol{margin:8px 0 8px 22px}
.dvbody li{margin:4px 0} .dvbody strong{font-weight:600;color:var(--ink)}
.dvbody code{font-family:ui-monospace,Menlo,monospace;background:var(--ghost);padding:1px 5px;border-radius:2px;font-size:14px;color:var(--cinnabar)}
.dvbody pre{background:var(--ghost);border:1px solid var(--hair);border-radius:3px;padding:12px 14px;overflow:auto;margin:12px 0;font-size:14px;line-height:1.6}
.dvbody pre code{background:none;color:var(--ink);padding:0}
.dvbody blockquote{border-left:2px solid var(--cinnabar);background:var(--ghost);padding:8px 14px;margin:12px 0;color:var(--ink2)}
.dvbody table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
.dvbody th,.dvbody td{border:1px solid var(--hair);padding:7px 10px;text-align:left;vertical-align:top}
.dvbody th{background:var(--ghost);font-weight:600}
.dvbody hr{border:0;border-top:1px solid var(--hair);margin:20px 0}
.dvbody a{color:var(--cinnabar);border-bottom:1px solid rgba(176,56,38,.4);cursor:pointer}
.dvbody textarea{width:100%;min-height:60vh;resize:vertical;border:1px solid var(--hair);border-radius:3px;padding:16px 18px;
  font-family:var(--f);font-size:16px;line-height:1.8;color:var(--ink);background:#fff;outline:none}
.dvbody textarea:focus{border-color:var(--cinnabar)}
#reader .editnote{font-size:14px;color:var(--cinnabar);margin-bottom:10px}
/* —— 文档页统一「总22-分18-细节16」操作台外壳，装饰与主界面同一套 —— */
.dvwrap{max-width:880px;margin:18px auto;text-align:left;background:var(--white);
  border:1px solid var(--hair2);border-radius:var(--r);box-shadow:0 1px 5px rgba(26,26,24,.05);
  padding:26px 30px 32px}
.dvloc{font-size:14px;color:var(--ink2);margin:0 0 4px}
.dvloc .tag{color:var(--cinnabar);font-weight:600;margin-right:8px}
.dvhead{font-size:22px;font-weight:600;letter-spacing:4px;
  padding-bottom:10px;border-bottom:2px solid var(--cinnabar);margin-bottom:10px}
.dvlead{font-size:14px;color:var(--ink2);line-height:1.8;margin-bottom:8px}
.dvtoc{margin:16px 0 20px;border:1px solid var(--hair);border-radius:var(--r);overflow:hidden;background:var(--white)}
.dvtoc .cap{font-size:18px;font-weight:600;color:var(--ink);
  display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;
  background:var(--ghost);border-bottom:1px solid var(--hair);padding:10px 16px;margin:0}
.dvtoc .cap em{font-style:normal;font-size:14px;font-weight:400;color:var(--ink2)}
.dvtoc ol{list-style:none;padding:8px 16px 12px;margin:0}
.dvtoc li{font-size:16px;padding:7px 0;border-bottom:1px solid var(--hair);
  display:flex;gap:9px;align-items:baseline;cursor:pointer}
.dvtoc li:last-child{border-bottom:0}
.dvtoc li:hover{color:var(--cinnabar)}
.dvtoc li .n{color:var(--cinnabar);font-size:14px;flex:none;min-width:22px}
.dvtoc li.sub{padding-left:22px;font-size:14px;color:var(--ink2)}
.dvtoc li.sub:hover{color:var(--cinnabar)}
.dvsec{margin:12px 0;border:1px solid var(--hair);border-radius:var(--r);background:var(--white);overflow:hidden}
.dvsec[open]{border-color:rgba(176,56,38,.35)}
.dvsec>summary{cursor:pointer;list-style:none;padding:12px 16px 12px 14px;font-size:18px;font-weight:600;
  letter-spacing:1px;display:flex;align-items:baseline;gap:9px;background:var(--ghost)}
.dvsec>summary::-webkit-details-marker{display:none}
.dvsec>summary::before{content:'＋';color:var(--cinnabar);font-size:16px;font-weight:400;flex:none}
.dvsec[open]>summary::before{content:'－'}
.dvsec[open]>summary{border-bottom:1px solid var(--hair)}
.dvsec>summary .sm{font-size:14px;font-weight:400;color:var(--ink2);margin-left:auto}
.dvsec .sc{padding:14px 16px 16px}
.dvsec .sc h1,.dvsec .sc h2,.dvsec .sc h3{font-size:16px;margin:12px 0 6px;color:var(--cinnabar)}
.dvplain{font-size:14px;color:var(--ink2);padding:10px 0}
/* 文档页同款微动效：入场淡入 + 折叠展开淡入 + 状态点呼吸（曲线/令牌见模板） */
.dvwrap{animation:panelIn .42s var(--ease, cubic-bezier(.22,.61,.36,1)) both}
details.dvsec[open] .sc{animation:foldIn .3s var(--ease, cubic-bezier(.22,.61,.36,1)) both}
.dvtoc li:hover{transform:translateX(2px)}
#svcbar{display:flex;align-items:center;gap:14px;justify-content:center;font-size:14px;color:var(--ink2);
  padding:9px 20px;background:var(--white);border:1px solid var(--hair);border-radius:var(--r);
  box-shadow:0 1px 3px rgba(26,26,24,.04);max-width:980px;margin:0 auto 4px}
#svcStatus{cursor:pointer;border-bottom:1px dashed var(--hair);padding-bottom:1px}
#svcStatus.on{color:#2f7d4f} #svcStatus.off{color:var(--cinnabar)}
#wbToast{position:fixed;right:22px;bottom:22px;z-index:500;background:var(--ink);color:#fff;font-size:13px;letter-spacing:1px;
  padding:11px 18px;border-radius:3px;opacity:0;transform:translateY(8px);transition:opacity .2s,transform .2s;pointer-events:none;max-width:70vw}
#wbToast.show{opacity:1;transform:translateY(0)}
@media(max-width:640px){.dvbar{padding:9px 14px}.dvpath{max-width:100%}.dvbody{padding:18px 16px 30px}.dvwrap{padding:18px 16px 24px;margin:10px}.tabbar{margin:0 10px 4px}section.tabpane{padding:20px 16px 24px}}
'''

def svcbar_dom():
    return (
        '\n<div id="svcbar" class="off">'
        '<button class="rbtn act" id="btnConnect" type="button">连接工作目录</button>'
        '<span id="svcStatus" class="off">● 未连接 · 点左侧选 01-内容</span>'
        '<button class="rbtn" id="btnSyncAll" type="button">⟳ 同步全库</button>'
        '</div>\n'
    )

def reader_dom():
    return (
        '<div id="docview">'
        '<div class="dvbar">'
        '<a class="dvback" id="dvBack" href="#">← 工作台</a>'
        '<span class="dvpath" id="dvPath"></span>'
        '<span class="dvspacer"></span>'
        '<button class="rbtn" id="btnRead" type="button">预览</button>'
        '<button class="rbtn" id="btnEdit" type="button">编辑</button>'
        '<button class="rbtn act" id="btnSave" type="button">保存到磁盘</button>'
        '<button class="rbtn" id="btnSyncDoc" type="button">⟳ 同步全库</button>'
        '<a class="rraw" id="readerRaw" target="_blank" rel="noopener">原文</a>'
        '</div>'
        '<div class="dvbody" id="readerBody"></div>'
        '</div>\n'
        '<div id="wbToast"></div>\n'
    )

def reader_js():
    return r'''
<script id="docbank" type="application/json">__DOCBANK_PAYLOAD__</script>
<script>
(function(){
  // 浏览器直写模式：不依赖任何后台服务。用户点「连接工作目录」授权 01-内容 后，
  // 保存 = 直接写 md 文件；同步全库 = 遍历所有 md + 重建内嵌快照并写回工作台 HTML。
  var BANK={};
  try{ BANK=JSON.parse(document.getElementById('docbank').textContent); }catch(e){}
  var docview=document.getElementById('docview'),
      rbody=document.getElementById('readerBody'),
      dvpath=document.getElementById('dvPath'),
      rraw=document.getElementById('readerRaw'),
      svcbar=document.getElementById('svcbar'),
      svcStatus=document.getElementById('svcStatus'),
      toastEl=document.getElementById('wbToast');
  var dirHandle=null, editing=false, currentDoc='', toastTimer=null;

  // —— toast ——
  function toast(msg){
    toastEl.textContent=msg; toastEl.classList.add('show');
    clearTimeout(toastTimer); toastTimer=setTimeout(function(){toastEl.classList.remove('show');},2600);
  }
  function escHtml(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}

  // —— Markdown 渲染（与 workbench-core.py 的 render() 逐条对齐）——
  function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function inline(s){
    s=esc(s);
    s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
    s=s.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
    s=s.replace(/\[([^\]]+)\]\(([^)]+)\)/g,function(m,t,u){
      u=u.replace(/"/g,'&quot;');
      if(/\.md($|\?|#)/.test(u))return '<a class="doclink" href="'+u+'">'+t+'</a>';
      return '<a href="'+u+'" target="_blank" rel="noopener">'+t+'</a>';
    });
    return s;
  }
  function mdRender(md){
    var lines=md.split('\n'),out=[],i=0,n=lines.length;
    var special=/^(#{1,6}\s|\||>|```|\s*[-*]\s|\s*\d+\.\s)/;
    function hrule(st){return /^(-{3,}|\*{3,}|_{3,})$/.test(st);}
    while(i<n){
      var line=lines[i],st=line.trim(),buf,m;
      if(st.indexOf('```')===0){
        i++;buf=[];
        while(i<n&&lines[i].trim().indexOf('```')!==0){buf.push(esc(lines[i]));i++;}
        i++;out.push('<pre>'+buf.join('\n')+'</pre>');continue;
      }
      if(hrule(st)){out.push('<hr>');i++;continue;}
      m=/^(#{1,6})\s+(.*)$/.exec(line);
      if(m){var lvl=m[1].length;out.push('<h'+lvl+'>'+inline(m[2])+'</h'+lvl+'>');i++;continue;}
      if(st.indexOf('>')===0){
        buf=[];
        while(i<n&&lines[i].trim().indexOf('>')===0){buf.push(inline(lines[i].trim().replace(/^>+/,'').trim()));i++;}
        out.push('<blockquote>'+buf.join('<br>')+'</blockquote>');continue;
      }
      if(st.indexOf('|')===0&&i+1<n&&/^\|?[\s:\-|]+\|?$/.test(lines[i+1].trim())&&lines[i+1].indexOf('-')>=0){
        function cells(x){return x.replace(/^\|+/,'').replace(/\|+$/,'').split('|').map(function(c){return c.trim();});}
        var header=cells(st);i+=2;var rows=[];
        while(i<n&&lines[i].trim().indexOf('|')===0){rows.push(cells(lines[i].trim()));i++;}
        var th=header.map(function(c){return '<th>'+inline(c)+'</th>';}).join('');
        var trs=rows.map(function(r){return '<tr>'+r.map(function(c){return '<td>'+inline(c)+'</td>';}).join('')+'</tr>';}).join('');
        out.push('<table><thead><tr>'+th+'</tr></thead><tbody>'+trs+'</tbody></table>');continue;
      }
      if(/^\s*[-*]\s+/.test(line)){
        buf=[];
        while(i<n&&/^\s*[-*]\s+/.test(lines[i])){buf.push(inline(lines[i].replace(/^\s*[-*]\s+/,'')));i++;}
        out.push('<ul>'+buf.map(function(x){return '<li>'+x+'</li>';}).join('')+'</ul>');continue;
      }
      if(/^\s*\d+\.\s+/.test(line)){
        buf=[];
        while(i<n&&/^\s*\d+\.\s+/.test(lines[i])){buf.push(inline(lines[i].replace(/^\s*\d+\.\s+/,'')));i++;}
        out.push('<ol>'+buf.map(function(x){return '<li>'+x+'</li>';}).join('')+'</ol>');continue;
      }
      if(st===''){i++;continue;}
      buf=[inline(line)];i++;
      while(i<n&&lines[i].trim()&&!special.test(lines[i])&&!hrule(lines[i].trim())){buf.push(inline(lines[i]));i++;}
      out.push('<p>'+buf.join('<br>')+'</p>');
    }
    return out.join('\n');
  }

  // —— 目录句柄 / 文件读写 ——
  function setConn(on,text){
    svcStatus.textContent=text||(on?'● 已连接工作目录':'● 未连接 · 点「连接工作目录」选 01-内容');
    svcStatus.className=on?'on':'off';
    svcbar.className=on?'':'off';
  }
  function connectDir(){
    if(!window.showDirectoryPicker){toast('此浏览器不支持文件直写，请用 Chrome / Edge 打开工作台');return;}
    window.showDirectoryPicker({mode:'readwrite'}).then(function(h){
      dirHandle=h;
      setConn(true,'● 已连接：'+h.name+' · 保存／同步直接写磁盘');
      toast('已连接工作目录「'+h.name+'」');
    }).catch(function(e){if(e&&e.name!=='AbortError')toast('连接失败：'+e);});
  }
  function fhFor(path,create){
    var parts=path.split('/'),dir=dirHandle;
    function step(i){
      if(i>=parts.length-1)return dir.getFileHandle(parts[i],{create:!!create});
      return dir.getDirectoryHandle(parts[i],{create:!!create}).then(function(d){dir=d;return step(i+1);});
    }
    return step(0);
  }
  function readText(path){
    return fhFor(path,false).then(function(fh){return fh.getFile();}).then(function(f){return f.text();});
  }
  function writeText(path,text){
    return fhFor(path,true).then(function(fh){return fh.createWritable();})
      .then(function(w){return w.write(text).then(function(){return w.close();});});
  }
  function walk(dir,prefix,docs){
    var it=typeof dir.entries==='function'?dir.entries():dir[Symbol.asyncIterator]();
    function next(){
      return it.next().then(function(res){
        if(res.done)return;
        var ent=res.value,name=ent[0],h=ent[1],rel=prefix?prefix+'/'+name:name;
        if(h&&h.kind==='directory'){
          if(name.charAt(0)==='.')return next();
          return walk(h,rel,docs).then(next);
        }
        if(/\.md$/.test(name)){
          return h.getFile().then(function(f){return f.text();}).then(function(t){docs[rel]=t;return next();});
        }
        return next();
      });
    }
    return next();
  }
  function payloadOf(docs){
    var bank={};
    Object.keys(docs).forEach(function(rel){bank[rel]={r:docs[rel],h:mdRender(docs[rel])};});
    return JSON.stringify(bank).replace(/</g,'\\u003c');
  }
  function rebuildHTML(docs){
    var payload=payloadOf(docs);
    var CLOSE='<'+'/script>', OPEN='<'+'script id="docbank" type="application/json">';
    return readText('写作工作台.html').then(function(html){
      var a=html.indexOf(OPEN);
      if(a<0)throw new Error('工作台 HTML 里找不到 docbank 段');
      var b=html.indexOf(CLOSE,a+OPEN.length);
      if(b<0)throw new Error('工作台 HTML 里 docbank 段未闭合');
      return writeText('写作工作台.html',html.slice(0,a)+OPEN+payload+CLOSE+html.slice(b+CLOSE.length));
    });
  }
  function rebuildFromDisk(){
    var docs={};
    return walk(dirHandle,'',docs).then(function(){return rebuildHTML(docs);});
  }

  // —— hash 路由 ——
  function readHash(){var m=/^#doc=(.*)$/.exec(location.hash||'');return m?decodeURIComponent(m[1]):'';}
  function goDoc(key){var h='#doc='+encodeURIComponent(key||'');if(location.hash===h){render(key);}else{location.hash=h;}}
  function goHome(){if(location.hash){location.hash='';}else{render('');}}
  function onHash(){var key=readHash();render(key);}
  function resolve(base,href){
    href=(href||'').split('#')[0].split('?')[0];
    if(!href)return '';
    if(Object.prototype.hasOwnProperty.call(BANK,href))return href;
    var dir=base.indexOf('/')>=0?base.substring(0,base.lastIndexOf('/')+1):'';
    var parts=(dir+href).split('/'),stack=[];
    for(var i=0;i<parts.length;i++){var p=parts[i];if(!p||p==='.')continue;if(p==='..'){stack.pop();continue;}stack.push(p);}
    return stack.join('/');
  }
  function zoneOf(key){
    if(/^00-/.test(key))return '总纲';
    if(key.indexOf('写作/')===0)return '小说';
    if(key.indexOf('大禹治水/')===0||key.indexOf('漫画线稿/')===0)return '漫画 · 单元';
    if(key.indexOf('历史长卷/')===0||key.indexOf('成书稿/')===0||key.indexOf('典籍库/')===0)return '史实';
    if(key.indexOf('手稿/')===0)return '旧稿';
    if(/任务卡/.test(key))return '任务卡';
    if(key.indexOf('写作工作台')>=0)return '工具';
    return '文档';
  }

  // —— 文档页外壳（总-分-细节）——
  function shellDocHTML(html,key){
    var box=document.createElement('div'); box.innerHTML=html||'';
    var fname=(key||'').split('/').pop().replace(/\.md$/,'');
    var lead='',firstBq=box.querySelector('blockquote');
    if(firstBq){lead=firstBq.textContent.replace(/\s+/g,' ').trim();}
    if(lead.length>150)lead=lead.slice(0,150)+'…';
    var secs=[],cur=null,buf=[];
    function flush(){var t=cur?cur.t:'',lv=cur?cur.lv:1,h=buf.join('');if(t||h.replace(/<[^>]+>/g,'').trim())secs.push({t:t,lv:lv,html:h});}
    Array.prototype.slice.call(box.childNodes).forEach(function(nd){
      var tag=nd.nodeType===1?nd.tagName.toLowerCase():'';
      if(tag==='h2'||tag==='h3'){flush();cur={t:nd.textContent.trim(),lv:tag==='h2'?2:3};buf=[];}
      else{buf.push(nd.outerHTML||(''+(nd.textContent||'')));}
    });
    flush();
    if(!secs.length){secs=[{t:'',lv:1,html:box.innerHTML}];}
    var toc=[],body=[],k=0;
    secs.forEach(function(s){
      k++;var id='dvsec-'+k,label=s.t||'开篇',sm=(s.html.replace(/<[^>]+>/g,'').length+' 字');
      toc.push('<li'+(s.lv===3?' class="sub"':'')+' data-goto="'+id+'"><span class="n">'+String(k).padStart(2,'0')+'</span>'+escHtml(label)+'</li>');
      body.push('<details class="dvsec" id="'+id+'"><summary>'+escHtml(label)+'<span class="sm">'+sm+'</span></summary><div class="sc">'+(s.html||'<p class="dvplain">（本节无正文）</p>')+'</div></details>');
    });
    return '<div class="dvwrap">'
      +'<div class="dvloc"><span class="tag">'+escHtml(zoneOf(key))+'</span>'+escHtml(key||'')+'　·　'+secs.length+' 节</div>'
      +'<div class="dvhead">'+escHtml(fname)+'</div>'
      +(lead?'<div class="dvlead">'+escHtml(lead)+'</div>':'')
      +'<div class="dvtoc"><div class="cap"><span>本档目录</span>'
      +'<em><a class="foldall" href="#" data-dvfold="open">展开全部</a> · <a class="foldall" href="#" data-dvfold="close">收起全部</a></em></div>'
      +'<ol>'+toc.join('')+'</ol></div>'
      +body.join('')+'</div>';
  }
  function previewHTML(key){
    var o=BANK[key];
    var h=o?(o.h||''):('<h2>未收录此篇</h2><p>内嵌快照里没有找到：'+escHtml(key||'')+'</p><p>点「连接工作目录」后同步全库即可补全。</p>');
    return shellDocHTML(h,key);
  }
  function syncBtns(){
    document.getElementById('btnRead').className='rbtn'+(editing?'':' act');
    document.getElementById('btnEdit').className='rbtn'+(editing?' act':'');
  }
  function showPreview(){editing=false;rbody.innerHTML=previewHTML(currentDoc);syncBtns();rbody.scrollTop=0;}
  function showEdit(){
    if(!currentDoc){toast('请先点开一篇文档');return;}
    var raw=(BANK[currentDoc]||{}).r||'';
    if(!dirHandle)toast('未连接工作目录：编辑仍可用，保存时会要求连接');
    editing=true;
    rbody.innerHTML='<div class="editnote">正在编辑 · 保存后直接写回 md 文件并更新工作台快照（下游不会自动改写，需另行派生）</div>'
      +'<textarea id="editArea" spellcheck="false">'+escHtml(raw)+'</textarea>';
    syncBtns();
    var ta=document.getElementById('editArea');if(ta){ta.focus();ta.scrollTop=0;}
  }
  function render(key){
    currentDoc=key||'';editing=false;
    if(!currentDoc){document.body.classList.remove('in-doc');return;}
    document.body.classList.add('in-doc');
    dvpath.textContent=currentDoc;
    rraw.setAttribute('href',currentDoc);
    rbody.innerHTML=previewHTML(currentDoc);
    syncBtns();
    window.scrollTo(0,0);
    document.title=currentDoc.split('/').pop()+' · 第七境写作工作台';
    // 已连接则读磁盘最新原文（外部改动也能即时看到）
    if(dirHandle){
      readText(currentDoc).then(function(raw){
        if(currentDoc&&!editing){BANK[currentDoc]={h:mdRender(raw),r:raw};showPreview();}
      }).catch(function(){});
    }
  }

  // —— 提交动作：仅点按钮时写盘 ——
  function saveDoc(){
    if(!currentDoc){toast('请先点开一篇文档');return;}
    var ta=document.getElementById('editArea');
    if(!ta){toast('请先点「编辑」再修改');return;}
    if(!dirHandle){toast('请先点「连接工作目录」选 01-内容');return;}
    var raw=ta.value;
    writeText(currentDoc,raw).then(function(){
      BANK[currentDoc]={h:mdRender(raw),r:raw};
      return rebuildFromDisk();
    }).then(function(){
      showPreview();toast('已写回磁盘 · 工作台快照已更新：'+currentDoc);
    }).catch(function(e){toast('保存失败：'+e);});
  }
  function syncAll(){
    if(!dirHandle){toast('请先点「连接工作目录」选 01-内容');return;}
    toast('正在扫描工作目录并重建快照…');
    var docs={};
    walk(dirHandle,'',docs).then(function(){
      var cnt=Object.keys(docs).length;
      BANK={};Object.keys(docs).forEach(function(rel){BANK[rel]={r:docs[rel],h:mdRender(docs[rel])};});
      return rebuildHTML(docs).then(function(){
        toast('已同步 '+cnt+' 篇并写回工作台文件，即将刷新');
        setTimeout(function(){location.reload();},900);
      });
    }).catch(function(e){toast('同步失败：'+e);});
  }

  // —— 事件 ——
  document.addEventListener('click',function(e){
    var t=e.target;
    if(t.id==='btnConnect'){connectDir();e.preventDefault();return;}
    if(t.id==='dvBack'){goHome();e.preventDefault();return;}
    if(t.id==='btnRead'){showPreview();e.preventDefault();return;}
    if(t.id==='btnEdit'){showEdit();e.preventDefault();return;}
    if(t.id==='btnSave'){saveDoc();e.preventDefault();return;}
    if(t.id==='btnSyncDoc'||t.id==='btnSyncAll'){syncAll();e.preventDefault();return;}
    if(t.id==='svcStatus'){if(!dirHandle)connectDir();return;}
    var dvfold=t.getAttribute&&t.getAttribute('data-dvfold');
    if(dvfold){e.preventDefault();var all=rbody.querySelectorAll('details.dvsec');for(var i=0;i<all.length;i++){all[i].open=(dvfold==='open');}return;}
    var goto=t.closest?t.closest('li[data-goto]'):null;
    if(goto){var tgt=document.getElementById(goto.getAttribute('data-goto'));if(tgt){tgt.open=true;tgt.scrollIntoView({behavior:'smooth',block:'start'});}return;}
    var a=t.closest?t.closest('a'):null;
    if(!a)return;
    if(a.id==='readerRaw')return;
    var href=a.getAttribute('href')||'';
    if(/\.md($|\?|#)/.test(href)){
      e.preventDefault();
      var base=document.body.classList.contains('in-doc')?currentDoc:'';
      goDoc(resolve(base,href));return;
    }
    if(a.classList&&a.classList.contains('rgolink')){e.preventDefault();goHome();}
  });
  window.addEventListener('hashchange',onHash);
  if(readHash()){render(readHash());}
  setConn(false);
  window.__WB_DOCS__=Object.keys(BANK);
  window.__WB_API__={connect:connectDir,save:saveDoc,sync:syncAll,get online(){return !!dirHandle;}};
})();
</script>
'''

def build_payload(docs):
    bank = {}
    for rel, md in docs.items():
        bank[rel] = {"r": md, "h": render(md)}
    return json.dumps(bank, ensure_ascii=False).replace('<', '\\u003c')

def reader_block(docs):
    payload = build_payload(docs)
    js = reader_js().replace('__DOCBANK_PAYLOAD__', payload)
    return reader_dom() + js

def ensure_template():
    """首次：从当前 HTML 剥离已有阅读器块/数据，生成可复用模板。"""
    if os.path.exists(TPL_PATH):
        return
    with open(HTML_PATH, encoding='utf-8') as fh:
        doc = fh.read()
    # 阅读器 CSS：从注释起点到 </style> 前
    doc, n1 = re.subn(r'/\* ===== 页内阅读器.*?\*/\s*', '/*__WB_READER_CSS__*/\n',
                      doc, count=1, flags=re.S)
    if not n1:
        # 兼容旧标记块（无注释标题）：在 </style> 前插入占位
        doc = doc.replace('</style>', '/*__WB_READER_CSS__*/\n</style>', 1)
    # 阅读器 DOM + docbank + JS：从 <div id="reader" 或 <div id="docview" 到 </body> 前
    doc, n2 = re.subn(r'<div id="(?:reader|docview)".*?(?=</body>)', '<!--__WB_READER__-->\n',
                      doc, count=1, flags=re.S)
    if not n2:
        raise RuntimeError('无法定位阅读器 DOM 块，模板生成失败')
    with open(TPL_PATH, 'w', encoding='utf-8') as fh:
        fh.write(doc)
    print('模板已生成:', TPL_PATH, '(%d KB)' % (os.path.getsize(TPL_PATH)//1024))

def rebuild():
    ensure_template()
    docs = collect_docs()
    with open(TPL_PATH, encoding='utf-8') as fh:
        tpl = fh.read()
    if '/*__WB_READER_CSS__*/' not in tpl or '<!--__WB_READER__-->' not in tpl:
        raise RuntimeError('模板占位符缺失')
    doc = tpl.replace('/*__WB_READER_CSS__*/', READER_CSS.strip())
    doc = doc.replace('<!--__WB_SVCBAR__-->', svcbar_dom())
    doc = doc.replace('<!--__WB_READER__-->', reader_block(docs))
    with open(HTML_PATH, 'w', encoding='utf-8') as fh:
        fh.write(doc)
    print('rebuild ok: %d docs, HTML %d KB' % (len(docs), os.path.getsize(HTML_PATH)//1024))
    return len(docs)

# ---------------- 本地 HTTP API ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = 'WBLocal/1.0'
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    def _send(self, code, obj, ctype='application/json; charset=utf-8'):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self._cors()
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError): pass
    def do_OPTIONS(self):
        self._send(204, b'')
    def do_GET(self):
        u = urlparse(self.path); p = unquote(u.path)
        if p in ('/ping', ''):
            self._send(200, {'ok': True, 'base': BASE, 'count': len(collect_docs())})
            return
        if p == '/doc':
            key = parse_qs(u.query).get('key', [''])[0]
            full = safe_path(key)
            if not full or not os.path.isfile(full):
                self._send(404, {'ok': False, 'error': 'not found'}); return
            try:
                raw = open(full, encoding='utf-8').read()
                self._send(200, {'ok': True, 'key': key, 'raw': raw, 'html': render(raw)})
            except Exception as e:
                self._send(500, {'ok': False, 'error': str(e)})
            return
        if p in ('/', '/写作工作台.html'):
            try:
                body = open(HTML_PATH, 'rb').read()
                self._send(200, body, 'text/html; charset=utf-8')
            except Exception as e:
                self._send(500, {'ok': False, 'error': str(e)})
            return
        self._send(404, {'ok': False, 'error': 'no such endpoint'})
    def do_POST(self):
        u = urlparse(self.path); p = unquote(u.path)
        length = int(self.headers.get('Content-Length', 0) or 0)
        raw_body = self.rfile.read(length) if length else b''
        if p == '/save':
            try:
                data = json.loads(raw_body.decode('utf-8'))
            except Exception as e:
                self._send(400, {'ok': False, 'error': 'bad json'}); return
            key = data.get('key', ''); raw = data.get('raw', '')
            full = safe_path(key)
            if not full:
                self._send(403, {'ok': False, 'error': 'path not allowed'}); return
            try:
                tmp = full + '.wbtmp'
                with open(tmp, 'w', encoding='utf-8') as fh: fh.write(raw)
                os.replace(tmp, full)
                self._send(200, {'ok': True, 'key': key, 'html': render(raw)})
            except Exception as e:
                self._send(500, {'ok': False, 'error': str(e)})
            return
        if p == '/rebuild':
            try:
                n = rebuild()
                self._send(200, {'ok': True, 'count': n})
            except Exception as e:
                self._send(500, {'ok': False, 'error': str(e)})
            return
        self._send(404, {'ok': False, 'error': 'no such endpoint'})
    def log_message(self, fmt, *args):
        # 本地服务静默，避免刷屏
        return

def serve(port):
    rebuild()
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print('本地读写服务已启动: http://127.0.0.1:%d/  (Ctrl+C 停止)' % port, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止'); srv.server_close()

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    sub.add_parser('init', help='生成模板并重建一次')
    sub.add_parser('rebuild', help='全量重建工作台快照')
    sp = sub.add_parser('serve', help='启动本地读写服务')
    sp.add_argument('--port', type=int, default=8899)
    args = ap.parse_args()
    if args.cmd == 'serve':
        serve(args.port)
    elif args.cmd == 'rebuild':
        rebuild()
    else:
        ensure_template(); rebuild()

if __name__ == '__main__':
    main()
