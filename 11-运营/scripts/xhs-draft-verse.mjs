// 每日一句金句线 · 小红书「存草稿」（CDP，复用 9226 已登录的 Chrome）
//
// 🔴 设计红线（继承 xhs-draft.mjs 2026-10-22 用户决策）：
//   · 只**存草稿**，绝不点「发布」——发布是对外不可逆动作，留在人手里。
//   · 失败一次即降级：任何一步没匹配上都原样停下并报错，绝不产出残缺草稿。
//   · 定时发布：存好后设好定时（默认当天 20:03），人只负责点提交。
//
// 与百家姓版 xhs-draft.mjs 的差异（2026-11-17）：
//   · 文案目录 = 金句日更-202611；配图 = 成品PNG；封面 = 金句日更-202611/封面-3x4 通用系列封面
//   · 合集 = 「第七境 每日一句金句系列」（平台上若尚无合集，回读会报未选中，需人工建）
//   · 话题 = 文案里自带的 10 个（正好平台上限），不再动态拼姓氏
//   · 配图 = 封面 1 张 + 该条 iPhone/Android 各 1 张（从配图对照表.csv 查）
//   · 幂等日志 = xhs-draft-verse-log.json（与百家姓分开）
//
// 用法：
//   node xhs-draft-verse.mjs --dry --day=D01      # 干跑：只算标题/话题/配图，不碰浏览器
//   node xhs-draft-verse.mjs --day=D01            # 存指定某天草稿
//   node xhs-draft-verse.mjs --day=D01 --time=20:03
//   node xhs-draft-verse.mjs --probe              # 探测发布页 DOM（不动内容）
// 前提：Chrome 已用 start-xhs-browser.sh 起在 9226 且已登录小红书。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const PORT = process.argv[2] && !process.argv[2].startsWith('--') ? process.argv[2] : '9226';
const MODE = process.argv.includes('--probe') ? 'probe'
  : process.argv.includes('--upload') ? 'upload'
  : process.argv.includes('--fix') ? 'fix'
  : process.argv.includes('--dry') ? 'dry' : 'draft';
const DAY_ARG = (process.argv.find(a => a.startsWith('--day=')) || '').split('=')[1];
const FORCE = process.argv.includes('--force');   // 显式强制重存（换封面等）；默认有日志即跳过

const PUBLISH_URL = 'https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image';
const DRAFT_DIR = path.join(ROOT, '04-市场', '03-推广获客', '金句日更-202611');
const IMG_DIR = path.join(DRAFT_DIR, '成品PNG');
const COVER_DIR = path.join(DRAFT_DIR, '封面-3x4');
const COVER_FALLBACK = path.join(COVER_DIR, '金句系列-封面-1179x1572.png'); // 旧通用封面（兼容）
// 当日封面：金句-Dxx-<关键词>-封面-1179x1572.png；找不到回退旧通用封面
function coverFor(day) {
  const hit = fs.readdirSync(COVER_DIR).find(f => f.startsWith(`金句-${day}-`) && /-封面-1179x1572\.png$/.test(f));
  return hit ? path.join(COVER_DIR, hit) : COVER_FALLBACK;
}
const MAP_FILE = path.join(DRAFT_DIR, '配图对照表.csv');
const LOG_FILE = path.join(ROOT, '11-运营', 'data', 'xhs-draft-verse-log.json');

const MAX_TITLE = 22;
const COLLECTION = '第七境 每日一句金句系列';

