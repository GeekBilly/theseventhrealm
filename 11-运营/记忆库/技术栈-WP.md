# 技术栈 · WordPress 与线上发布

> 由 `.workbuddy/memory/MEMORY.md` v21 拆分（2026-10-17），**原文未改**。
> 这是「按需读取」层：MEMORY.md 只留索引＋红线摘要，命中本主题才读这里。

---

7/8/9. WordPress（TT5 子主题 `seventhrealm-child`）＋GoDaddy cPanel＋CF 证书；⚠️ 全站默认居中（`qijing.css` L24）⇒ 新布局显式对齐。WP 用户名 `MollyBot_No.2`、钥匙串 `theseventhrealm-wp`，curl 须 `-u -L`。bash 变量后跟中文写 `${VAR}`。  

9b. 🔴🔴 **REST 可直写线上（10-17 推翻旧结论）**：此前记录「CF 拦 `/wp-json/`」是**错的** —— 真实原因是 **curl 默认 UA `curl/8.x` 被 CF 拒**。  

9c. 🔴🔴 **往 WP 正文贴 HTML 前必须 `wp_safe()`（10-17 线上事故）**：WP 的 `wpautop()` 按 `\n\s*\n` 切块、逐块包 `<p>`。  
