# -*- coding: utf-8 -*-
"""金句壁纸 · 批量 HTML→PNG（本地零积分）

逐张调用系统 Chrome 无头截图；每张单独进程 + 超时保护。
任何一张失败（崩溃/超时）都记进失败清单，跳过继续，不无限重试。
按「失败一次即降级」：整体失败面大时停止，改交付 HTML。

用法：
  python3 shoot-verse-wallpaper.py             # 全部 60 张（30条×2尺寸）
  python3 shoot-verse-wallpaper.py --limit=4   # 只截前 4 张（验证用）
  python3 shoot-verse-wallpaper.py --start=D06 --force  # 只重截 D06 及之后（保留前面已确认的成品）
"""
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
D = ROOT / '04-市场/03-推广获客/金句日更-202611/壁纸HTML'
PNG = D.parent / '成品PNG'
CH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
PROFILE = '/tmp/chrome-verse-batch'
PNG.mkdir(parents=True, exist_ok=True)

SIZES = {'iphone': (1179, 2556), 'android': (1080, 2400)}


def shot(html: pathlib.Path, png: pathlib.Path, size) -> bool:
    w, h = SIZES[size]
    # --no-sandbox：本环境（WorkBuddy 沙箱）里 Chrome 自带沙箱初始化失败会 FATAL
    #   （"sandbox initialization failed" / "GPU process isn't usable"），必须显式关掉。
    cmd = [CH, '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
           '--allow-file-access-from-files', '--force-device-scale-factor=1',
           f'--user-data-dir={PROFILE}', f'--window-size={w},{h}',
           '--virtual-time-budget=4000', f'--screenshot={png}', f'file://{html.resolve()}']
    # 成功判定不能只看「文件存在且够大」——旧文件残留会被误判成功（2026-11-17 踩坑：
    # --force 报 OK 但 mtime 没变）。改为截图后校验 mtime 确实在本次调用窗口内刷新。
    import time as _t
    t0 = _t.time() - 1
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired:
        return False
    return png.exists() and png.stat().st_size > 10000 and png.stat().st_mtime >= t0


def main():
    limit, force, start = None, False, None
    for a in sys.argv[1:]:
        if a.startswith('--limit='):
            limit = int(a.split('=')[1])
        if a == '--force':
            force = True
        if a.startswith('--start='):
            start = a.split('=')[1].upper()   # 如 D06：只处理该天及之后
    htmls = sorted(D.glob('D*-phone-*.html'))
    if start:
        htmls = [h for h in htmls if h.name[:3] >= start]
    if limit:
        htmls = htmls[:limit]
    ok, fail = 0, []
    for i, hp in enumerate(htmls, 1):
        size = 'iphone' if 'iphone' in hp.stem else 'android'
        out = PNG / f'{hp.stem}.png'
        # 已存在且够大则跳过（幂等）；--force 时强制重出
        if not force and out.exists() and out.stat().st_size > 10000:
            ok += 1
            continue
        good = shot(hp, out, size)
        if good:
            ok += 1
        else:
            fail.append(hp.name)
            if out.exists() and out.stat().st_size < 10000:
                out.unlink()
        print(f'[{i}/{len(htmls)}] {"OK" if good else "FAIL"} {hp.name}')
        time.sleep(0.3)
    print(f'\n完成 {ok}/{len(htmls)}；失败 {len(fail)}')
    if fail:
        print('失败清单:', ', '.join(fail))
        (PNG / '_失败清单.txt').write_text('\n'.join(fail), encoding='utf-8')


if __name__ == '__main__':
    main()
