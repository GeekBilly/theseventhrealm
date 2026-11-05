// 一次性探针：统计晨检 transcript 的轮次结构
const fs = require('fs');
const files = process.argv.slice(2);
for (const f of files) {
  const lines = fs.readFileSync(f + '.jsonl', 'utf8').trim().split('\n');
  const t = {};
  let reasoningChars = 0, msgChars = 0, toolResultChars = 0;
  for (const l of lines) {
    try {
      const j = JSON.parse(l);
      const k = j.type || '?';
      t[k] = (t[k] || 0) + 1;
      if (k === 'reasoning') reasoningChars += l.length;
      if (k === 'message') msgChars += l.length;
      if (k === 'function_call_result') toolResultChars += l.length;
    } catch (e) {}
  }
  console.log(f.slice(0, 8), JSON.stringify(t),
    'msgKB:' + Math.round(msgChars / 1024),
    'toolResKB:' + Math.round(toolResultChars / 1024),
    'reasonKB:' + Math.round(reasoningChars / 1024));
}
