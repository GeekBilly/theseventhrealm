#!/bin/bash
# deadlinks-ignore-file
# 把 wallpapers/ 收编进 02-商品/（2026-09-29，用户批准）
# 只移动、不删除；移动后由 fix-paths.sh 修正脚本与 HTML 里的路径引用
set -e
R="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
C="${R}/02-商品"
W="${R}/wallpapers"

mkdir -p "${C}/01-规划" "${C}/02-素材/字体" "${C}/02-素材/古文字" "${C}/02-素材/底纹" \
         "${C}/03-字形线/版式" "${C}/03-字形线/成品" "${C}/04-金句线/版式" "${C}/06-归档"

# 1) 承接站先加编号（与 01/02/03 同序列），后面的脚本才有落点
mv "${C}/承接站" "${C}/05-承接站"

# 2) 名录目录拆解：规划文档 / 脚本各归各位
mv "${C}/名录/商品名录-v1.md" "${C}/名录/catalog.csv" "${C}/名录/sources.csv" "${C}/01-规划/"
mv "${C}/名录/build-catalog.py" "${C}/05-承接站/"
mv "${C}/名录/gen-wallpaper.py" "${C}/名录/gen-wallpaper-phone.py" "${C}/名录/shoot-wallpaper.py" \
   "${C}/名录/verify-wallpaper.py" "${C}/名录/verify-phone.py" "${C}/名录/lock-preview.py" \
   "${C}/名录/build-phone.sh" "${C}/04-金句线/版式/"
mv "${C}/名录/gen-wallpaper-classic.py" "${C}/名录/build-classic.sh" "${C}/03-字形线/版式/"
rmdir "${C}/名录"

# 3) wallpapers 素材三分类
cd "${W}"
mv MaShanZheng.ttf nssc-black.woff2 msz.css nssc.css OFL-MaShanZheng.txt OFL-NotoSerifSC.txt \
   fonts "${C}/02-素材/字体/"
mv jiaguwen-*.svg jinwen-*.svg crop-oracle.png 周字古文字候选.png "${C}/02-素材/古文字/"
mv xuanniao-raw.png phoenix-raw.png seal.png "${C}/02-素材/底纹/"

# 4) v9 版式稿与成品
mv wallpaper-商-v9.html wallpaper-商-v9-4k.html wallpaper-商-v9-mac.html wallpaper-商-v9-mac-4k.html \
   wallpaper-周-v9.html wallpaper-周-v9-4k.html wallpaper-周-v9-mac.html wallpaper-周-v9-mac-4k.html \
   "${C}/03-字形线/版式/"
mv 第七境壁纸-商-v9*.png 第七境壁纸-周-v9*.png "${C}/03-字形线/成品/"

# 5) 其余全部归档（v1–v8 稿、旧成品、调试图、旧生成器）
mv ./* "${C}/06-归档/" 2>/dev/null || true
cd "${R}"
rmdir "${W}" && echo "wallpapers/ 已清空并移除" || echo "注意：wallpapers/ 未清空，请检查"
echo "迁移完成"
