// 给常驻 Chrome 的活动标签截一张图（用于首次扫码登录）
// 用法：node fetch-credits-shot.mjs [端口] [输出路径]

const PORT = process.argv[2] || '9222';
const OUT = process.argv[3] || '/tmp/wb-login-qr.png';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

import fs from 'node:fs';

const r0 = await fetch(`http://127.0.0.1:${PORT}/json/list`);
const list = await r0.json();
const page = list.find(t => t.type === 'page' && /workbuddy\.cn/.test(t.url || ''))
           || list.find(t => t.type === 'page' && !/^chrome|extension/.test(t.url || ''));
if (!page) { console.error('NO_PAGE'); process.exit(1); }

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws')); });

let id = 0;
const send = (method, params) => new Promise((resolve) => {
  const myId = ++id;
  const h = (ev) => { const m = JSON.parse(ev.data); if (m.id === myId) { ws.removeEventListener('message', h); resolve(m); } };
  ws.addEventListener('message', h);
  ws.send(JSON.stringify({ id: myId, method, params }));
});

await send('Page.enable', {});
await sleep(4000);
const shot = await send('Page.captureScreenshot', { format: 'png' });
ws.close();

const b64 = shot.result?.data;
if (!b64) { console.error('SHOT_FAILED'); process.exit(1); }
fs.writeFileSync(OUT, Buffer.from(b64, 'base64'));
console.error('已截图 → ' + OUT + ' (' + page.url.slice(0, 70) + ')');
