// 通用 CDP 页面读取：连已登录的常驻 Chrome，抓某个标签页的文本 + 截图。
// 用法：node cdp-page-read.mjs <端口> <url正则> [截图输出路径]
// 输出：JSON { title, url, text, tables, shot }
//
// 说明：不新建标签（新建标签会丢登录态），只接管已经打开的那一页。

const PORT = process.argv[2] || '9222';
const URL_RE = new RegExp(process.argv[3] || '.');
const SHOT = process.argv[4] || '';

const out = (o) => { console.log(JSON.stringify(o, null, 2)); process.exit(0); };
const fail = (o) => { console.log(JSON.stringify(o, null, 2)); process.exit(1); };

async function main() {
  let list;
  try {
    list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  } catch {
    return fail({ error: 'NO_DEBUG_PORT', hint: `端口 ${PORT} 上没有 Chrome` });
  }

  const page = list.find(t => t.type === 'page' && URL_RE.test(t.url || ''));
  if (!page) {
    return fail({
      error: 'NO_MATCH_TAB',
      tabs: list.filter(t => t.type === 'page').map(t => (t.url || '').slice(0, 100)),
    });
  }

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

  const evalJs = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) return { __err: JSON.stringify(r.result.exceptionDetails).slice(0, 300) };
    return r.result?.result?.value;
  };

  // 1) 页面基本信息 + 可见文本
  const info = await evalJs(`(() => {
    const t = (document.body && document.body.innerText) || '';
    const rows = [...document.querySelectorAll('table tr')].slice(0, 40).map(tr =>
      [...tr.querySelectorAll('th,td')].map(td => (td.innerText||'').trim().replace(/\\s+/g,' ')).join(' | ')
    );
    return JSON.stringify({
      title: document.title,
      url: location.href,
      textLen: t.length,
      text: t.replace(/\\n{3,}/g,'\\n\\n').slice(0, 8000),
      tableRows: rows,
    });
  })()`);

  let parsed = info;
  if (typeof info === 'string') { try { parsed = JSON.parse(info); } catch { parsed = { raw: info }; } }

  // 2) 截图（有头 Chrome；捕获可视区域）
  let shotPath = null;
  if (SHOT) {
    await send('Page.enable', {});
    const s = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    if (s.result?.data) {
      const fs = await import('node:fs');
      fs.writeFileSync(SHOT, Buffer.from(s.result.data, 'base64'));
      shotPath = SHOT;
    }
  }
  ws.close();

  out({ ...(parsed || {}), shot: shotPath });
}

main().catch(e => fail({ error: 'SCRIPT_ERROR', raw: String(e).slice(0, 300) }));
