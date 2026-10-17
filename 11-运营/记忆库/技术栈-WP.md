# 技术栈 · WordPress 与线上发布

> 由 `.workbuddy/memory/MEMORY.md` v21 拆分（2026-10-17），**原文未改**。
> 这是「按需读取」层：MEMORY.md 只留索引＋红线摘要，命中本主题才读这里。

---

7/8/9. WordPress（TT5 子主题 `seventhrealm-child`）＋GoDaddy cPanel＋CF 证书；⚠️ 全站默认居中（`qijing.css` L24）⇒ 新布局显式对齐。WP 用户名 `MollyBot_No.2`、钥匙串 `theseventhrealm-wp`，curl 须 `-u -L`。bash 变量后跟中文写 `${VAR}`。  

9b. 🔴🔴 **REST 可直写线上（10-17 推翻旧结论）**：此前记录「CF 拦 `/wp-json/`」是**错的** —— 真实原因是 **curl 默认 UA `curl/8.x` 被 CF 拒**。  

9c. 🔴🔴 **往 WP 正文贴 HTML 前必须 `wp_safe()`（10-17 线上事故）**：WP 的 `wpautop()` 按 `\n\s*\n` 切块、逐块包 `<p>`。  

## live-diff.py 必须带浏览器 UA（2026-10-18 修复）
- 🔴 症状：脚本内 curl 无 UA → Cloudflare 返回 403 HTML 而非 JSON → 「取数失败」，退出码形同 2，发布前判定器失效。10-06 首次记录，10-18 用户批准后已修（`fetch()` 加 `-A $UA`）。
- ✅ 修复后首次全量比对：`--parent 32 --dir 03-页面/朝代页` 覆盖 16 个朝代页（id 94–109），`--map "134:collection" --dir 03-页面` 覆盖藏品页。**`--dir` 必须显式给**，否则默认在仓库根找 `<slug>.html` 会报「本地缺」。
- 🔴 **判读差异方向**：脚本输出 `线上 N 本地 M`，**本地少 ＝ 发布是倒退，绝不能发**，正确动作是把线上 `content.raw` 拉下来覆盖本地（覆盖前先 cp 一份 .bak）。10-18 实测：`109 juexing` 本地比线上少 239 字（线上有商品 CTA 模块），已按此处理。
