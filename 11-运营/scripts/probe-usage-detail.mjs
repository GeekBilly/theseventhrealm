// 一次性探针：拉今天（或指定日期）的逐条扣分明细，按模型/场景聚合
// 用法：node probe-usage-detail.mjs [端口，默认 9222] [日期，默认今天]
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.argv[2] || '9222';
const today = process.argv[3] || '';

const PAGE_JS = `
(async () => {
  const base = 'https://www.workbuddy.cn';
  const post = async (p, b) => {
    const r = await fetch(base + p, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      credentials: 'include', body: JSON.stringify(b)
    });
    return await r.json();
  };
  try {
    const pad = n => String(n).padStart(2, '0');
    const fmt = d => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    const day = '${today}' || fmt(new Date());
    const start = day + ' 00:00:00', end = day + ' 23:59:59';
    let all = [], totalRows = 0;
    for (let page = 1; page <= 10; page++) {
      const u = await post('/billing/meter/get-user-request-usage', {
        PageNum: page, PageSize: 200, StartTime: start, EndTime: end
      });
      const d = (u.data && u.data.data) || [];
      totalRows = (u.data && u.data.total) || 0;
      all = all.concat(d);
      if (!d.length || all.length >= totalRows) break;
    }
    return JSON.stringify({ day, totalRows, rows: all });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String(e && e.message || e) });
  }
})()
`;

const out = (o) => { console.log(typeof o === 'string' ? o : JSON.stringify(o)); process.exit(0); };
const fail = (o) => { console.log(JSON.stringify(o)); process.exit(1); };

async function main() {
  let list;
  try {
    const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
    list = await r.json();
  } catch {
    return fail({ error: 'NO_DEBUG_PORT', hint: `Chrome 未以 --remote-debugging-port=${PORT} 启动` });
  }
  const page = list.find(t => t.type === 'page' && /workbuddy\.cn\/profile\/plans-usage/.test(t.url || ''));
  if (!page) return fail({ error: 'NO_LOGGED_IN_TAB', hint: '没找到 plans-usage 标签' });

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws error')); });
  let id = 0;
  const send = (method, params) => new Promise((resolve) => {
    const myId = ++id;
    const h = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === myId) { ws.removeEventListener('message', h); resolve(m); }
    };
    ws.addEventListener('message', h);
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  const r = await send('Runtime.evaluate', { expression: PAGE_JS, awaitPromise: true, returnByValue: true });
  ws.close();
  if (r.result?.exceptionDetails) return fail({ error: 'EVAL_EXCEPTION' });
  const v = r.result?.result?.value;
  out(v);
}
main().catch(e => fail({ error: 'SCRIPT_ERROR', raw: String(e).slice(0, 200) }));
