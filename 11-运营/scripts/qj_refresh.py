#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七境 · 刷新按钮（前端片段 + 端点约定）

为什么需要它：工作台与晨检看板都是「生成好的静态 HTML」，
页面自己不会去取数。想点一下就看到新数据，必须有个东西在背后真去跑取数脚本。
所以刷新分两层：

  1. 本地刷新服务 refresh-server.py（Mac mini 上常驻，127.0.0.1:8787）
     —— 真取数（站点体检）→ 重建看板片段 → 重建工作台 → 可选同步云端。
  2. 页面上的按钮
     —— 服务在，就真刷新；服务不在，退化为「重新载入」（资料库在线页仍可拉到
        最近一次同步上来的版本）。

本文件被两个生成器共用（与 qj_theme.py 同样的理由：两边各写一套必然风格漂移）：
  - build-workbench.py       门户（:root 作用域，按钮常驻 tabbar）
  - build-morning-board.py   看板（.mb 作用域，按钮在 header；内嵌片段不含 header，故不重复）

命名：下划线。项目脚本用连字符，Python 不能直接 import，只能按文件路径加载。
"""
from datetime import datetime

# 与 refresh-server.py 保持一致；改端口两边一起改
API_BASE = "http://127.0.0.1:8787"
PORT = 8787

# ---------- 样式：门户（:root 作用域） ----------
CSS_HOST = """
.qjbar{display:flex;align-items:center;gap:10px;margin-left:8px;flex-wrap:wrap}
.qjbtn{font-family:var(--f-brush);font-size:15px;letter-spacing:2px;color:var(--ink2);
 background:var(--wash);border:1px solid var(--line);border-radius:2px;padding:5px 13px;
 cursor:pointer;transition:color .2s,border-color .2s,background .2s;white-space:nowrap}
.qjbtn:hover{color:var(--cinnabar);border-color:rgba(176,56,38,.35);background:var(--wash2)}
.qjbtn[disabled]{opacity:.5;cursor:progress}
.qjbtn.ok{color:var(--ok);border-color:rgba(74,124,89,.4)}
.qjbtn.bad{color:var(--cinnabar);border-color:rgba(176,56,38,.4)}
.qjtip{font-size:11.5px;color:var(--ink3);letter-spacing:.4px;line-height:1.6}
@media(max-width:520px){.qjbtn{font-size:13px;padding:5px 10px}}
"""

# ---------- 样式：看板（.mb 作用域，不污染宿主） ----------
CSS_MB = """
.mb .qjbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:14px}
.mb .qjbtn{font-family:var(--f-body);font-size:13px;letter-spacing:.1em;color:var(--ink2);
 background:var(--white);border:1px solid var(--line);border-radius:2px;padding:5px 14px;cursor:pointer}
.mb .qjbtn:hover{color:var(--cinnabar);border-color:rgba(176,56,38,.35)}
.mb .qjbtn[disabled]{opacity:.5;cursor:progress}
.mb .qjbtn.ok{color:var(--ok);border-color:rgba(74,124,89,.4)}
.mb .qjbtn.bad{color:var(--cinnabar);border-color:rgba(176,56,38,.4)}
.mb .qjtip{font-size:12px;color:var(--ink3);letter-spacing:.06em}
"""

JS_BTN = """
<button class="qjbtn" id="qj-refresh" type="button"
 title="点一下：重新取数并重建本页（Shift + 点：同时同步到资料库）">刷新数据</button>
