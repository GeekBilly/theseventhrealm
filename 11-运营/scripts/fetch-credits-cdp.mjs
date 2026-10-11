// 通过 Chrome 远程调试端口，在「已登录的那个标签」上取积分。
// 不用 agent-browser：它 connect 后会绑死在一个自己新建的 about:blank 目标上，
// 而 workbuddy.cn 的登录态是按标签页存的（sessionStorage），新标签没有登录态 → 必然失败。
//
// 用法：node fetch-credits-cdp.mjs [端口，默认 9222]
// 输出：单行 JSON（ok/remain/byDay/avg7...）

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.argv[2] || '9222';
const JS_FILE = path.join(__dirname, 'fetch-credits.js');

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

  // 必须挑中真正在 workbuddy.cn 用量页的那个标签
  const page = list.find(t => t.type === 'page' && /workbuddy\.cn\/profile\/plans-usage/.test(t.url || ''));
  if (!page) {
    const any = list.filter(t => t.type === 'page').map(t => (t.url || '').slice(0, 80));
    return fail({
      error: 'NO_LOGGED_IN_TAB',
      hint: '没找到停在 workbuddy.cn/profile/plans-usage 的标签，请在该 Chrome 里打开并登录一次',
      tabs: any,
    });
  }

  const js = fs.readFileSync(JS_FILE, 'utf8');
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

  const r = await send('Runtime.evaluate', {
    expression: js,
    awaitPromise: true,
    returnByValue: true,
  });
  ws.close();

  if (r.result?.exceptionDetails) {
    return fail({ error: 'EVAL_EXCEPTION', raw: JSON.stringify(r.result.exceptionDetails).slice(0, 300) });
  }
  const v = r.result?.result?.value;
  if (v === undefined || v === null) return fail({ error: 'EMPTY_RESPONSE' });

  // 页面里的 JS 返回的是 JSON 字符串，原样透传；不是字符串就自己 stringify
  if (typeof v === 'string') {
    try { out(JSON.stringify(JSON.parse(v))); } catch { out(v); }
  } else {
    out(v);
  }
}

main().catch(e => fail({ error: 'SCRIPT_ERROR', raw: String(e).slice(0, 200) }));
