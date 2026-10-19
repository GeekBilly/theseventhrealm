// 抖音创作者中心 · 每日数据采集（CDP，复用已登录的 Chrome）
//
// 为什么必须每天采：抖音数据中心只展示「近 7 天 / 近 30 天」滚动窗口，
// 断一天就永久缺一天，跟 Cloudflare 分析、小红书一个道理。
//
// 用法：node dy-stats.mjs [端口，默认 9226]
// 产出：
//   stdout                    单行 JSON
//   11-运营/data/dy-stats.json    最新快照（看板消费）
//   11-运营/data/dy-账号数据.csv   每日追加（按日期 upsert）
//   11-运营/data/dy-作品.csv       作品明细（按 标题 upsert）
//
// 前提：Chrome 已起在 9226 且 creator.douyin.com 已登录。
//      没登录/没开端口 → 输出 {"error":"NO_DY_TAB"} 并 exit 1，调用方直接降级。
//
// ⚠️ 路由坑（实测）：只有 /creator-micro/data-center/operation 有数据，
//    /data-center/content-data 是空路由（渲染不出东西），别猜别的路径。
// ⚠️ 解析坑：三个区块用同一个标签名（如「粉丝净增」总览区和粉丝区都有），
//    必须先按「数据总览 / 作品数据 / 粉丝数据」切成三段，再在段内按
//    「标签行 → 下一行就是值」取值，不能全文 match。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const DATA = path.join(ROOT, '11-运营', 'data');
const PORT = process.argv[2] || '9226';

const URL_OP = 'https://creator.douyin.com/creator-micro/data-center/operation';

const dump = (o) => { console.log(JSON.stringify(o)); process.exit(0); };
const fail = (o) => { console.log(JSON.stringify(o)); process.exit(1); };

const PAGE_JS = `(() => { try { return JSON.stringify({ ok:true, url: location.href, text: document.body.innerText || '' }); } catch(e) { return JSON.stringify({ ok:false, err:String(e) }); } })()`;

