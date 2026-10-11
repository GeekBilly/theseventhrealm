# -*- coding: utf-8 -*-
"""把样张 HTML 截成 PNG。用法：
  python3 02-商品/04-金句线/版式/shoot-wallpaper.py shang          # 只截商
  python3 02-商品/04-金句线/版式/shoot-wallpaper.py --all          # 全部已生成的 HTML
依赖：agent-browser（已装在 ~/.workbuddy/binaries/node/workspace）
"""
import subprocess, os, sys, pathlib

BASE = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17/02-商品/05-承接站/样张')
env = dict(os.environ)
env['PATH'] = '/Users/billyhou/.workbuddy/binaries/node/versions/22.22.2-3/bin:' + env['PATH']
AB = '/Users/billyhou/.workbuddy/binaries/node/workspace/bin/agent-browser'


def size_for(stem):
    """按文件名后缀决定截图视口。手机样张必须用竖版视口，否则会被压成横图。"""
    if stem.endswith('phone-iphone') or stem.endswith('lockpreview'):
        return ('1179', '2556')
    if stem.endswith('phone-android'):
        return ('1080', '2400')
    if stem.endswith('mobile'):
        return ('1170', '2532')
    return ('1920', '1080')


def run(a, t=45):
    try:
        r = subprocess.run([AB] + a, timeout=t, capture_output=True, text=True, env=env)
        return ((r.stdout or '') + (r.stderr or '')).strip()
    except Exception:
        return 'TIMEOUT'


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    files = sorted(BASE.glob('*.html'))
    if args:
        files = [f for f in files if f.stem.split('-')[0] in args]
    if not files:
        print('没有可截的 HTML，先跑 gen-wallpaper.py')
        sys.exit(1)
    for f in files:
        w, h = size_for(f.stem)
        run(['set', 'viewport', w, h])
        run(['open', f'file://{f}'])
        run(['wait', '2500'])
        print(f.stem, run(['screenshot', str(f.with_suffix('.png'))])[:60])
    run(['close'])
