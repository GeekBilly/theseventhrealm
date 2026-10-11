#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ruby 注音标签可行性验证（零线上影响）

做法：新建一个 status=draft 的草稿页（不对外可见），内容里同时放：
  <ruby><rt><rp>  —— 注音正主
  <abbr>          —— 对照组（非白名单标签）
  <span style>    —— 对照组（带内联样式）
保存后回读 content.rendered，看哪个被 WordPress 过滤掉。

用法：
  python3 /tmp/wp-ruby-test.py            # 创建 + 回读
  python3 /tmp/wp-ruby-test.py --cleanup  # 删除测试草稿
"""
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request

SITE = 'https://theseventhrealm.com'
USER = 'MollyBot_No.2'


def get_pass():
    return subprocess.run(
        ['security', 'find-generic-password', '-s', 'theseventhrealm-wp', '-w'],
        capture_output=True, text=True).stdout.strip()


def req(method, path, body=None):
    pw = get_pass()
    tok = base64.b64encode(f'{USER}:{pw}'.encode()).decode()
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    r = urllib.request.Request(SITE + path, data=data, method=method)
    r.add_header('Authorization', f'Basic {tok}')
    r.add_header('Content-Type', 'application/json')
    r.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                               'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36')
    r.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8', 'replace'), strict=False)
    except urllib.error.HTTPError as e:
        print('HTTP', e.code, e.read().decode('utf-8', 'replace')[:500])
        raise


CONTENT = (
    '<p>注音测试：'
    '<ruby>桀<rp>(</rp><rt>jié</rt><rp>)</rp></ruby>'
    '纣王好<ruby>酒<rt>jiǔ</rt></ruby>之乐，'
    '<ruby>冒顿<rt>Mò dú</rt></ruby>'
    '<ruby>单于<rt>chán yú</rt></ruby>。</p>'
    '<p>对照组：<abbr title="对照组">abbr标签</abbr>、'
    '<span style="color:red">span内联样式</span>、'
    '<ruby>龘<rt>dá</rt></ruby>。</p>'
)

if '--cleanup' in sys.argv:
    pid = int(sys.argv[sys.argv.index('--cleanup') + 1])
    req('DELETE', f'/wp-json/wp/v2/pages/{pid}?force=true')
    print(f'已删除草稿 {pid}')
    sys.exit(0)

page = req('POST', '/wp-json/wp/v2/pages', {
    'title': 'Ruby注音可行性测试-勿发布',
    'slug': 'ruby-test-tmp',
    'status': 'draft',
    'content': CONTENT,
})
pid = page['id']
print(f'✓ 草稿已建 id={pid} status={page["status"]}')

saved = page.get('content', {}).get('rendered', '')
print('\n=== 保存后 WordPress 返回的内容 ===')
print(saved)

print('\n=== 判定 ===')
for tag, label in [('<ruby', 'ruby'), ('<rt>', 'rt'), ('<rp>', 'rp'),
                   ('<abbr', 'abbr'), ('style=', '内联 style')]:
    print(f'  {label:12s} {"✅ 保留" if tag in saved else "❌ 被剥离"}')

print(f'\n清理命令：python3 /tmp/wp-ruby-test.py --cleanup {pid}')