const dump = (o) => { console.log(JSON.stringify(o)); process.exit(0); };
const fail = (o) => { console.log(JSON.stringify(o)); process.exit(1); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const PROBE_JS = `(() => { try {
  const q = (s) => Array.from(document.querySelectorAll(s));
  return JSON.stringify({
    url: location.href,
    inputs: q('input').map(i => ({ type: i.type, accept: i.accept, cls: String(i.className).slice(0,60), ph: i.placeholder })),
    editables: q('textarea,[contenteditable="true"]').map(e => ({ tag: e.tagName, cls: String(e.className).slice(0,60), ph: e.getAttribute('data-placeholder') || e.placeholder || '' })),
    buttons: q('button').map(b => ({ t: (b.innerText||'').trim().slice(0,20), cls: String(b.className).slice(0,60) })).filter(b => b.t),
    clickables: q('button,div,a,span').map(e => ({ tag: e.tagName, t: (e.innerText||'').trim().slice(0,14), cls: String(e.className).slice(0,70) }))
      .filter(e => e.t && /草稿|发布|保存|存为|预览|定时|提交/.test(e.t + e.cls)),
    text: (document.body.innerText||'').slice(0, 800),
    titleMax: (()=>{ const t = document.querySelector('input.d-text[placeholder="填写标题会有更多赞哦"]');
      return t ? { maxLength: t.maxLength, valLen: (t.value||'').length } : null; })(),
    tail: (document.body.innerText||'').slice(-1600),
  });
} catch(e) { return JSON.stringify({ err: String(e) }); } })()`;

// 简易 CSV（本批字段无引号内含逗号）
function readMap() {
  const txt = fs.readFileSync(MAP_FILE, 'utf8').trim().split(/\r?\n/);
  const head = txt[0].split(',');
  return txt.slice(1).map(line => {
    const c = line.split(',');
    return Object.fromEntries(head.map((h, i) => [h, c[i] || '']));
  });
}

function parseDay(day) {
  const file = fs.readdirSync(DRAFT_DIR).find(f => f.startsWith(day + '-'));
  if (!file) return null;
  const md = fs.readFileSync(path.join(DRAFT_DIR, file), 'utf8');
  const title = ((md.match(/\*\*标题\*\*：(.+)/) || [])[1] || '')
    .replace(/[（(]\s*\d+\s*字\s*[）)]\s*$/, '').trim();
  const body = (md.match(/```\n([\s\S]*?)\n```/) || [])[1] || '';
  const topicLine = ((md.match(/\*\*话题\*\*：(.+)/) || [])[1] || '').trim();
  const topics = topicLine.split(/\s+/).filter(t => t.startsWith('#')).map(t => t.slice(1));
  const kw = (file.match(/^D\d+-(.+)\.md$/) || [])[1] || '';
  const map = readMap().find(r => r['关键词'] === kw);
  return { day, file, title, body, topics, kw, map };
}

function fitTitle(t) {
  if ([...t].length <= MAX_TITLE) return { text: t, truncated: false };
  let s = [...t].slice(0, MAX_TITLE).join('');
  s = s.replace(/[（(][^（()）]*$/, '').trim();
  return { text: s, truncated: true };
}

function buildBody(d) {
  // 正文里的话题行（若有）剥掉，统一由脚本按文案 **话题** 行附加
  const lines = d.body.split('\n').filter(l => !/^\s*#/.test(l)).join('\n').replace(/\n{3,}/g, '\n\n').trimEnd();
  const tops = d.topics.length ? d.topics : ['传统文化', '国风', '国学智慧'];
  return lines + '\n\n' + tops.map(t => '#' + t).join(' ');
}

async function main() {
  if (MODE === 'probe' && !DAY_ARG) { /* probe 不需要 day */ }
  else if (!DAY_ARG) return fail({ error: 'NEED_DAY', hint: '金句线按 --day=D01 显式指定，不按日期推算' });
  const day = (DAY_ARG || 'D01').toUpperCase();
  const d = parseDay(day);
  if (!d) return fail({ error: 'NO_DAY_FILE', day });
  const cover = coverFor(day);
  if (!fs.existsSync(cover)) return fail({ error: 'COVER_MISSING', cover });
  if (!d.map) return fail({ error: 'NO_MAP_ROW', kw: d.kw });
  const imgs = [d.map['iPhone图'], d.map['Android图']].map(n => path.join(IMG_DIR, n));
  const files = [cover, ...imgs];
  const missing = files.filter(f => !fs.existsSync(f));
  if (missing.length) return fail({ error: 'IMG_MISSING', missing });
  if (!d.title || !d.body) return fail({ error: 'PARSE_FAIL', day, title: !!d.title, body: !!d.body });

  const t = fitTitle(d.title);
  const body = buildBody(d);

  if (MODE === 'dry') return dump({
    stage: 'dry', day, file: d.file, kw: d.kw,
    title: t.text, titleLen: [...t.text].length, titleTruncated: t.truncated,
    uploadOrder: files.map(f => path.basename(f)),
    topics: d.topics, topicCount: d.topics.length,
    bodyLen: [...body].length, collection: COLLECTION, body,
  });

  // 幂等
  let log = {};
  try { log = JSON.parse(fs.readFileSync(LOG_FILE, 'utf8')); } catch { }
  if (log[day] && !FORCE) return dump({ stage: 'already-saved', day, at: log[day].at });

  let list;
  try { list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); }
  catch { return fail({ error: 'NO_DEBUG_PORT', hint: `Chrome 未以 --remote-debugging-port=${PORT} 启动` }); }
  const page = list.find(t2 => t2.type === 'page' && /xiaohongshu\.com/.test(t2.url || ''));
  if (!page) return fail({ error: 'NO_XHS_TAB', hint: '没找到小红书标签，先跑 start-xhs-browser.sh 并登录' });

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws error')); });
  let id = 0;
  const send = (method, params) => new Promise((resolve) => {
    const myId = ++id;
    const h = (ev) => { const m = JSON.parse(ev.data); if (m.id === myId) { ws.removeEventListener('message', h); resolve(m); } };
    ws.addEventListener('message', h);
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  const ev = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    return r.result?.result?.value;
  };

  await send('Page.enable'); await send('Runtime.enable');
  let cur = '';
  try { cur = await ev('location.href'); } catch { }
  if (!((MODE === 'probe' || MODE === 'fix') && /publish\/publish/.test(cur || ''))) {
    await send('Page.navigate', { url: PUBLISH_URL });
    await sleep(8000);
  } else {
    await sleep(1500);
  }
  // 2026-11-17 修复：连续存多篇时，小红书会把未提交的上一篇编辑态“粘”回来
  // （标题/图还在、无 input.upload-input）⇒ 强制 reload 拿干净的上传页，最多 2 次。
  if (MODE === 'draft' || MODE === 'upload') {
    for (let k = 0; k < 2; k++) {
      const clean = await ev("!!document.querySelector('input.upload-input')");
      if (clean) break;
      await send('Page.reload', { ignoreCache: false });
      await sleep(6000);
    }
  }

  if (MODE === 'probe') return dump(await ev(PROBE_JS));

  // 1. 上传图片
  if (MODE !== 'fix') {
    await send('DOM.enable');
    const doc = await send('DOM.getDocument', { depth: -1 });
    const rootId = doc.result?.root?.nodeId;
    const q = await send('DOM.querySelector', { nodeId: rootId, selector: 'input.upload-input' });
    const inputId = q.result?.nodeId;
    if (!inputId) return fail({ error: 'NO_UPLOAD_INPUT', hint: '没找到 input.upload-input，页面结构可能已变' });
    await send('DOM.setFileInputFiles', { files, nodeId: inputId });
    // 2026-11-17 修复：上传后编辑态渲染有延迟，固定 15s 仍可能查不到标题框 ⇒ 轮询等待
    // input.d-text[placeholder] 出现（最多 ~30s），否则报 NO_TITLE_INPUT（不硬重试）。
    const TITLE_SEL_EARLY = 'input.d-text[placeholder="填写标题会有更多赞哦"]';
    let waited = 0;
    for (; waited < 30; waited += 2) {
      await sleep(2000);
      const ready = await ev(`!!document.querySelector(${JSON.stringify(TITLE_SEL_EARLY)})`);
      if (ready) break;
    }
    await sleep(1500);  // 标题框出来后再给正文框一点渲染时间
    if (MODE === 'upload') return dump({ stage: 'uploaded', day, count: files.length, waitedSec: waited, ...JSON.parse(await ev(PROBE_JS) || '{}') });
  }

  // 2. 标题（focus 校验后插入）
  const TITLE_SEL = 'input.d-text[placeholder="填写标题会有更多赞哦"]';
  const BODY_SEL = 'div.tiptap.ProseMirror';
  const clearTitleJs = `(()=>{const e=document.querySelector(${JSON.stringify(TITLE_SEL)}); if(!e) return 'NO'; e.focus(); e.setSelectionRange(0,(e.value||'').length); return String((e.value||'').length);})()`;
  const had = await ev(clearTitleJs);
  if (had === 'NO') return fail({ error: 'NO_TITLE_INPUT' });
  if (Number(had) > 0) {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
    await sleep(500);
  }
  await send('Input.insertText', { text: t.text });
  await sleep(1200);

  // 3. 正文
  const clearBodyJs = `(()=>{const b=document.querySelector(${JSON.stringify(BODY_SEL)}); if(!b) return 'NO'; b.focus();
    document.execCommand('selectAll'); document.execCommand('delete');
    return document.activeElement===b ? 'OK' : 'NOTFOCUSED';})()`;
  const cb = await ev(clearBodyJs);
  if (cb !== 'OK') return fail({ error: 'NO_BODY_FOCUS', got: cb });
  await send('Input.insertText', { text: body });
  await sleep(6000);

  // 4. 选合集「第七境 每日一句金句系列」——按标签优先级挑候选行，真实鼠标事件点，回读校验
  const collState = () => ev(`(()=>{const w=document.querySelector('div.collection-plugin-wrapper')||document.querySelector('div.collection-plugin-button');
    return w? (w.innerText||'').replace(/\\n/g,' ').slice(0,80) : 'NO';})()`);
  const openColl = await ev(`(()=>{const b=document.querySelector('div.collection-plugin-button'); if(!b) return 'NO'; b.scrollIntoView({block:'center'}); b.click(); return 'OK';})()`);
  await sleep(2500);
  const candsRaw = openColl === 'OK' ? await ev(`(()=>{
    const pri=(e)=>{const c=String(e.className);const t=e.tagName;
      if(e.getAttribute&&e.getAttribute('role')==='option')return 0;
      if(t==='LI')return 1;
      if(/option|item|cell|row/i.test(c))return 2;
      if(t==='LABEL')return 3;
      return 4;};
    const els=Array.from(document.querySelectorAll('li,label,div,span,a,button'))
      .filter(x=>x.offsetParent && String(x.innerText||'').trim().includes('金句'))
      .filter(x=>x.querySelectorAll('*').length<40);
    els.sort((a,b)=>pri(a)-pri(b)||a.querySelectorAll('*').length-b.querySelectorAll('*').length);
    return JSON.stringify(els.slice(0,4).map(x=>{const r=x.getBoundingClientRect();
      return {tag:x.tagName,cls:String(x.className).slice(0,50),txt:(x.innerText||'').trim().slice(0,24),
        x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),w:Math.round(r.width),h:Math.round(r.height)};}));})()`) : '[]';
  let collNow = await collState();
  let pickColl = openColl === 'OK' ? 'NOTFOUND' : 'NO_BUTTON';
  let tried = [];
  for (const c of (JSON.parse(candsRaw || '[]') || [])) {
    if (c.w < 5 || c.h < 5 || c.w > 600 || c.h > 160) { tried.push('SKIP:' + c.txt); continue; }
    for (const [type, button] of [['mouseMoved', 'none'], ['mousePressed', 'left'], ['mouseReleased', 'left']]) {
      await send('Input.dispatchMouseEvent', { type, x: c.x, y: c.y, button, clickCount: 1 });
    }
    await sleep(1600);
    collNow = await collState();
    tried.push(c.txt);
    if (/金句/.test(collNow) && !/选择合集/.test(collNow)) { pickColl = 'OK:' + c.txt; break; }
    pickColl = 'CLICKED_NOT_APPLIED:' + c.txt;
  }

  // 5. 原创声明 / AI 合成声明
  const SW_ORIGINAL = 'div.original-wrapper .d-switch-simulator';
  const mouseClick = async (x, y) => {
    for (const [type, button] of [['mouseMoved', 'none'], ['mousePressed', 'left'], ['mouseReleased', 'left']]) {
      await send('Input.dispatchMouseEvent', { type, x, y, button, clickCount: 1 });
    }
  };
  const flipSwitch = async (sel) => {
    const raw = await ev("(()=>{const s=document.querySelector(" + JSON.stringify(sel) + "); if(!s) return null;"
      + " s.scrollIntoView({block:'center'}); const r=s.getBoundingClientRect();"
      + " return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),"
      + " on:/\\bchecked\\b/.test(String(s.className))});})()");
    if (!raw) return { state: 'NO_SWITCH' };
    const b = JSON.parse(raw);
    if (b.on) return { state: 'ALREADY_ON' };
    await mouseClick(b.x, b.y);
    await sleep(2000);
    const after = await ev("(()=>{const s=document.querySelector(" + JSON.stringify(sel) + ");"
      + " return s ? (/\\bchecked\\b/.test(String(s.className)) ? 'ON' : 'STILL_OFF') : 'NO_SWITCH';})()");
    return { state: after };
  };
  const originalSw = await flipSwitch(SW_ORIGINAL);
  const aiNow = await ev("(()=>{const w=Array.from(document.querySelectorAll('.d-select-wrapper'))"
    + ".filter(x=>String(x.innerText||'').includes('添加内容类型声明')&&x.offsetParent)[0];"
    + " return w ? (w.innerText||'').replace(/\\n/g,' ').slice(0,60) : 'NO';})()");
  let aiRes = 'SKIPPED';
  if (aiNow !== 'NO' && !/AI合成/.test(aiNow)) {
    const raw = await ev("(async()=>{const sl=(ms)=>new Promise(r=>setTimeout(r,ms));"
      + " const w=Array.from(document.querySelectorAll('.d-select-wrapper'))"
      + ".filter(x=>String(x.innerText||'').includes('添加内容类型声明')&&x.offsetParent)[0];"
      + " const m=w&&w.querySelector('.d-select-main'); if(!m) return 'NOMAIN';"
      + " m.scrollIntoView({block:'center'}); m.click(); await sl(900);"
      + " const os=Array.from(document.querySelectorAll('li,div,span')).filter(o=>o.offsetParent"
      + " && o.children.length===0 && /AI合成/.test((o.innerText||'').trim()));"
      + " if(!os.length) return 'NO_OPTION'; const r=os[0].getBoundingClientRect();"
      + " return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),txt:(os[0].innerText||'').trim()});})()");
    if (raw && String(raw)[0] === '{') { const b = JSON.parse(raw); await mouseClick(b.x, b.y); await sleep(1200); aiRes = 'PICKED:' + b.txt; }
    else aiRes = String(raw);
  } else if (/AI合成/.test(aiNow)) aiRes = 'ALREADY';

  // 5.5 定时发布（默认当天 20:03，不足 30 分钟顺延次日）
  const TIME_ARG = (process.argv.find(a => a.startsWith('--time=')) || '').split('=')[1] || '20:03';
  const [SH, SM] = TIME_ARG.split(':').map(Number);
  const nowD = new Date();
  let stT = new Date(nowD.getFullYear(), nowD.getMonth(), nowD.getDate(), SH, SM, 0, 0);
  if (stT.getTime() - nowD.getTime() < 30 * 60000) stT = new Date(stT.getTime() + 86400000);
  const sDay = String(stT.getDate());
  const sHH = String(stT.getHours()).padStart(2, '0');
  const sMM = String(stT.getMinutes()).padStart(2, '0');
  const schedTarget = stT.getFullYear() + '-' + String(stT.getMonth() + 1).padStart(2, '0')
    + '-' + String(stT.getDate()).padStart(2, '0') + ' ' + sHH + ':' + sMM;
  const SW_POSTTIME = 'div.post-time-wrapper .d-switch-simulator';
  const timeSw = await flipSwitch(SW_POSTTIME);
  const sched = { switch: timeSw.state, target: schedTarget };
  if (timeSw.state === 'ON' || timeSw.state === 'ALREADY_ON') {
    // 2026-11-17 修复：React 组件不吃 el.click()，必须真实鼠标事件才弹日期层（NO_CELL 的根因）
    const pickRaw = await ev("(()=>{const w=document.querySelector('div.post-time-wrapper'); if(!w) return 'NO_WRAP';"
      + " const i=w.querySelector('input.d-text'); if(!i) return 'NO_INPUT';"
      + " i.scrollIntoView({block:'center'}); const r=i.getBoundingClientRect();"
      + " return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)});})()");
    if (pickRaw && String(pickRaw)[0] === '{') { const b = JSON.parse(pickRaw); await mouseClick(b.x, b.y); sched.picker = 'MOUSE_CLICKED'; }
    else sched.picker = String(pickRaw);
    await sleep(2000);
    const cellRaw = await ev("(()=>{const pop=document.querySelector('.post-time-date-picker-popover')||document.body;"
      + " const cs=Array.from(pop.querySelectorAll('*')).filter(e=>e.children.length===0"
      + " && !/prev|next|other|disabled/i.test(String(e.className))"
      + " && (e.innerText||'').trim()===" + JSON.stringify(sDay) + ");"
      + " if(!cs.length) return 'NO_CELL'; const r=cs[0].getBoundingClientRect();"
      + " return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)});})()");
    if (cellRaw && String(cellRaw)[0] === '{') { const b = JSON.parse(cellRaw); await mouseClick(b.x, b.y); await sleep(1500); sched.day = 'CLICKED'; }
    else sched.day = String(cellRaw);
    const snapCol = async (idx, val) => {
      const raw = await ev("(()=>{const bars=Array.from(document.querySelectorAll('.d-timepicker-timebar'));"
        + " const bar=bars[" + idx + "]; if(!bar) return 'NO_BAR';"
        + " const t=Array.from(bar.children).find(i=>(i.innerText||'').trim()===" + JSON.stringify(val) + ");"
        + " if(!t) return 'NO_ITEM'; bar.scrollTop=t.offsetTop-bar.clientHeight/2+t.clientHeight/2;"
        + " const r=bar.getBoundingClientRect();"
        + " return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),st:bar.scrollTop});})()");
      if (!raw || String(raw)[0] !== '{') return String(raw);
      const b = JSON.parse(raw);
      await send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: b.x, y: b.y }] });
      await send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: b.x, y: b.y - 2 }] });
      await send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
      await sleep(1200);
      return 'SNAPPED';
    };
    sched.hour = await snapCol(0, sHH);
    sched.min = await snapCol(1, sMM);
    sched.value = await ev("(()=>{const w=document.querySelector('div.post-time-wrapper');"
      + " const i=w&&w.querySelector('input.d-text'); return i?i.value:null;})()");
  }

  // 6. 验证 + 落日志
  const verify = await ev(`(() => { try {
    const ti = document.querySelector('${TITLE_SEL}');
    const b = document.querySelector('div.tiptap.ProseMirror');
    const m = (document.body.innerText||'').match(/草稿箱\\((\\d+)\\)/);
    return JSON.stringify({ title: (ti && ti.value) || '', bodyLen: ((b && b.innerText) || '').length,
      draftBox: m ? m[1] : null, autoSaved: /编辑于/.test(document.body.innerText||'') });
  } catch(e) { return JSON.stringify({ err: String(e) }); } })()`);
  const v = JSON.parse(verify || '{}');

  log[day] = { at: new Date().toISOString(), file: d.file, title: t.text };
  fs.writeFileSync(LOG_FILE, JSON.stringify(log, null, 1));

  return dump({
    stage: 'draft-saved', day, file: d.file, kw: d.kw,
    title: t.text, titleLen: [...t.text].length, titleTruncated: t.truncated,
    topics: d.topics, uploadOrder: files.map(f => path.basename(f)),
    collection: collNow.includes('金句') && !/选择合集/.test(collNow) ? COLLECTION : ('未选中:' + collNow),
    collectionOpened: openColl, collectionPicked: pickColl, collectionTried: tried,
    original: originalSw.state, aiDeclare: aiRes, schedule: sched,
    manual: ['点「发布笔记」提交（提交按钮自动化定位不到，永远人工点）'],
    manualNote: '原创声明不随草稿保存：若中途重开过草稿箱，提交前需当场重勾',
    ...v,
  });
}

main().catch(e => fail({ error: 'EXCEPTION', msg: String(e) }));
