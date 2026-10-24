// 1024 造物挑战 · 活动页投稿表单「填值」（CDP，复用 9226 Chrome）
//   --dry             只读表单结构（字段清单），不写任何值
//   --shot --out=路径  填完后截全页图
// 🔴 永不点「提交」：投稿是对外不可逆动作，最后一步永远留给人。
import fs from 'node:fs';

const PORT = '9226';
const FORM_URL = 'https://www.workbuddy.link/p/8QYARuAmZ9RgQty3FSzNUs';
const DRY = process.argv.includes('--dry');
const SHOT = process.argv.includes('--shot');
const OUT = (process.argv.find(a => a.startsWith('--out=')) || '--out=/tmp/wb-contest.png').slice(6);

// —— 投稿内容（与 投稿材料-1024造物挑战.md 一致）——
const V = {
  slogan: '这个 1024，我做了一个百家姓壁纸生成器，让每个姓都能领回一张三千年的手机壁纸。',
  name: '百家姓 · 姓氏壁纸生成器',
  author: '第七境',
  link: 'https://baijiaxing-wallpaper.app.workbuddy.host/?sharecode=RVEUDSI4GY',
  intro: '输入你的姓，当场取回这一姓的手机壁纸：卡面一姓四体（草书／行书／隶书／碑刻）依次排开，配竖排注、出处与「第七境」印章，就是公开发布的那一版。覆盖《百家姓》前 100 姓，每姓配一位史有明载的人物（赵·赵武灵王、郑·郑和、萧·萧何……）与它在《百家姓》里的位次；不在 100 姓里的字也能现场排一张简版，人物一行留白待补，绝不瞎编。选 iPhone（1179×2556）或 Android（1080×2400），右侧实时换图，点一下下载无水印 PNG，存进相册即可设为壁纸。全程在浏览器本地完成，输入的字不上传、不留存。适合喜欢传统文化、想把姓氏放进日常的手机用户。',
};
const SHOTS = [
  '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/06-姓氏线/应用-百家姓卡/投稿截图-iPhone版.png',
  '/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/06-姓氏线/应用-百家姓卡/投稿截图-Android版.png',
];

const sleep = ms => new Promise(r => setTimeout(r, ms));
const dump = o => { console.log(JSON.stringify(o, null, 1)); process.exit(0); };
const fail = o => { console.log(JSON.stringify({ ok: false, ...o }, null, 1)); process.exit(1); };

const PROBE_JS = `(()=>{
  const out=[];
  const labelOf = el => {
    let p=el, acc=[];
    for(let i=0;i<5 && p;i++){
      const t=(p.textContent||'').trim();
      if(t && t.length<300 && p!==el){ const first=t.split('\\n')[0].trim(); if(first) acc.unshift(first); }
      p=p.parentElement;
    }
    return acc[0]||el.getAttribute('placeholder')||el.getAttribute('aria-label')||'';
  };
  document.querySelectorAll('input,textarea,[contenteditable="true"],select').forEach((el,i)=>{
    const r=el.getBoundingClientRect();
    if(r.width<2||r.height<2) return;
    const cs=getComputedStyle(el); if(cs.display==='none'||cs.visibility==='hidden') return;
    out.push({i, tag:el.tagName.toLowerCase(), type:el.type||null, ce:el.isContentEditable,
      max:el.maxLength>0?el.maxLength:null, ph:el.getAttribute('placeholder')||'',
      val:(el.value||el.textContent||'').slice(0,40), label:labelOf(el).slice(0,70)});
  });
  const btns=[];
  document.querySelectorAll('button,[role=button]').forEach(b=>{
    const r=b.getBoundingClientRect(); if(r.width<2||r.height<2) return;
    const t=(b.textContent||'').trim().slice(0,20); if(t) btns.push(t);
  });
  return {fields:out, buttons:[...new Set(btns)].slice(0,25),
    text:(document.body.innerText||'').replace(/\\n{2,}/g,'\\n').slice(0,1200)};
})()`;

// 连一个 target；🔴 表单在**跨域 OOPIF**（独立进程）里，getFrameTree 看不到，
//    必须 Target.attachToTarget + flatten 拿 sessionId，后续命令全部带上它。
async function attach(t) {
  let ws;
  try { ws = new WebSocket(t.webSocketDebuggerUrl); } catch { return null; }
  try { await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws')); }); } catch { return null; }
  let id = 0;
  const send = (m, p, sid) => new Promise(res => {
    const my = ++id;
    const h = ev => { const o = JSON.parse(ev.data); if (o.id === my && (sid ? o.sessionId === sid : !o.sessionId)) { ws.removeEventListener('message', h); res(o); } };
    ws.addEventListener('message', h);
    ws.send(JSON.stringify({ id: my, method: m, params: p, ...(sid ? { sessionId: sid } : {}) }));
  });
  await send('Page.enable'); await send('DOM.enable');
  await send('Target.setDiscoverTargets', { discover: true });
  await sleep(600);
  const info = await send('Target.getTargets');
  const kids = (info?.result?.targetInfos || []).filter(x => x.type === 'iframe' && /codebuddy\.work|workbuddy/.test(x.url || ''));
  if (!kids.length) { try { ws.close(); } catch { } return null; }
  const at = await send('Target.attachToTarget', { targetId: kids[0].targetId, flatten: true });
  const SID = at?.result?.sessionId;
  if (!SID) { try { ws.close(); } catch { } return null; }
  await send('Runtime.enable', {}, SID);
  await send('DOM.enable', {}, SID);
  await sleep(800);
  return { ws, send, SID, frameUrl: kids[0].url };
}

async function pageTargets() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  return list.filter(x => x.type === 'page' && /workbuddy\.link/.test(x.url || ''));
}

