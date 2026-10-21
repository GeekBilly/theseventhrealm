# 技术栈 · WordPress 与线上发布

> 由 `.workbuddy/memory/MEMORY.md` v21 拆分（2026-10-17），**原文未改**。
> 这是「按需读取」层：MEMORY.md 只留索引＋红线摘要，命中本主题才读这里。

---

7/8/9. WordPress（TT5 子主题 `seventhrealm-child`）＋GoDaddy cPanel＋CF 证书；⚠️ 全站默认居中（`qijing.css` L24）⇒ 新布局显式对齐。WP 用户名 `MollyBot_No.2`、钥匙串 `theseventhrealm-wp`，curl 须 `-u -L`。bash 变量后跟中文写 `${VAR}`。  

9b. 🔴🔴 **REST 可直写线上（10-17 推翻旧结论）**：此前记录「CF 拦 `/wp-json/`」是**错的** —— 真实原因是 **curl 默认 UA `curl/8.x` 被 CF 拒**。  

9c. 🔴🔴 **往 WP 正文贴 HTML 前必须 `wp_safe()`（10-17 线上事故）**：WP 的 `wpautop()` 按 `\n\s*\n` 切块、逐块包 `<p>`。  

9d. 🔴🔴 **上传媒体必须用 `curl -F`（multipart），裸二进制 >1MB 一律 413（10-21 实测）**：  
　- 症状：`-H "Content-Disposition: attachment; filename=…"` + `--data-binary @file` 传 20.5MB zip → **413 Payload Too Large**；逐级降到 2/6/11/16MB **全拒**，缩到 600KB 才 201。  
　- 定位：50KB 裸传能穿到 PHP（返回 WP 的 `rest_upload_sideload_error`）⇒ **限制在边缘/网关，不是 PHP 的 `upload_max_filesize`**，改 PHP 配置没用。  
　- `wp-admin/async-upload.php` 也走不通 —— 整个 `/wp-admin/` 被 **CF 挑战挡**（403「Just a moment...」），后台分片上传这条路对脚本关闭。  
　- ✅ **解法**：`curl -F "file=@x.zip;type=application/zip" -u … https://…/wp-json/wp/v2/media` ⇒ 20.5MB **一次 201**。  
　- 顺带：探测用的临时文件记得 `DELETE /wp-json/wp/v2/media/<id>?force=1` 清掉（本次误传 5 个已清理）。  

9e. 🔴 **批量改文案＝先扫全站再按模板替换（10-21）**：改任何「承诺型」文案（张数、价格、交付方式）前，先 `wp-json/wp/v2/pages?per_page=100&context=edit` 拉全量 `content.raw`，按关键词去重统计**共有几种写法**，再按模板批量替换。只改眼前那页必然漏（本次 /collection/ 改完，仍有 21 页写着旧数字）。  
　- 🔴 **残留校验正则必须加 `(?<!\d)`**：查「32 张」残留时，新文「232 张」里的「32 张」会被误判 —— 不加负向前瞻会 22 页全误报。  
　- 🔴 **朝代页 URL 是 `/collection/dynasty/<slug>/`**（带 collection 前缀）。用 `/dynasty/<slug>/` curl 会拿到重定向页、`<title>` 还正确 ⇒ **极易误判「改动没生效」**。验收一律用 REST 的 `link` 字段取真 URL。  
　- 可复用脚本：`11-运营/scripts/update-email-copy.py`（`--dry` 只报命中／`--apply` 推送并校验落库长度）。  

## live-diff.py 必须带浏览器 UA（2026-10-18 修复）
- 🔴 症状：脚本内 curl 无 UA → Cloudflare 返回 403 HTML 而非 JSON → 「取数失败」，退出码形同 2，发布前判定器失效。10-06 首次记录，10-18 用户批准后已修（`fetch()` 加 `-A $UA`）。
- ✅ 修复后首次全量比对：`--parent 32 --dir 03-页面/朝代页` 覆盖 16 个朝代页（id 94–109），`--map "134:collection" --dir 03-页面` 覆盖藏品页。**`--dir` 必须显式给**，否则默认在仓库根找 `<slug>.html` 会报「本地缺」。
- 🔴 **判读差异方向**：脚本输出 `线上 N 本地 M`，**本地少 ＝ 发布是倒退，绝不能发**，正确动作是把线上 `content.raw` 拉下来覆盖本地（覆盖前先 cp 一份 .bak）。10-18 实测：`109 juexing` 本地比线上少 239 字（线上有商品 CTA 模块），已按此处理。
