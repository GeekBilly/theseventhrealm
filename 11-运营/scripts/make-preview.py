#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成品 → 站点预览图

⚠️ 核心原则（用户 2026-10-04 强调）：**网站上的预览图绝不能用商品原图**，
   否则等于免费送。所以：
     ① 分辨率砍到 1200 宽（原图 1920/3840）—— 手机上够看，当桌面壁纸不够用
     ② 叠一层淡斜水印（品牌 + 域名）
     ③ 右下角一个明确的「预览图」角标

用法：
  python3 11-运营/scripts/make-preview.py <成品.png> <输出.jpg> [--width 1200]
  python3 11-运营/scripts/make-preview.py --batch   # 按内置清单批量出
"""
import argparse, pathlib
from PIL import Image, ImageDraw, ImageFont

SERIF = "/System/Library/Fonts/Supplemental/Songti.ttc"   # index 6 ≈ 宋体
ROOT = pathlib.Path(__file__).resolve().parents[2]


def font(size, idx=6):
    try:
        return ImageFont.truetype(SERIF, size, index=idx)
    except Exception:
        return ImageFont.load_default()


def watermark_layer(w, h):
    """斜向重复水印：品牌 + 域名。

    ⚠️ 2026-10-04 实测教训：**不要用「画小图再拼贴」的写法** ——
       `alpha_composite` 静默丢弃负坐标贴图、拼贴也可能整层为空，
       排查了两轮才发现。**直接在整幅画布上画，最后整体旋转**，最稳。
    """
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(max(18, int(w * 0.026)))
    # ⚠️ 2026-10-05 修正：原写作 "theseseventhrealm.com"（多了一个 se），
    #    线上已上传的旧预览图带着错域名，重出即修正；旧图是否替换另开申请单。
    text = "第七境  ·  theseventhrealm.com"
    step_x, step_y = int(w * 0.42), int(h * 0.19)
    for y in range(-step_y, h + step_y, step_y):
        for x in range(-step_x, w + step_x, step_x):
            d.text((x, y), text, font=f, fill=(26, 26, 24, 42))
    # 整体旋转（画布够大，四角丢失可接受，反正只作水印）
    return layer.rotate(24, resample=Image.BICUBIC)


def corner_badge(img):
    """右下角「预览图」角标"""
    d = ImageDraw.Draw(img)
    w, h = img.size
    f = font(max(14, int(w * 0.0155)))
    label = "预览图 · 非交付文件"
    bbox = d.textbbox((0, 0), label, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(w * 0.011)
    x1, y1 = w - pad, h - pad
    x0, y0 = x1 - tw - pad * 2, y1 - th - pad * 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=int(pad * 0.6), fill=(247, 245, 240, 235))
    d.text((x0 + pad, y0 + pad - bbox[1]), label, font=f, fill=(160, 60, 45, 255))


def make_preview(src, dst, width=1200):
    src, dst = pathlib.Path(src), pathlib.Path(dst)
    im = Image.open(src).convert("RGB")
    ow, oh = im.size
    if width and ow > width:
        im = im.resize((width, round(oh * width / ow)), Image.LANCZOS)
    im = im.convert("RGBA")
    im = Image.alpha_composite(im, watermark_layer(*im.size))
    corner_badge(im)
    im.convert("RGB").save(dst, "JPEG", quality=86, optimize=True, progressive=True)
    return pathlib.Path(dst).stat().st_size, Image.open(dst).size


BATCH = [
    ("02-商品/03-字形线/成品-演变/01-正式成品/shang-1920x1080.png", "02-商品/09-上架素材/预览/shang-preview.jpg"),
    ("02-商品/03-字形线/成品-演变/01-正式成品/zhou-1920x1080.png",  "02-商品/09-上架素材/预览/zhou-preview.jpg"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--batch", action="store_true")
    a = ap.parse_args()
    jobs = BATCH if a.batch else [(a.src, a.dst)]
    for s, d in jobs:
        if not s:
            continue
        sp = ROOT / s if not pathlib.Path(s).is_absolute() else pathlib.Path(s)
        dp = ROOT / d if not pathlib.Path(d).is_absolute() else pathlib.Path(d)
        if not sp.exists():
            print(f"  ✗ 源文件不存在: {sp}")
            continue
        dp.parent.mkdir(parents=True, exist_ok=True)
        size, dim = make_preview(sp, dp, a.width)
        print(f"  ✓ {dp.name}  {dim[0]}×{dim[1]}  {size//1024} KB   （源 {Image.open(sp).size}）")


if __name__ == "__main__":
    main()