async function main() {
  let list;
  try { list = await pageTargets(); }
  catch { return fail({ error: 'NO_DEBUG_PORT', hint: 'Chrome 未以 --remote-debugging-port=9226 启动' }); }

  let ctx = null;
  for (const t of list) { ctx = await attach(t); if (ctx) break; }
  if (!ctx) {
    // 没有已开的活动页 ⇒ 新建一个，等加载后再试一轮
    await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(FORM_URL)}`, { method: 'PUT' });
    await sleep(10000);
    for (const t of await pageTargets()) { ctx = await attach(t); if (ctx) break; }
  }
  if (!ctx) return fail({ error: 'NO_FORM_CTX', hint: '找不到装着表单的 iframe；可能需要先登录 WorkBuddy' });

  const { send, SID } = ctx;
  const ev = async expr => (await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true }, SID))?.result?.result?.value;

  // 活动正文是作品墙；表单要先把「✏️ 发布作品」点开才出现
  const opened = await ev(`(()=>{
    const b=[...document.querySelectorAll('button,[role=button],a,div')]
      .find(e=>/^\\s*\\S*\\s*发布作品\\s*$/.test((e.textContent||'').trim()));
    if(!b) return 'NO_PUBLISH_BTN';
    b.scrollIntoView({block:'center'}); b.click(); return 'CLICKED';
  })()`);
  if (opened === 'NO_PUBLISH_BTN') return fail({ error: 'NO_PUBLISH_BTN', hint: '页面上没有「发布作品」入口，可能需要先登录 WorkBuddy' });
  await sleep(5000);

  if (DRY) return dump({ frameUrl: ctx.frameUrl, opened, ...(await ev(PROBE_JS)) });

  const before = await ev(PROBE_JS);
  // 🔴 定位一律按 placeholder（稳定唯一），不要按 DOM 索引：
  //    点开表单后列表会同义重排，索引会串位（曾把昵称写进搜索框）。
  const setValuePh = (phSub, text) => ev(`(()=>{
    const el=[...document.querySelectorAll('input,textarea')].find(e=>(e.placeholder||'').includes(${JSON.stringify(phSub)}));
    if(!el) return 'NO_EL';
    const proto = el.tagName==='TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(el, ${JSON.stringify(text)});
    el.dispatchEvent(new Event('input',{bubbles:true}));
    el.dispatchEvent(new Event('change',{bubbles:true}));
    el.blur();
    return 'SET:'+el.value.length;
  })()`);

  const steps = [];
  const do_ = async (phSub, text, tag) => {
    steps.push({ tag, result: await setValuePh(phSub, text) });
    await sleep(300);
  };

  await do_('这个 1024，我做了一个待办整理助手', V.slogan, '01 我的作品宣言');
  await do_('给你的作品取个名字', V.name, '02 作品名称');
  await do_('请输入昵称', V.author, '03 作者昵称');
  await do_('介绍谁会使用你的作品', V.intro, '05 作品介绍');
  await do_('可以公开打开并体验作品的链接', V.link, '06 体验链接');
  await do_('搜索作品、创作者、标签', '', '—清理误填的搜索框');

  const formPick = await ev(`(()=>{
    const c=[...document.querySelectorAll('label,button,[role=radio],li,span,div')]
      .filter(e=>/^\\s*(网页应用|小程序应用)\\s*$/.test((e.textContent||'').trim()));
    const web=c.find(e=>/网页应用/.test(e.textContent));
    if(!web) return 'NO_OPTION';
    const t=web.querySelector('input')||web; t.scrollIntoView({block:'center'}); t.click();
    return 'CLICKED';
  })()`);
  steps.push({ tag: '作品形态', result: formPick });

  // 给 file input 打临时属性，保证 DOM.querySelector 一定能命中
  const upInfo = await ev(`(()=>{
    const f=[...document.querySelectorAll('input[type=file]')];
    if(!f.length) return 'NO_FILE_INPUT';
    f[0].setAttribute('data-autoup','1');
    return {n:f.length, accept:f[0].accept, multiple:f[0].multiple};
  })()`);
  if (upInfo?.n) {
    const docRes = await send('DOM.getDocument', { depth: 0 }, SID);
    const rootId = docRes?.result?.root?.nodeId;
    if (!rootId) {
      steps.push({ tag: '截图上传', result: 'NO_DOC_ROOT', raw: JSON.stringify(docRes).slice(0, 200) });
    } else {
      const q = await send('DOM.querySelector', { nodeId: rootId, selector: '[data-autoup="1"]' }, SID);
      const nodeId = q?.result?.nodeId || 0;
      if (nodeId) {
        await send('DOM.setFileInputFiles', { files: SHOTS, nodeId }, SID);
        steps.push({ tag: '截图上传', result: `已传 ${SHOTS.length} 张` });
      } else steps.push({ tag: '截图上传', result: 'NO_FILE_NODE' });
    }
    await sleep(3500);
  } else steps.push({ tag: '截图上传', result: upInfo });

  if (SHOT) {
    // 截的是外层面面记录为准；contentinside iframe 无法直接 capture ⇒ 取整页截图
    const s = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    fs.writeFileSync(OUT, Buffer.from(s.result.data, 'base64'));
  }

  const after = await ev(PROBE_JS);
  dump({
    ok: true, stage: 'filled', note: '已填完，**未点提交**，请你核完自己点',
    steps,
    fields: after.fields.map(f => ({ label: f.label.slice(0, 24), len: (f.val || '').length, val: (f.val || '').slice(0, 24) })),
    screenshot: SHOT ? OUT : null,
  });
}

main().catch(e => fail({ error: 'EXCEPTION', detail: String(e) }));
