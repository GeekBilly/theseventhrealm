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

## publish-single.sh 必须带 UA + 正文必须压空行（2026-11-08 修）

- 🔴 **同一类病根**：该脚本 4 处 curl **全都没带 UA** → CF 拒 curl 默认 UA（curl/8.x）→ 403 HTML 而非 JSON
  → **发布静默失败**（看起来跑完了，线上其实没变）。已加 `UA="…Chrome/126…"`（备份 `11-运营/backup/publish-single.sh.bak-20261020`）。
  📌 以后新增任何对 WP REST 的 curl，**一律带浏览器 UA**。
- 🔴 **正文贴 HTML 前先压掉连续空行**（`re.sub(r"\n\s*\n+","\n")`）：
  空行会被 `wpautop()` 插成 `<p><br></p>`；子主题 the_content filter 只清「**完全空白**的 `<p>`」，
  压空行更彻底。10-20 实测：24 处空行 → 0，线上复核空段落残留 0。
- 📌 **发单页用 `publish-single.sh <slug> <标题> <正文文件> [摘要]`**（幂等，已存在则更新；实测新页得 id 729）。
  第 4 个参数「摘要」不能省 —— 子主题钩子会把它同步到三处 description，等于零成本拿 SEO 描述。
- 📌 **站内表单块要连 loader 一起搬**：从别的页面复制 MailerLite 表单时，
  只抓到 `ml-form-embedBody`（568 B）**缺 `ml-form-scripts` + `webforms.min.js` loader → 表单不提交**；
  完整块应取到 `ml-form-scripts` 的 `</div>` 为止（2,023 B）。

## 改既有长页正文＝最小增量插入（2026-11-08，页面 13 补 /memory-token/ 入口）

- 🔴 **别整篇跑 `wp_safe()` 压空行**：首页 178 KB 正文里既有的空行是「现状」的一部分，
  全篇重排会改变整页渲染。正确做法＝**只有新增块单行、内部无空行**，其余一个字符都不动，
  原样 POST 回去。（`wp_safe` 铁律适用于「新页贴整篇 HTML」，不适用于「老页插一行」。）
- ✅ 可复用流程（`11-运营/scripts/deploy-lp-entry.py`，`--dry` / `--rollback`）：
  REST `?context=edit` 取 raw → 备份落盘 → 唯一锚点前插单行块 →
  POST **只传 `{"content":...}`**（不动 title / excerpt / slug）→ 拉回 raw **逐字比对**
  → `cf-cache-rules.py --purge` → 抓公开 HTML 数链接数／查空 `<p>`／查关键标记。
- 📌 新增块**不要用 `class="reveal"`**（滚动观察器未必扫得到 ⇒ 长期隐藏）；
  **不要放在 `<style id="qj-rhythm">` 之后**（末尾注入块必须最后出现才赢，版式铁律）。
- 🔴 POST 成功但线上 raw 与本地不一致 ⇒ **直接回滚降级，不排障、不重试**。
- 📌 首页入站口选在「留个邮箱」订阅节之后：不插进「七境之门」内容地图，
  也不打断主转化漏斗；内链可达即可，不必抢首屏。

## 🔴 搬 MailerLite 表单块：loader 之外还必须带外层容器（2026-11-08，页面 729）

- 上次「补齐 `webforms.min.js` loader」**仍不够**：落地页搬的是半块，外层
  缺 `class="ml-subscribe-form-46577392"` ⇒ loader 回调里
  `document.querySelector('.ml-subscribe-form-46577392')` 恒为 null ⇒ **提交后不会切到成功态**。
- 半块还夹带三处脏数据：①成功提示沿用藏品页的「32 张壁纸的下载链接已经发到你邮箱」
  ②`loading` 按钮里混入 `</p>` ③末尾多 3 个孤立 `</div>`（div 不平衡）。
- ✅ **完整块判据（6 项缺一不可）**：容器 id/class ＋ `.row-form` ＋ `.row-success`
  ＋ `ml-form-scripts` 与 loader ＋ **成功文案改成当前页面自己的话** ＋ `<div>` 开闭平衡。
  只搬 `ml-form-embedBody` 不算搬完；换页面时最稳是整段重写成自洽结构。
- 📌 「目前还没开卖」这类**状态型文案有时效**：任一渠道真正可搜/可买的当天必须回来改，
  否则它自己会变成新的虚假陈述。写文案时同步在申请单里挂一条「后续必须回来改」。
