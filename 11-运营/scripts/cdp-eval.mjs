// 在指定标签页上执行一段自定义 JS（用于精确读取选中态 / 必填未完成项）
// 用法：node cdp-eval.mjs <端口> <url正则> <js文件路径>
const fs = await import('node:fs');

const PORT = process.argv[2] || '9222';
const RE = new RegExp(process.argv[3] || '.');
const JSF = process.argv[4];

const out = (o) => { console.log(JSON.stringify(o, null, 2)); process.exit(0); };
const fail = (o) => { console.log(JSON.stringify(o, null, 2)); process.exit(1); };

async function main() {
const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const page = list.find(t => t.type === 'page' && RE.test(t.url || ''));
if (!page) return fail({ error: 'NO_MATCH_TAB', tabs: list.filter(t => t.type === 'page').map(t => t.url) });

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = () => j(new Error('ws')); });
let id = 0;
const send = (method, params) => new Promise((resolve) => {
  const i = ++id;
  const h = (ev) => { const m = JSON.parse(ev.data); if (m.id === i) { ws.removeEventListener('message', h); resolve(m); } };
  ws.addEventListener('message', h);
  ws.send(JSON.stringify({ id: i, method, params }));
});

const r = await send('Runtime.evaluate', {
  expression: fs.readFileSync(JSF, 'utf8'),
  awaitPromise: true,
  returnByValue: true,
});
ws.close();
if (r.result?.exceptionDetails) return fail({ error: 'EVAL_ERR', raw: JSON.stringify(r.result.exceptionDetails).slice(0, 400) });
out(r.result?.result?.value);
}

main().catch(e => fail({ error: 'SCRIPT_ERROR', raw: String(e).slice(0, 300) }));
