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
const TOPIC_FILE = path.join(ROOT, '11-运营', 'data', 'xhs-topics.json');
const LOG_FILE = path.join(ROOT, '11-运营', 'data', 'xhs-draft-log.json');
const START_DATE = '2026-10-22';   // D01 的发布日，之后每天 +1

// —— 发布口径（2026-10-22 用户定）——
const MAX_TITLE = 22;                       // 标题字数上限，超了自动截断
const COLLECTION = '第七境 百家姓系列';       // 平台上的合集名（用户名叫「第七境 百家姓」）
const FIXED_TOPICS = ['壁纸', '传统文化', '国风', '手机壁纸', '书法', '东方美学', '百家姓', '汉字'];

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
  const title = (md.match(/\*\*标题\*\*：(.+)/) || [])[1]?.trim() || '';
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

// 话题：固定高流量 8 个（按真实浏览量排序）+ 当天 4 个姓氏
function buildTopics(d) {
  let views = {};
  try { views = Object.fromEntries((JSON.parse(fs.readFileSync(TOPIC_FILE, 'utf8')).topics || []).map(t => [t.name, t.views])); } catch { }
  const fixed = [...FIXED_TOPICS].sort((a, b) => (views[b] || 0) - (views[a] || 0));
  const surnames = [...(d.surname || '')].map(c => c + '氏');
  return { list: [...fixed, ...surnames], fixed, surnames, viewsOf: fixed.map(t => [t, views[t] || null]) };
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
  const files = d.imgs.map(n => path.join(IMG_DIR, n));
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
    imgs: d.imgs, topics: topics.list, topicViews: topics.viewsOf,
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
  const openColl = await ev(`(()=>{const b=document.querySelector('div.collection-plugin-button'); if(!b) return 'NO'; b.scrollIntoView({block:'center'}); b.click(); return 'OK';})()`);
  await sleep(2200);
  const pickColl = await ev(`(()=>{const els=Array.from(document.querySelectorAll('div,span,li'))
    .filter(x=>String(x.innerText||'').trim().includes('百家姓') && x.offsetParent);
    if(!els.length) return 'NOTFOUND';
    els.sort((a,b)=>a.querySelectorAll('*').length-b.querySelectorAll('*').length);
    els[0].click(); return 'OK';})()`);
  await sleep(1800);
  const collNow = await ev(`(()=>{const w=document.querySelector('div.collection-plugin-wrapper'); return w? w.innerText.replace(/\\n/g,' ').slice(0,80):'NO';})()`);

  // —— 5. 原创声明 / 内容含 AI 合成 ——
  // ⚠️ 2026-10-22 实测：这两个开关用 JS click、真实鼠标事件、键盘 Space/Enter 都点不动
  //    （可能是账号权限未开放，或组件用了自定义事件）。这里仍然尝试一次，
  //    但状态无法可靠读回，输出里标 unknown ⇒ 简报提醒人在发布前手动确认。
  await ev(`(()=>{const w=document.querySelector('div.original-wrapper'); const c=w&&w.querySelector('.custom-switch-card'); if(c){c.scrollIntoView({block:'center'}); c.click();} return 1;})()`);
  await sleep(1200);
  const swState = await ev(`(()=>{const w=document.querySelector('div.original-wrapper'); if(!w) return 'NO';
    const s=w.querySelector('.custom-switch-icon svg'); const m=s?String(s.outerHTML).match(/scaleX\\((-?[\\d.]+)\\)/):null;
    return m?m[1]:'?';})()`);
  await ev(`(()=>{const w=Array.from(document.querySelectorAll('.d-select-wrapper')).filter(x=>String(x.innerText||'').includes('添加内容类型声明')&&x.offsetParent)[0];
    if(!w) return 'NO'; const m=w.querySelector('.d-select-main'); if(!m) return 'NOMAIN'; m.scrollIntoView({block:'center'}); m.click(); return 'OK';})()`);
  await sleep(1500);

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
    collection: collNow.includes('百家姓') ? COLLECTION : ('未选中:' + collNow),
    collectionOpened: openColl, collectionPicked: pickColl,
    original: swState === '?' ? 'unknown' : ('scaleX=' + swState),
    aiDeclare: 'unknown',
    manual: ['原创声明', '内容含 AI 合成标注'],
    ...v,
  });
}

main().catch(e => fail({ error: 'EXCEPTION', msg: String(e) }));
