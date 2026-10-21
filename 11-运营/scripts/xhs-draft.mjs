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
  : process.argv.includes('--fix') ? 'fix' : 'draft';
const DAY_ARG = (process.argv.find(a => a.startsWith('--day=')) || '').split('=')[1];

const PUBLISH_URL = 'https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image';
const DRAFT_DIR = path.join(ROOT, '04-市场', '03-推广获客', '姓氏日更-202610');
const IMG_DIR = path.join(ROOT, '02-商品', '06-姓氏线', '成品-手机竖版', '小红书-3x4');
const START_DATE = '2026-10-22';   // D01 的发布日，之后每天 +1

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
  return { day, file, title, imgs, body };
}

function todayDay() {
  if (DAY_ARG) return DAY_ARG.toUpperCase();
  const s = new Date(START_DATE + 'T00:00:00');
  const n = new Date(); const n0 = new Date(n.getFullYear(), n.getMonth(), n.getDate());
  const diff = Math.round((n0 - s) / 86400000);
  if (diff < 0 || diff > 24) return null;
  return 'D' + String(diff + 1).padStart(2, '0');
}

async function main() {
  let list;
  try { list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); }
  catch { return fail({ error: 'NO_DEBUG_PORT', hint: `Chrome 未以 --remote-debugging-port=${PORT} 启动` }); }

  let page = list.find(t => t.type === 'page' && /xiaohongshu\.com/.test(t.url || ''));
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
  // 探测模式且已经在发布页上 → 不重新导航（否则会丢掉刚上传的图片）
  let cur = '';
  try { cur = await ev('location.href'); } catch { }
  if (!((MODE === 'probe' || MODE === 'fix') && /publish\/publish/.test(cur || ''))) {
    await send('Page.navigate', { url: PUBLISH_URL });
    await sleep(8000);
  } else {
    await sleep(1500);
  }

  if (MODE === 'probe') return dump(await ev(PROBE_JS));

  const d = parseDay(todayDay() || '');
  if (!d) return fail({ error: 'NO_DAY', hint: '今天不在 D01–D25 窗口内，或 --day 指定的文件不存在' });
  const files = d.imgs.map(n => path.join(IMG_DIR, n));
  const missing = files.filter(f => !fs.existsSync(f));
  if (missing.length) return fail({ error: 'IMG_MISSING', missing });
  if (!d.title || !d.body) return fail({ error: 'PARSE_FAIL', day: d.day, title: !!d.title, body: !!d.body });

  // —— 1. 上传图片（这时页面才会进入编辑态，标题/正文框才出现）——
  if (MODE !== 'fix') {
  await send('DOM.enable');
  const doc = await send('DOM.getDocument', { depth: -1 });
  const rootId = doc.result?.root?.nodeId;
  const q = await send('DOM.querySelector', { nodeId: rootId, selector: 'input.upload-input' });
  const inputId = q.result?.nodeId;
  if (!inputId) return fail({ error: 'NO_UPLOAD_INPUT', hint: '没找到 input.upload-input，页面结构可能已变' });
  await send('DOM.setFileInputFiles', { files, nodeId: inputId });
  await sleep(15000);   // 4 张图上传 + 平台处理，宁可多等

  if (MODE === 'upload') return dump({ stage: 'uploaded', day: d.day, count: files.length, ...JSON.parse(await ev(PROBE_JS) || '{}') });
  }

  // —— 2. 填标题 ——
  // 小红书发布页没有「存草稿」按钮：上传图片后平台会自动建草稿并自动保存
  // （页面底部显示「编辑于 刚刚」）。所以只需把内容填进去，草稿就成型了。
  //
  // 🔴 2026-10-22 踩坑：只 .click() 不够 —— Input.insertText 发给的是
  //    document.activeElement，ProseMirror 的 div 被 click 后**不一定成为 activeElement**，
  //    结果正文被整个塞进了标题框。必须 focus() 后**校验 activeElement 真的是它**再插字。
  const TITLE_SEL = 'input.d-text[placeholder="填写标题会有更多赞哦"]';
  const BODY_SEL = 'div.tiptap.ProseMirror';
  const focusJs = (sel) => `(()=>{const e=document.querySelector(${JSON.stringify(sel)}); if(!e) return 'NO'; e.scrollIntoView({block:'center'}); e.focus(); return document.activeElement===e ? 'OK' : 'NOTFOCUSED:' + String(document.activeElement && (document.activeElement.className || document.activeElement.tagName));})()`;
  // 每次都先清空标题框（重跑时不会把旧内容顶在前面）
  const clearJs = `(()=>{const e=document.querySelector(${JSON.stringify(TITLE_SEL)}); if(!e) return 'NO'; e.focus(); e.setSelectionRange(0,(e.value||'').length); return String((e.value||'').length);})()`;
  const had = await ev(clearJs);
  if (had === 'NO') return fail({ error: 'NO_TITLE_INPUT' });
  if (Number(had) > 0) {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
    await sleep(500);
  }
  await send('Input.insertText', { text: d.title });
  await sleep(1500);

  // —— 3. 填正文（ProseMirror contenteditable） ——
  const r2 = await ev(focusJs(BODY_SEL));
  if (r2 !== 'OK') return fail({ error: 'NO_BODY_FOCUS', got: r2 });
  await send('Input.insertText', { text: d.body });
  await sleep(8000);   // 等平台自动保存

  // —— 4. 验证：标题/正文是否落上、草稿箱计数、是否显示「编辑于」 ——
  const verify = await ev(`(() => { try {
    const t = document.querySelector('${TITLE_SEL}');
    const b = document.querySelector('div.tiptap.ProseMirror');
    const m = (document.body.innerText||'').match(/草稿箱\\((\\d+)\\)/);
    return JSON.stringify({ title: (t && t.value) || '', bodyLen: ((b && b.innerText) || '').length, draftBox: m ? m[1] : null, autoSaved: /编辑于/.test(document.body.innerText||'') });
  } catch(e) { return JSON.stringify({ err: String(e) }); } })()`);
  return dump({ stage: 'draft-saved', day: d.day, ...JSON.parse(verify || '{}') });
}

main().catch(e => fail({ error: 'EXCEPTION', msg: String(e) }));
