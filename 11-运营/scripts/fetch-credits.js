// 在已登录的 workbuddy.cn 页面上下文里取「积分余额 + 近 7 日逐日消耗」
// 由 11-运营/scripts/fetch-credits.sh 通过 agent-browser eval 调用
(async () => {
  const base = 'https://www.workbuddy.cn';
  const post = async (p, b) => {
    const r = await fetch(base + p, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(b)
    });
    return await r.json();
  };
  const round = x => Math.round(x * 100) / 100;
  const pad = n => String(n).padStart(2, '0');
  const fmt = d => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  try {
    const s = await post('/billing/meter/get-user-resource-summary', {});
    const pk = (s.data && s.data.Packages) || [];
    let remain = 0, used = 0, total = 0;
    pk.forEach(p => {
      remain += parseFloat(p.CycleRemainCapacity || 0);
      used += parseFloat(p.CycleUsedCapacity || 0);
      total += parseFloat(p.CycleTotalCapacity || 0);
    });
    const now = new Date();
    const start = fmt(new Date(now.getTime() - 6 * 86400000)) + ' 00:00:00';
    const end = fmt(now) + ' 23:59:59';
    let all = [], totalRows = 0;
    for (let page = 1; page <= 6; page++) {
      const u = await post('/billing/meter/get-user-request-usage', {
        PageNum: page, PageSize: 200, StartTime: start, EndTime: end
      });
      const d = (u.data && u.data.data) || [];
      totalRows = (u.data && u.data.total) || 0;
      all = all.concat(d);
      if (!d.length || all.length >= totalRows) break;
    }
    const byDay = {};
    all.forEach(r => {
      const day = String(r.requestTime || '').slice(0, 10);
      if (!day) return;
      byDay[day] = (byDay[day] || 0) + (Number(r.credit) || 0);
    });
    const days = Object.keys(byDay).sort();
    const sum7 = days.reduce((a, d) => a + byDay[d], 0);
    return JSON.stringify({
      ok: true,
      fetchedAt: new Date().toLocaleString('zh-CN'),
      window: start.slice(0, 10) + '~' + end.slice(0, 10),
      remain: round(remain),
      cycleUsed: round(used),
      cycleTotal: round(total),
      pkgCount: pk.length,
      isPaidUser: !!(s.data && s.data.IsPaidUser),
      rowsInWindow: totalRows,
      byDay: days.map(d => d + ':' + round(byDay[d])),
      sum7: round(sum7),
      avg7: round(sum7 / 7)
    });
  } catch (e) {
    return JSON.stringify({ ok: false, error: String(e && e.message || e) });
  }
})()
