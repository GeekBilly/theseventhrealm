# -*- coding: utf-8 -*-
"""锁屏场景预览：把手机壁纸 PNG 垫底，叠加 iOS 锁屏 UI（时间/日期/底部按钮），
用来肉眼验证「内容有没有被系统元素压住」。
用法：python3 lock-preview.py shang
输出：02-商品/05-承接站/样张/<slug>-phone-lockpreview.html / .png
"""
import sys, pathlib

ROOT = pathlib.Path('/Users/billyhou/WorkBuddy/2026-09-25-15-56-17')
OUT = ROOT / '02-商品/05-承接站/样张'

TPL = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1179px;height:2556px;overflow:hidden;background:#000}
.wall{position:absolute;left:0;top:0;width:1179px;height:2556px}
.ui{position:absolute;inset:0;font-family:-apple-system,'SF Pro Display','PingFang SC',sans-serif}
.status{position:absolute;left:64px;right:64px;top:52px;display:flex;justify-content:space-between;
 align-items:center;color:rgba(40,40,40,.85);font-size:30px;font-weight:500;letter-spacing:1px}
.bars{display:flex;gap:5px;align-items:flex-end}
.bars i{display:block;width:7px;background:rgba(40,40,40,.85);border-radius:1px}
.batt{width:52px;height:25px;border:2px solid rgba(40,40,40,.6);border-radius:6px;position:relative}
.batt::after{content:'';position:absolute;left:3px;top:3px;bottom:3px;width:30px;
 background:rgba(40,40,40,.8);border-radius:3px}
.date{position:absolute;left:0;right:0;top:250px;text-align:center;font-size:32px;
 font-weight:500;color:rgba(40,40,40,.88);letter-spacing:1px}
.clock{position:absolute;left:0;right:0;top:330px;text-align:center;font-size:206px;
 font-weight:600;line-height:1;color:rgba(35,35,35,.92);letter-spacing:-4px}
.widg{position:absolute;left:0;right:0;top:640px;text-align:center;font-size:26px;
 color:rgba(60,60,60,.7);letter-spacing:2px}
.btns{position:absolute;left:0;right:0;bottom:82px;display:flex;justify-content:space-between;
 padding:0 96px}
.btn{width:92px;height:92px;border-radius:50%;background:rgba(30,30,30,.30)}
.hbar{position:absolute;left:50%;transform:translateX(-50%);bottom:26px;width:200px;height:8px;
 border-radius:4px;background:rgba(30,30,30,.5)}
</style></head><body>
<img class="wall" src="file://__PNG__">
<div class="ui">
  <div class="status">
    <span>9:41</span>
    <div class="bars"><i style="height:11px"></i><i style="height:15px"></i><i style="height:19px"></i><i style="height:23px"></i>
      <span class="batt"></span></div>
  </div>
  <div class="date">9月29日 星期二</div>
  <div class="clock">9:41</div>
  <div class="btns"><div class="btn"></div><div class="btn"></div></div>
  <div class="hbar"></div>
</div></body></html>"""

if __name__ == '__main__':
    slug = (sys.argv[1:] or ['shang'])[0]
    png = OUT / f'{slug}-phone-iphone.png'
    html = TPL.replace('__PNG__', str(png))
    p = OUT / f'{slug}-phone-lockpreview.html'
    p.write_text(html, encoding='utf-8')
    print('生成', p)
