// 小红书创作服务平台 · 每日「存草稿」（CDP，复用 9226 已登录的 Chrome）
//
// 🔴 设计红线（2026-10-22 用户决策）：
//   · 只**存草稿**，绝不点「发布」——发布是对外不可逆动作，留在人手里。
//   · 每天一篇（姓氏日更 D01–D25），草稿存好后由人早上点一下发出去。
//   · 失败一次即降级：任何一步没匹配上都原样停下并报错，绝不产出残缺草稿。
//
// 用法：
//   node xhs-draft.mjs --probe              # 探测发布页 DOM 结构（不动任何内容）
//   node xhs-draft.mjs --day=D01            # 存指定某天的草稿
//   node xhs-draft.mjs --dry                # 干跑：只算标题/话题/配图，不碰浏览器
//   node xhs-draft.mjs                      # 按日期自动推算今天该存哪篇
//
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

const PUBLISH_URL = 'https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image';
const DRAFT_DIR = path.join(ROOT, '04-市场', '03-推广获客', '姓氏日更-202610');
const IMG_DIR = path.join(ROOT, '02-商品', '06-姓氏线', '成品-手机竖版', '小红书-3x4');
// 封面：图 1 专用（2026-10-23 起）。版式复刻《16 张朝代手机壁纸》成功封面，
// 由 02-商品/06-姓氏线/版式/gen-cover-v2.py 生成，文件名 DNN-四姓-封面-1179x1572.png
const COVER_DIR = path.join(ROOT, '02-商品', '06-姓氏线', '成品-手机竖版', '封面-3x4');
const TOPIC_FILE = path.join(ROOT, '11-运营', 'data', 'xhs-topics.json');
const LOG_FILE = path.join(ROOT, '11-运营', 'data', 'xhs-draft-log.json');
const START_DATE = '2026-10-22';   // D01 的发布日，之后每天 +1

// —— 发布口径（2026-10-22 用户定）——
const MAX_TITLE = 22;                       // 标题字数上限，超了自动截断
const COLLECTION = '第七境 百家姓系列';       // 平台上的合集名（用户名叫「第七境 百家姓」）
// 🔴 2026-10-26 用户改口径：平台话题上限 10 个 ⇒ 固定话题砍到 6 个（去掉「壁纸」「书法」），
//    6 固定 + 当天 4 姓氏 = 正好 10。MAX_TOPICS 是硬兜底，超了从尾部截断。
const FIXED_TOPICS = ['传统文化', '国风', '手机壁纸', '东方美学', '百家姓', '汉字'];
const MAX_TOPICS = 10;

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
    topicish: q('div,span,label,li').map(e => ({ tag: e.tagName, cls: String(e.className).slice(0,80), t: (e.innerText||'').trim().slice(0,28) }))
      .filter(e => /合集|原创|声明|AI|合成|生成|话题|标签|参与|活动/.test(e.t + e.cls)),
    tail: (document.body.innerText||'').slice(-1600),
  });
} catch(e) { return JSON.stringify({ err: String(e) }); } })()`;

// 解析 D0X 文案 md：标题 / 配图文件名 / 正文
function parseDay(day) {
  const file = fs.readdirSync(DRAFT_DIR).find(f => f.startsWith(day + '-'));
  if (!file) return null;
  const md = fs.readFileSync(path.join(DRAFT_DIR, file), 'utf8');
  // 🔴 2026-10-25 修复：文案里 `**标题**：xxx（15 字）` 的「（N 字）」是给编辑看的字数标注，
  //    以前直接整行取走 ⇒ D01–D04 实际发布标题末尾都带着「（15 字）」，等于把草稿备注发到了线上。
  //    这里剥掉末尾的字数标注；文件里保留标注不影响判断。
  const title = ((md.match(/\*\*标题\*\*：(.+)/) || [])[1]?.trim() || '')
    .replace(/[（(]\s*\d+\s*字\s*[）)]\s*$/, '')
    .trim();
  const imgsLine = (md.match(/\*\*配图\*\*[^\n]*：(.+)/) || [])[1] || '';
  const imgs = Array.from(imgsLine.matchAll(/`([^`]+\.png)`/g)).map(m => m[1]);
  const body = (md.match(/```\n([\s\S]*?)\n```/) || [])[1] || '';
  const surname = (file.match(/^D\d+-(.+)\.md$/) || [])[1] || '';
  return { day, file, title, imgs, body, surname };
}

function todayDay() {
  if (DAY_ARG) return DAY_ARG.toUpperCase();
  const s = new Date(START_DATE + 'T00:00:00');
  const n = new Date(); const n0 = new Date(n.getFullYear(), n.getMonth(), n.getDate());
  const diff = Math.round((n0 - s) / 86400000);
  if (diff < 0 || diff > 24) return null;
  return 'D' + String(diff + 1).padStart(2, '0');
}

