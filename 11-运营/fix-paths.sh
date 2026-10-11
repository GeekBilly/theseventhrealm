#!/bin/bash
# deadlinks-ignore-file
# 合并后修正路径引用（2026-09-29）
set -e
R="/Users/billyhou/WorkBuddy/2026-09-25-15-56-17"
# 注意：BSD grep 的 BRE 不支持 \| 交替，必须用 -E
FILES=$(grep -rlE "wallpapers|02-商品/承接站|02-商品/名录" \
  --include="*.py" --include="*.sh" --include="*.html" --include="*.md" \
  --exclude="fix-paths.sh" \
  "${R}/02-商品" "${R}/11-运营" "${R}/README-空间结构.md" 2>/dev/null || true)

echo "待修正文件："
echo "${FILES}" | sed 's/^/  /'

# 注意：本机 sed 是 toybox 版，`-i ''` 会把空串当文件名 → 必须用 `-i.bak` 再清理
for f in ${FILES}; do
  [ -n "$f" ] || continue
  sed -i.bak \
    -e 's|wallpapers/MaShanZheng\.ttf|02-商品/02-素材/字体/MaShanZheng.ttf|g' \
    -e 's|wallpapers/nssc-black\.woff2|02-商品/02-素材/字体/nssc-black.woff2|g' \
    -e 's|wallpapers/seal\.png|02-商品/02-素材/底纹/seal.png|g' \
    -e 's|wallpapers/xuanniao-raw\.png|02-商品/02-素材/底纹/xuanniao-raw.png|g' \
    -e 's|wallpapers/phoenix-raw\.png|02-商品/02-素材/底纹/phoenix-raw.png|g' \
    -e 's|wallpapers/fonts/|02-商品/02-素材/字体/fonts/|g' \
    -e 's|wallpapers/jiaguwen-|02-商品/02-素材/古文字/jiaguwen-|g' \
    -e 's|wallpapers/jinwen-|02-商品/02-素材/古文字/jinwen-|g' \
    -e "s|'wallpapers'|'02-商品/03-字形线/版式'|g" \
    -e 's|02-商品/承接站|02-商品/05-承接站|g' \
    -e 's|02-商品/名录/gen-wallpaper-phone\.py|02-商品/04-金句线/版式/gen-wallpaper-phone.py|g' \
    -e 's|02-商品/名录/gen-wallpaper-classic\.py|02-商品/03-字形线/版式/gen-wallpaper-classic.py|g' \
    -e 's|02-商品/名录/|02-商品/|g' \
    "$f"
done

echo
echo "=== 残留 wallpapers 引用（应为空）==="
grep -rn "wallpapers" --include="*.py" --include="*.sh" --include="*.html" \
  "${R}/02-商品" "${R}/11-运营" 2>/dev/null | head -10 || echo "  （无）"
echo "=== 残留 02-商品/名录 引用（应为空）==="
grep -rn "02-商品/名录" --include="*.py" --include="*.sh" --include="*.html" --include="*.md" \
  "${R}/02-商品" "${R}/11-运营" "${R}/README-空间结构.md" 2>/dev/null | head -10 || echo "  （无）"
echo "路径修正完成"
