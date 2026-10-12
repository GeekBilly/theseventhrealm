// 通用 CDP 动作序列引擎
// 用法：node cdp-act.mjs <端口> <url正则> <actions.json>
// actions 支持的 do： eval(用 js/file) | click(sel|text) | dblclick | wait | key | insertText | shot
const fs = await import('node:fs');
const PORT = process.argv[2] || '9222';
const RE = new RegExp(process.argv[3] || '.');
const AF = process.argv[4];

const say = (o) => console.log(JSON.stringify(o, null, 2));

async function main() {
  const actions = JSON.parse(fs.readFileSync(AF, 'utf8'));
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const page = list.find(t => t.type === 'page' && RE.test(t.url || ''));
  if (!page) throw new Error('NO_MATCH_TAB');

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = () => j(new Error('ws')); });
  let id = 0;
  const send = (method, params) => new Promise((resolve) => {
    const i = ++id;
    const h = (ev) => { const m = JSON.parse(ev.data); if (m.id === i) { ws.removeEventListener('message', h); resolve(m); } };
    ws.addEventListener('message', h);
    ws.send(JSON.stringify({ id: i, method, params }));
  });

  const ev = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) throw new Error('EVAL: ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300));
    return r.result?.result?.value;
  };

  const rectOf = async (a) => {
    const js = `(() => {
      const sel = ${JSON.stringify(a.sel || '')}, txt = ${JSON.stringify(a.text || '')};
      let el = sel ? document.querySelector(sel) : null;
      if (!el && txt) {
        el = [...document.querySelectorAll('*')].filter(e => (e.textContent||'').includes(txt) && e.children.length <= ${a.maxKids ?? 3})
              .sort((x,y)=>(x.textContent||'').length-(y.textContent||'').length)[0];
      }
      if (!el) return JSON.stringify({found:false});
      el.scrollIntoView({block:'center', inline:'center'});
      const r = el.getBoundingClientRect();
      const x = r.x + ${a.dx ?? 0} + Math.min(30, r.width/2);
      const y = r.y + ${a.dy ?? 0} + Math.min(12, r.height/2);
      return JSON.stringify({found:true, x:Math.round(x), y:Math.round(y), w:Math.round(r.width), h:Math.round(r.height)});
    })()`;
    return JSON.parse(await ev(js));
  };

  const mouse = async (type, x, y, opts = {}) => send('Input.dispatchMouseEvent', {
    type, x, y, button: opts.button || 'left', clickCount: opts.clickCount || 1, buttons: opts.buttons ?? (type === 'mouseReleased' ? 0 : 1),
  });

  const results = [];
  for (const a of actions) {
    switch (a.do) {
      case 'eval': {
        const v = await ev(fs.readFileSync(a.file, 'utf8'));
        results.push({ do: 'eval', out: v });
        break;
      }
      case 'click':
      case 'dblclick': {
        const r = await rectOf(a);
        if (!r.found) { results.push({ do: a.do, found: false }); break; }
        const n = a.do === 'dblclick' ? 2 : 1;
        for (let i = 1; i <= n; i++) {
          await mouse('mousePressed', r.x, r.y, { clickCount: i });
          await mouse('mouseReleased', r.x, r.y, { clickCount: i });
        }
        if (a.wait) await new Promise(r2 => setTimeout(r2, a.wait));
        results.push({ do: a.do, rect: r });
        break;
      }
      case 'point': {
        await mouse('mousePressed', a.x, a.y, { clickCount: 1 });
        await mouse('mouseReleased', a.x, a.y, { clickCount: 1 });
        if (a.wait) await new Promise(r2 => setTimeout(r2, a.wait));
        results.push({ do: 'point', x: a.x, y: a.y });
        break;
      }
      case 'navigate': {
        await send('Page.enable', {});
        await send('Page.navigate', { url: a.url });
        if (a.wait) await new Promise(r2 => setTimeout(r2, a.wait));
        results.push({ do: 'navigate', url: a.url });
        break;
      }
      case 'wait':
        await new Promise(r2 => setTimeout(r2, a.ms || 500));
        results.push({ do: 'wait', ms: a.ms });
        break;
      case 'key': {
        for (let i = 0; i < (a.times || 1); i++) {
          for (const type of ['keyDown', 'keyUp']) {
            await send('Input.dispatchKeyEvent', {
              type, key: a.key, code: a.key, windowsVirtualKeyCode: a.code || (a.key || 'a').charCodeAt(0),
              nativeVirtualKeyCode: a.code || (a.key || 'a').charCodeAt(0),
            });
          }
        }
        if (a.wait) await new Promise(r2 => setTimeout(r2, a.wait));
        results.push({ do: 'key', key: a.key, times: a.times || 1 });
        break;
      }
      case 'insertText': {
        await send('Input.insertText', { text: a.text });
        if (a.wait) await new Promise(r2 => setTimeout(r2, a.wait || 300));
        results.push({ do: 'insertText', len: (a.text || '').length });
        break;
      }
      case 'shot': {
        await send('Page.enable', {});
        const s = await send('Page.captureScreenshot', { format: 'png' });
        if (s.result?.data) fs.writeFileSync(a.file, Buffer.from(s.result.data, 'base64'));
        results.push({ do: 'shot', file: a.file });
        break;
      }
      default:
        results.push({ do: a.do, skipped: true });
    }
  }
  ws.close();
  say(results);
}

main().catch(e => { say({ error: 'SCRIPT_ERROR', raw: String(e).slice(0, 400) }); process.exit(1); });