// 标题截断到 22 字；截断后若停在半截括号上就把它去掉
function fitTitle(t) {
  if ([...t].length <= MAX_TITLE) return { text: t, truncated: false };
  let s = [...t].slice(0, MAX_TITLE).join('');
  s = s.replace(/[（(][^（()）]*$/, '').trim();
  return { text: s, truncated: true };
}

// 话题：固定 6 个（按真实浏览量排序）+ 当天 4 个姓氏，硬上限 10 个
function buildTopics(d) {
  let views = {};
  try { views = Object.fromEntries((JSON.parse(fs.readFileSync(TOPIC_FILE, 'utf8')).topics || []).map(t => [t.name, t.views])); } catch { }
  const fixed = [...FIXED_TOPICS].sort((a, b) => (views[b] || 0) - (views[a] || 0));
  const surnames = [...(d.surname || '')].map(c => c + '氏');
  const list = [...fixed, ...surnames].slice(0, MAX_TOPICS);
  return { list, fixed, surnames, viewsOf: fixed.map(t => [t, views[t] || null]) };
}

// 正文：剥掉 md 里自带的话题行（统一由脚本生成），再附加精选话题
function buildBody(d, topics) {
  const lines = d.body.split('\n').filter(l => !/^\s*#/.test(l)).join('\n').replace(/\n{3,}/g, '\n\n').trimEnd();
  return lines + '\n\n' + topics.list.map(t => '#' + t).join(' ');
}

async function main() {
  const day = todayDay();
  if (!day) return fail({ error: 'NO_DAY', hint: '今天不在 D01–D25 窗口内，或 --day 指定的文件不存在' });
  const d = parseDay(day);
  if (!d) return fail({ error: 'NO_DAY_FILE', day });
  // 图 1 = 封面（v2 版式），其后才是 4 张单字卡
  const coverName = `${d.day}-${d.surname}-封面-1179x1572.png`;
  const coverPath = path.join(COVER_DIR, coverName);
  if (!fs.existsSync(coverPath)) return fail({
    error: 'COVER_MISSING', cover: coverName,
    hint: '先跑 gen-cover-v2.py --day ' + d.day,
  });
  const files = [coverPath, ...d.imgs.map(n => path.join(IMG_DIR, n))];
  const missing = files.filter(f => !fs.existsSync(f));
  if (missing.length) return fail({ error: 'IMG_MISSING', missing });
  if (!d.title || !d.body) return fail({ error: 'PARSE_FAIL', day: d.day, title: !!d.title, body: !!d.body });

  const t = fitTitle(d.title);
  const topics = buildTopics(d);
  const body = buildBody(d, topics);

  // —— 干跑：只看算出来的内容，不碰浏览器 ——
  if (MODE === 'dry') return dump({
    stage: 'dry', day: d.day, file: d.file,
    title: t.text, titleLen: [...t.text].length, titleTruncated: t.truncated,
    cover: coverName, imgs: d.imgs, uploadOrder: files.map(f => path.basename(f)),
    topics: topics.list, topicViews: topics.viewsOf,
    bodyLen: [...body].length, body,
  });

  // —— 幂等：同一篇已存过就不再存 ——
  let log = {};
  try { log = JSON.parse(fs.readFileSync(LOG_FILE, 'utf8')); } catch { }
  if (log[day] && !DAY_ARG) return dump({ stage: 'already-saved', day, at: log[day].at });

  let list;
  try { list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); }
  catch { return fail({ error: 'NO_DEBUG_PORT', hint: `Chrome 未以 --remote-debugging-port=${PORT} 启动` }); }

  let page = list.find(t2 => t2.type === 'page' && /xiaohongshu\.com/.test(t2.url || ''));
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

  if (MODE === 'probe') return dump(await ev(PROBE_JS));

  // —— 1. 上传图片（进入编辑态后标题/正文框才出现）——
  if (MODE !== 'fix') {
    await send('DOM.enable');
    const doc = await send('DOM.getDocument', { depth: -1 });
    const rootId = doc.result?.root?.nodeId;
    const q = await send('DOM.querySelector', { nodeId: rootId, selector: 'input.upload-input' });
    const inputId = q.result?.nodeId;
    if (!inputId) return fail({ error: 'NO_UPLOAD_INPUT', hint: '没找到 input.upload-input，页面结构可能已变' });
    await send('DOM.setFileInputFiles', { files, nodeId: inputId });
    await sleep(15000);
    if (MODE === 'upload') return dump({ stage: 'uploaded', day: d.day, count: files.length, ...JSON.parse(await ev(PROBE_JS) || '{}') });
  }

  // —— 2. 标题（先清空，再插入，截断到 22 字）——
  // 🔴 2026-10-22 踩坑：只 .click() 不够 —— Input.insertText 发给的是
  //    document.activeElement，ProseMirror 的 div 被 click 后**不一定成为 activeElement**，
  //    结果正文被整个塞进了标题框。必须 focus() 后**校验 activeElement 真的是它**再插字。
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

  // —— 3. 正文（清空 → focus 校验 → 插入，话题已在正文末尾）——
  const clearBodyJs = `(()=>{const b=document.querySelector(${JSON.stringify(BODY_SEL)}); if(!b) return 'NO'; b.focus();
    document.execCommand('selectAll'); document.execCommand('delete');
    return document.activeElement===b ? 'OK' : 'NOTFOCUSED';})()`;
  const cb = await ev(clearBodyJs);
  if (cb !== 'OK') return fail({ error: 'NO_BODY_FOCUS', got: cb });
  await send('Input.insertText', { text: body });
  await sleep(6000);

  // —— 4. 选合集「第七境 百家姓系列」——
  // 🔴 2026-10-26 重写：旧版用 el.click() 点最小节点，D01–D05 实测**一次都没选中**
  //    （回读仍是「加入合集 … 选择合集」）。新版：开弹层 → 按标签优先级挑候选行 →
  //    **真实鼠标事件**点中心点（reds/React 组件常不吃 el.click()）→ 逐个候选尝试并回读校验。
  //    ⚠️ 不点任何「确定/完成」类按钮：发布页上有真·发布按钮，误点是不可逆对外动作。
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
      .filter(x=>x.offsetParent && String(x.innerText||'').trim().includes('百家姓'))
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
    if (/百家姓/.test(collNow) && !/选择合集/.test(collNow)) { pickColl = 'OK:' + c.txt; break; }
    pickColl = 'CLICKED_NOT_APPLIED:' + c.txt;
  }

  // —— 5. 原创声明 / 内容含 AI 合成 ——
  // 🔴 2026-11-02 推翻旧结论：不是「点不动」，是**点错了目标**。
  //    应点 `.d-switch-simulator`（开关本体）；`.custom-switch-card` 是整张卡片（308×44），不响应点击。
  //    状态看 class 是否含 checked —— ⚠️ `unchecked` 也含 checked 子串，必须用 \b 边界。
  //    技术依据 `11-运营/小红书定时发布-技术发现-20261102.md`。
  const SW_ORIGINAL = 'div.original-wrapper .d-switch-simulator';
  const SW_POSTTIME = 'div.post-time-wrapper .d-switch-simulator';
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

  // AI 合成声明：⚠️ 下拉会因焦点丢失自动关闭 ⇒ 打开 + 选择必须在同一串连续动作里完成
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

  // —— 5.5 定时发布（2026-11-03 新增）——
  // 用户 2026-11-03 决策：晨检自动存草稿 + **自动设好定时发布**，人只负责点「提交」。
  // ⏰ 默认当天 20:03（--time=HH:MM 可改）。若目标时刻已过或不足 30 分钟 ⇒ 自动顺延次日。
  // ⚠️ 分钟列无首尾 padding ⇒ 「00」无法居中会 snap 到 03，**设不出整点**，属平台限制。
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

  const timeSw = await flipSwitch(SW_POSTTIME);
  const sched = { switch: timeSw.state, target: schedTarget };
  if (timeSw.state === 'ON' || timeSw.state === 'ALREADY_ON') {
    sched.picker = await ev("(()=>{const w=document.querySelector('div.post-time-wrapper'); if(!w) return 'NO_WRAP';"
      + " const i=w.querySelector('input.d-text'); if(!i) return 'NO_INPUT';"
      + " i.scrollIntoView({block:'center'}); i.click(); return 'OK';})()");
    await sleep(2000);
    // 日期格：叶子文本 == 目标日，排除跨月/禁用的 prev/next/other/disabled
    const cellRaw = await ev("(()=>{const pop=document.querySelector('.post-time-date-picker-popover')||document.body;"
      + " const cs=Array.from(pop.querySelectorAll('*')).filter(e=>e.children.length===0"
      + " && !/prev|next|other|disabled/i.test(String(e.className))"
      + " && (e.innerText||'').trim()===" + JSON.stringify(sDay) + ");"
      + " if(!cs.length) return 'NO_CELL'; const r=cs[0].getBoundingClientRect();"
      + " return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)});})()");
    if (cellRaw && String(cellRaw)[0] === '{') { const b = JSON.parse(cellRaw); await mouseClick(b.x, b.y); await sleep(1500); sched.day = 'CLICKED'; }
    else sched.day = String(cellRaw);
    // 时间列：bar[0]=小时 / bar[1]=分钟 —— 必须「scrollTop 居中 + 轻触 snap」才生效
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

  // —— 6. 验证 + 落日志 ——
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
    stage: 'draft-saved', day: d.day, file: d.file,
    title: t.text, titleLen: [...t.text].length, titleTruncated: t.truncated,
    topics: topics.list, topicViews: topics.viewsOf,
    collection: collNow.includes('百家姓') && !/选择合集/.test(collNow) ? COLLECTION : ('未选中:' + collNow),
    collectionOpened: openColl, collectionPicked: pickColl, collectionTried: tried,
    original: originalSw.state,
    aiDeclare: aiRes,
    schedule: sched,
    manual: ['点「发布笔记」提交（提交按钮自动化定位不到，永远人工点）'],
    manualNote: '原创声明不随草稿保存：若中途重开过草稿箱，提交前需当场重勾',
    ...v,
  });
}

main().catch(e => fail({ error: 'EXCEPTION', msg: String(e) }));
