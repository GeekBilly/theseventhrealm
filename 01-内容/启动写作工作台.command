#!/bin/zsh
# 第七境 · 写作工作台启动器（浏览器直写版 · 无后台服务）
# 双击本文件：用 Chrome 打开工作台。不启动任何服务、不上网、不烧积分。
# 首次进入点「连接工作目录」选 01-内容 授权一次；之后保存/同步全库都由浏览器直接写磁盘。

cd "$(dirname "$0")" || exit 1
HTML="$(pwd)/写作工作台.html"

echo "=============================================="
echo " 第七境 · 写作工作台（浏览器直写 · 无后台服务）"
echo "=============================================="
echo
echo "用法："
echo "  1. 打开后点上方「连接工作目录」，选择 01-内容 文件夹授权一次"
echo "  2. 点任意文档进入；「编辑」改完点「保存到磁盘」即写回 md"
echo "  3. 改了外部文件后点「同步全库」刷新工作台内嵌快照"
echo "  没有任何后台进程；关掉浏览器即可。"
echo

if [ ! -f "$HTML" ]; then
  echo "❌ 找不到 写作工作台.html：$HTML"
  read "?按回车关闭…"
  exit 1
fi

# 优先用 Chrome（File System Access API 支持最好）；否则交给默认浏览器
if [ -d "/Applications/Google Chrome.app" ]; then
  open -a "Google Chrome" "$HTML"
else
  open "$HTML"
fi
