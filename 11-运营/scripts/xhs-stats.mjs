// 小红书创作服务平台 · 每日数据采集（CDP，复用已登录的 Chrome）
//
// 为什么必须每天采：小红书数据看板只展示「近 7 天 / 近 30 天」滚动窗口，
// 断一天就永久缺一天，跟 Cloudflare 分析一个道理。
//
// 用法：node xhs-stats.mjs [端口，默认 9226]
// 产出：
//   stdout                    单行 JSON
//   11-运营/data/xhs-stats.json    最新快照（看板消费）
//   11-运营/data/xhs-账号数据.csv   每日追加（按日期 upsert）
//   11-运营/data/xhs-笔记.csv       笔记明细（按 标题+发布时间 upsert）
//
// 前提：Chrome 已用 start-xhs-browser.sh 起在 9226 且已登录。
//      没登录/没开端口 → 输出 {"error":"NO_XHS_TAB"} 并 exit 1，调用方直接降级。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..', '..');
const DATA = path.join(ROOT, '11-运营', 'data');
const PORT = process.argv[2] || '9226';

const URLS = {
  account: 'https://creator.xiaohongshu.com/statistics/account/v2?source=official',
  notes: 'https://creator.xiaohongshu.com/statistics/data-analysis?source=official',
  fans: 'https://creator.xiaohongshu.com/statistics/fans-data?source=official',
};

const dump = (o) => { console.log(JSON.stringify(o)); process.exit(0); };
const fail = (o) => { console.log(JSON.stringify(o)); process.exit(1); };

// —— 页面内执行的取数 JS：把渲染好的文本抓出来，交给 Node 侧解析 ——
const PAGE_JS = `(() => { try { return JSON.stringify({ ok:true, url: location.href, text: document.body.innerText || '' }); } catch(e) { return JSON.stringify({ ok:false, err:String(e) }); } })()`;