async function main() {
  let list;
  try {
    list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  } catch {
    return fail({ error: 'NO_DEBUG_PORT', hint: `Chrome 未以 --remote-debugging-port=${PORT} 启动` });
  }
  const page = list.find(t => t.type === 'page' && /creator\.douyin\.com/.test(t.url || ''));
  if (!page) {
    return fail({
      error: 'NO_DY_TAB',
      hint: '没找到抖音标签，请先开 Chrome（9226）并登录 creator.douyin.com',
      tabs: list.filter(t => t.type === 'page').map(t => (t.url || '').slice(0, 80)),
    });
  }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('ws error')); });
  let id = 0;
  const send = (method, params) => new Promise((resolve) => {
    const myId = ++id;
    const h = (ev) => { const m = JSON.parse(ev.data); if (m.id === myId) { ws.removeEventListener('message', h); resolve(m); } };
    ws.addEventListener('message', h);
    ws.send(JSON.stringify({ id: myId, method, params }));
  });

  await send('Page.navigate', { url: URL_OP });
  await new Promise(r => setTimeout(r, 9000));
  const r = await send('Runtime.evaluate', { expression: PAGE_JS, returnByValue: true });
  ws.close();

  const v = r.result?.result?.value;
  let text = '';
  try { const o = JSON.parse(v || '{}'); if (o.ok) text = o.text; } catch { /* 掉登录 */ }
  if (!text || text.length < 200) {
    return fail({ error: 'EMPTY_PAGE', hint: '数据中心页没取到文本，多半是掉登录了（或页面未渲染完）' });
  }

  // ---------- 解析 ----------
  const lines = text.split('\n').map(x => x.trim()).filter(Boolean);
  const idx = (label) => lines.indexOf(label);
  const cut = (a, b) => {
    const i = idx(a);
    if (i < 0) return [];
    const j = b ? idx(b) : lines.length;
    return lines.slice(i, j < 0 ? lines.length : j);
  };
  // 段内取值。⚠️ 两种排版都遇到过得兼容：
  //   总览区是「播放量 307」同行；作品区是「投稿量 \n 16」分两行。
  const grab = (seg, label) => {
    for (let i = 0; i < seg.length; i++) {
      const l = seg[i];
      if (l === label) return seg[i + 1] ?? null;
      if (l.startsWith(label)) {
        const rest = l.slice(label.length).trim();
        if (rest) return rest;
        return seg[i + 1] ?? null;
      }
    }
    return null;
  };
  const num = (s) => {
    if (s == null) return null;
    const m = String(s).match(/-?[\d,，.]+/);
    return m ? Number(m[0].replace(/[,，]/g, '')) : null;
  };
  const raw = (s) => (s == null ? null : String(s));
  const periodOf = (seg) => {
    for (let i = 0; i < seg.length; i++) {
      const m = seg[i].match(/统计周期[：:]?\s*([\d-]+\s*至\s*[\d-]+)/);
      if (m) return m[1].replace(/\s/g, '');
    }
    return null;
  };

  const segOv = cut('数据总览', '播放量分析');
  const segCt = cut('作品数据', '粉丝数据');
  const segFn = cut('粉丝数据', null);

  // 近 7 日总览
  const period = periodOf(segOv);
  const overview = {
    plays: num(grab(segOv, '播放量')),
    interactRate: raw(grab(segOv, '互动率')),
    finishRate: raw(grab(segOv, '完播率')),
    works: num(grab(segOv, '作品数')),
    fanNet: num(grab(segOv, '粉丝净增')),
  };
  // 同类作者百分位（总览页只给播放量这一句）
  const pct = (() => {
    const m = text.match(/您的视频播放量为\s*([\d,，]+)，高于\s*([\d.]+)%的同类创作者/);
    return m ? { plays: num(m[1]), higherThan: Number(m[2]) } : null;
  })();

  // 作品数据（默认 tab，可能是近 7 日也可能是近 30 日，以页上 period 为准）
  const content = {
    period: periodOf(segCt),
    posted: num(grab(segCt, '投稿量')),
    plays: num(grab(segCt, '总播放量')),
    likes: num(grab(segCt, '总点赞量')),
    shares: num(grab(segCt, '总分享量')),
    comments: num(grab(segCt, '总评论量')),
    finish5s: raw(grab(segCt, '5秒完播率')),
    bounce2s: raw(grab(segCt, '2秒跳出率')),
    coverCtr: raw(grab(segCt, '封面点击率')),
    avgPlay: raw(grab(segCt, '平均播放时长')),
  };

  // 粉丝数据（近 7 日）
  const fans = {
    period: periodOf(segFn),
    total: num(grab(segFn, '总粉丝量')),
    net: num(grab(segFn, '粉丝净增')),
    gained: num(grab(segFn, '吸粉量')),
    lost: num(grab(segFn, '脱粉量')),
    returning: num(grab(segFn, '回访粉丝量')),
  };

  // 播放量贡献 TOP3：锚点「7日新增播放量」→ 上一行标题 / 下一行数值
  const videos = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i] !== '7日新增播放量') continue;
    const title = (lines[i - 1] || '').replace(/^(查看所有作品|播放量贡献TOP3)$/, '').trim();
    const val = num(lines[i + 1]);
    if (!title || val == null) continue;
    videos.push({ title: title.slice(0, 80), plays7d: val });
  }

  const today = new Date();
  const dstr = today.toISOString().slice(0, 10);
  const out = {
    ok: true,
    fetchedAt: `${dstr} ${today.toTimeString().slice(0, 5)}`,
    date: dstr,
    period, overview, pct, content, fans,
    videos, videoCount: videos.length,
  };

  // ---------- 落盘 ----------
  fs.mkdirSync(DATA, { recursive: true });
  fs.writeFileSync(path.join(DATA, 'dy-stats.json'), JSON.stringify(out, null, 2), 'utf8');

  const acctCsv = path.join(DATA, 'dy-账号数据.csv');
  const acctHeader = '日期,统计周期7天,播放量,互动率,完播率,作品数,粉丝净增,周期作品,投稿量,总播放量,总点赞,总分享,总评论,5秒完播率,2秒跳出率,封面点击率,平均播放时长,总粉丝量,吸粉量,脱粉量,回访粉丝量';
  const acctRow = [dstr, period || '', overview.plays ?? '', overview.interactRate ?? '', overview.finishRate ?? '',
    overview.works ?? '', overview.fanNet ?? '', content.period || '', content.posted ?? '', content.plays ?? '',
    content.likes ?? '', content.shares ?? '', content.comments ?? '', content.finish5s ?? '', content.bounce2s ?? '',
    content.coverCtr ?? '', content.avgPlay ?? '', fans.total ?? '', fans.gained ?? '', fans.lost ?? '', fans.returning ?? ''].join(',');
  upsertCsv(acctCsv, acctHeader, acctRow, 0);

  const vidCsv = path.join(DATA, 'dy-作品.csv');
  const vidHeader = '采集日,标题,7日新增播放量';
  for (const v of videos) {
    upsertCsv(vidCsv, vidHeader, [dstr, csv(v.title), v.plays7d ?? ''].join(','), -1, csv(v.title));
  }

  dump(out);
}

function csv(s) { return /[",\n]/.test(String(s)) ? '"' + String(s).replace(/"/g, '""') + '"' : String(s); }

function upsertCsv(file, header, row, keyIdx, keyVal) {
  let lines = [];
  if (fs.existsSync(file)) lines = fs.readFileSync(file, 'utf8').split('\n').filter(x => x.trim());
  if (!lines.length) lines = [header];
  const key = keyVal !== undefined ? keyVal : String(row.split(',')[0]);
  const i = lines.findIndex((l, ix) => ix > 0 && l.split(',')[1] === key);
  if (i > 0) lines[i] = row; else lines.push(row);
  fs.writeFileSync(file, lines.join('\n') + '\n', 'utf8');
}

main().catch(e => fail({ error: 'SCRIPT_ERROR', raw: String(e).slice(0, 200) }));