"""

# 「连不上」有两种完全不同的原因，提示必须分开说（两块脚本共用，拼在 go() 之前）：
#   1) 云端页（https）——浏览器规则禁止 https 页请求 http://127.0.0.1，服务跑着也连不上；
#   2) 本地页（file:// 或 127.0.0.1）——多半是服务真没启动。
# 之前两种都写「刷新服务未启动」，用户在云端页点了就被误导（2026-10-09 实测）。
JS_OFFLINE = """
function offline(){
  var remote=(location.protocol==='https:')||
             (location.hostname!=='127.0.0.1'&&location.hostname!=='localhost'&&location.hostname!=='');
  btn.disabled=false; btn.className='qjbtn';
  say(remote?'云端页连不到本机服务（浏览器规则）· 已重新载入；要实时取数请在本机打开 127.0.0.1:8787'
             :'刷新服务未启动 · 已重新载入；在终端跑 refresh-server.py 后可真取数');
  setTimeout(function(){ location.reload(); },600);
}
"""

# ---------- 脚本：门户（含状态灯细粒度重绘） ----------
# 约定：容器 #qj-pulse（状态灯）、数据 #qj-pulse-data（内嵌 JSON）、
#      时间戳 #qj-gen、提示 #qj-refresh-tip。
# 一律用 createElement + textContent 构建 DOM（不拼字符串进 DOM），避免注入面。
JS_HOST = """
(function(){
var API='::API::';
var btn=document.getElementById('qj-refresh');
if(!btn){return;}
var tipEl=document.getElementById('qj-refresh-tip');
var boxEl=document.getElementById('qj-pulse');
var dataEl=document.getElementById('qj-pulse-data');
var genEl=document.getElementById('qj-gen');
var KEY='qj-pulse-v1';
function say(s){ if(tipEl){tipEl.textContent=s;} }
function read(el){ if(!el){return null;} try{return JSON.parse(el.textContent||'');}catch(e){return null;} }
function newer(a,b){ return !!(a&&a.gen&&(!b||!b.gen||String(a.gen)>String(b.gen))); }
function draw(list){
  if(!boxEl||!list||!list.length){return;}
  while(boxEl.firstChild){boxEl.removeChild(boxEl.firstChild);}
  list.forEach(function(it){
    var d=document.createElement('div'); d.className='p '+(it.cls||'na');
    var k=document.createElement('div'); k.className='pk'; k.textContent=it.k||'';
    var v=document.createElement('div'); v.className='pv '+(it.cls||'na'); v.textContent=it.v||'';
    var n=document.createElement('div'); n.className='pn'; n.textContent=it.n||'';
    d.appendChild(k); d.appendChild(v); d.appendChild(n); boxEl.appendChild(d);
  });
}
function apply(p){
  if(!p||!p.items){return;}
  draw(p.items);
  if(genEl&&p.gen){ genEl.textContent=p.gen+' 刷新'; }
  var red=p.items.filter(function(x){return x.cls==='bad'||x.cls==='warn';}).length;
  var sEl=document.getElementById('qj-pulse-sum');
  if(sEl){ sEl.textContent=p.items.length+' 项指标　·　'+(red?('有 '+red+' 项不在正常区间'):'全部正常'); }
}
function store(p){ try{sessionStorage.setItem(KEY,JSON.stringify(p));}catch(e){} }
var cur=read(dataEl), saved=null;
try{ saved=JSON.parse(sessionStorage.getItem(KEY)||'null'); }catch(e){}
if(newer(saved,cur)){ apply(saved); }
function to(url,opt,ms){
  opt=opt||{};
  if(typeof AbortController==='function'){
    var c=new AbortController(); opt.signal=c.signal;
    var t=setTimeout(function(){c.abort();},ms||1500);
    return fetch(url,opt).then(function(r){clearTimeout(t);return r;},
                               function(e){clearTimeout(t);throw e;});
  }
  return fetch(url,opt);
}
function go(upload){
  btn.disabled=true; btn.className='qjbtn';
  say(upload?'正在取数并同步云端…':'正在取数…');
  to(API+'/ping',{cache:'no-store'},1200).then(function(){
    return to(API+'/refresh'+(upload?'?upload=1':''),{method:'POST',cache:'no-store'},240000);
  }).then(function(r){return r.json();}).then(function(j){
    btn.disabled=false;
    if(j&&j.ok){
      btn.className='qjbtn ok';
      say('已刷新 · '+(j.gen||'')+(j.uploaded?' · 已同步云端':'')+' · 正在载入');
      apply(j); store(j);
      setTimeout(function(){ location.reload(); },900);
    }else{
      btn.className='qjbtn bad';
      say('刷新失败：'+((j&&j.error)||'服务端未返回数据'));
    }
  }).catch(function(){ offline(); });
}
btn.addEventListener('click',function(ev){ go(!!ev.shiftKey); });
})();
"""

# ---------- 脚本：看板（无状态灯 JSON，刷新后整页重载） ----------
JS_MB = """
(function(){
var API='::API::';
var btn=document.getElementById('qj-refresh');
if(!btn){return;}
var tipEl=document.getElementById('qj-refresh-tip');
function say(s){ if(tipEl){tipEl.textContent=s;} }
function to(url,opt,ms){
  opt=opt||{};
  if(typeof AbortController==='function'){
    var c=new AbortController(); opt.signal=c.signal;
    var t=setTimeout(function(){c.abort();},ms||1500);
    return fetch(url,opt).then(function(r){clearTimeout(t);return r;},
                               function(e){clearTimeout(t);throw e;});
  }
  return fetch(url,opt);
}
function go(upload){
  btn.disabled=true;
  say(upload?'正在取数并同步云端…':'正在取数…');
  to(API+'/ping',{cache:'no-store'},1200).then(function(){
    return to(API+'/refresh'+(upload?'?upload=1':''),{method:'POST',cache:'no-store'},240000);
  }).then(function(r){return r.json();}).then(function(j){
    btn.disabled=false;
    if(j&&j.ok){ say('已刷新 · '+(j.gen||'')+(j.uploaded?' · 已同步云端':'')+' · 正在载入');
      setTimeout(function(){ location.reload(); },900);
    }else{ say('刷新失败：'+((j&&j.error)||'服务端未返回数据')); }
  }).catch(function(){ offline(); });
}
btn.addEventListener('click',function(ev){ go(!!ev.shiftKey); });
})();
"""

# 把 offline 拼进两块脚本（避免两处各抄一遍）
JS_HOST = JS_HOST.replace("\nfunction go(upload){", JS_OFFLINE + "\nfunction go(upload){")
JS_MB = JS_MB.replace("\nfunction go(upload){", JS_OFFLINE + "\nfunction go(upload){")


def js(kind="host"):
    """返回可用脚本（把 ::API:: 替换成真实端点）。kind: host | mb"""
    src = JS_HOST if kind == "host" else JS_MB
    return src.replace("::API::", API_BASE)


def button(tip=""):
    """按钮 + 提示文案（提示区可为空，由 JS 写入）"""
    return f'{JS_BTN.strip()}\n      <span class="qjtip" id="qj-refresh-tip">{tip}</span>'


def pulse_payload(items):
    """内嵌到页面的状态灯数据，供刷新后无需重载即可重绘。"""
    import json
    return json.dumps({"gen": datetime.now().strftime("%Y-%m-%d %H:%M"),
                       "items": items}, ensure_ascii=False)