async function main() {
  let list;
  try {
    list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  } catch {
    return fail({ error: 'NO_DEBUG_PORT', hint: `Chrome 未以 --remote-debugging-port=${PORT} 启动` });
  }
  const page = list.find(t => t.type === 'page' && /xiaohongshu\.com/.test(t.url || ''));
  if (!page) {
    return fail({
      error: 'NO_XHS_TAB',
      hint: '没找到小红书标签，请先跑 start-xhs-browser.sh 并登录一次',
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

  const visit = async (url) => {
    await send('Page.navigate', { url });
    await new Promise(r => setTimeout(r, 8000));
    const r = await send('Runtime.evaluate', { expression: PAGE_JS, returnByValue: true });
    const v = r.result?.result?.value;
    if (!v) return '';
    try { const o = JSON.parse(v); return o.ok ? o.text : ''; } catch { return ''; }
  };

  const tAccount = await visit(URLS.account);
  const tNotes = await visit(URLS.notes);
  const tFans = await visit(URLS.fans);
  ws.close();

  if (!tAccount && !tNotes && !tFans) {
    return fail({ error: 'EMPTY_PAGE', hint: '三个页面都没取到文本，多半是掉登录了' });
  }

  // ---------- 解析 ----------
  const num = (s) => (s == null ? null : Number(String(s).replace(/[,，\s]/g, '')));
  const first = (re, s) => { const m = s.match(re); return m ? m[1] : null; };

  // 账号诊断（近 7 日）
  const diag = {
    views: num(first(/观看数为\s*([\d,，]+)/, tAccount)),
    newFans: num(first(/涨粉数为\s*(-?[\d,，]+)/, tAccount)),
    profileVisits: num(first(/主页访客数为\s*([\d,，]+)/, tAccount)),
    published: num(first(/发布数为\s*([\d,，]+)/, tAccount)),
    interactions: num(first(/互动数为\s*([\d,，]+)/, tAccount)),
  };

  // 数据总览（近 7 日）
  const period = first(/统计周期\s*([\d-]+\s*至\s*[\d-]+)/, tAccount);
  const overview = {
    exposure: num(first(/曝光数\s*\n?\s*([\d,，]+)/, tAccount)),
    views: num(first(/观看数\s*\n?\s*([\d,，]+)\s*\n?\s*环比/, tAccount)),
    ctr: first(/封面点击率\s*\n?\s*([\d.]+%)/, tAccount),
    avgWatch: first(/平均观看时长\s*\n?\s*([\d.]+\s*(?:分钟|秒))/, tAccount),
    totalWatch: first(/观看总时长\s*\n?\s*([\d.]+\s*(?:分钟|秒))/, tAccount),
    finishRate: first(/视频完播率\s*\n?\s*([\d.]+%)/, tAccount),
  };
  const mom = {
    exposure: first(/曝光数\s*\n?\s*[\d,，]+\s*\n?\s*环比\s*([+\-—]?[\d.]*%?)/, tAccount),
    views: first(/观看数\s*\n?\s*[\d,，]+\s*\n?\s*环比\s*([+\-—]?[\d.]*%?)/, tAccount),
    ctr: first(/封面点击率\s*\n?\s*[\d.]+%\s*\n?\s*环比\s*([+\-—]?[\d.]*%?)/, tAccount),
  };

  // 粉丝
  const fans = {
    total: num(first(/总粉丝数\s*\n?\s*([\d,，]+)/, tFans)),
    added: num(first(/新增粉丝数\s*\n?\s*(-?[\d,，]+)/, tFans)),
    lost: num(first(/流失粉丝数\s*\n?\s*(-?[\d,，]+)/, tFans)),
  };

  // 笔记明细（内容分析页表格）
  const notes = [];
  // 表格是「标题行 \n 发布于xxxx-xx-xx xx:xx \n 指标行」，按行找锚点最稳
  const nl = tNotes.split('\n').map(x => x.trim()).filter(Boolean);
  for (let i = 0; i < nl.length; i++) {
    const anchor = nl[i].match(/^发布于(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})/);
    if (!anchor) continue;
    // 表格每个字段都被渲染成独立的一行，往下顺序收集 10 个值：
    // 曝光 观看 封面点击率 点赞 评论 收藏 涨粉 分享 人均观看时长 弹幕
    const vals = [];
    for (let j = i + 1; j < nl.length && vals.length < 10; j++) {
      const v = nl[j];
      if (v === '分析详情') break;
      if (/^[\d,，]+$|^[\d.]+%$|^\d+s$/.test(v)) { vals.push(v); continue; }
      if (vals.length) break;
    }
    if (vals.length < 10) continue;
    const title = (nl[i - 1] || '').replace(/^分析详情$/, '').trim();
    notes.push({
      title: title.slice(0, 60) || '(无标题)',
      publishedAt: `${anchor[1]} ${anchor[2]}`,
      exposure: num(vals[0]), views: num(vals[1]), ctr: vals[2],
      likes: num(vals[3]), comments: num(vals[4]), collects: num(vals[5]),
      newFans: num(vals[6]), shares: num(vals[7]), avgWatch: vals[8], danmu: num(vals[9]),
    });
  }

  const today = new Date();
  const dstr = today.toISOString().slice(0, 10);
  const out = {
    ok: true,
    fetchedAt: `${dstr} ${today.toTimeString().slice(0, 5)}`,
    date: dstr,
    period: period || null,
    diag, overview, mom, fans,
    notes,
    noteCount: notes.length,
  };

  // ---------- 落盘 ----------
  fs.mkdirSync(DATA, { recursive: true });
  fs.writeFileSync(path.join(DATA, 'xhs-stats.json'), JSON.stringify(out, null, 2), 'utf8');

  // 账号数据 CSV（按日期 upsert）
  const acctCsv = path.join(DATA, 'xhs-账号数据.csv');
  const acctHeader = '日期,统计周期,曝光数,观看数,封面点击率,平均观看时长,观看总时长,视频完播率,涨粉数,主页访客,发布数,互动数,总粉丝数';
  const acctRow = [dstr, period || '', overview.exposure ?? '', overview.views ?? '', overview.ctr ?? '',
    overview.avgWatch ?? '', overview.totalWatch ?? '', overview.finishRate ?? '',
    diag.newFans ?? '', diag.profileVisits ?? '', diag.published ?? '', diag.interactions ?? '', fans.total ?? ''].join(',');
  upsertCsv(acctCsv, acctHeader, acctRow, 0);

  // 笔记 CSV（按 标题+发布时间 upsert）
  const noteCsv = path.join(DATA, 'xhs-笔记.csv');
  const noteHeader = '采集日,标题,发布于,曝光,观看,封面点击率,点赞,评论,收藏,涨粉,分享,人均观看';
  for (const n of notes) {
    upsertCsv(noteCsv, noteHeader,
      [dstr, csv(n.title), n.publishedAt, n.exposure ?? '', n.views ?? '', n.ctr ?? '',
        n.likes ?? '', n.comments ?? '', n.collects ?? '', n.newFans ?? '', n.shares ?? '', n.avgWatch ?? ''].join(','),
      -1, `${csv(n.title)}|${n.publishedAt}`);
  }

  dump(out);
}

function csv(s) { return /[",\n]/.test(String(s)) ? '"' + String(s).replace(/"/g, '""') + '"' : String(s); }

function upsertCsv(file, header, row, keyIdx, keyVal) {
  let lines = [];
  if (fs.existsSync(file)) lines = fs.readFileSync(file, 'utf8').split('\n').filter(x => x.trim());
  if (!lines.length) lines = [header];
  const key = keyVal !== undefined ? keyVal : String(row.split(',')[0]);
  const findIdx = (l) => {
    const cells = l.split(',');
    if (keyVal !== undefined) {
      // 标题列 + 发布时间列
      return `${cells[1]}|${cells[2]}` === key;
    }
    return cells[0] === key;
  };
  const i = lines.findIndex((l, idx) => idx > 0 && findIdx(l));
  if (i > 0) lines[i] = row; else lines.push(row);
  fs.writeFileSync(file, lines.join('\n') + '\n', 'utf8');
}

main().catch(e => fail({ error: 'SCRIPT_ERROR', raw: String(e).slice(0, 200) }));
