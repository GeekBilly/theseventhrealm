# IndexNow key 上传流程（人工操作 · 约 3 分钟）

> 建立：2026-10-15 ｜ 状态：**待你操作**
> 对应待办：T-03 ｜ 目标：让 Bing / Yandex / Seznam / Naver / DuckDuckGo 知道本站有新页面

---

## 零、先说结论：**只差一件事**

我把现状核对了一遍，比预想的简单很多：

| 项目 | 之前以为 | **实际核对结果** |
|---|---|---|
| `sitemap-baidu.xml` | 线上还是旧的 24 条 | ✅ **已完成**：线上 43 条，与本地逐条一致 |
| IndexNow key 文件 | 未上传 | ❌ **404，未上传** ← 唯一要做的 |

所以你不用管 sitemap 了，**只需要上传一个 32 字节的 txt 文件**。

---

## 一、要上传的文件（已备好）

```
本地路径：03-页面/站点文件/0a985f58b6ccb3453930c53306fde21c.txt
```

- **文件名**：`0a985f58b6ccb3453930c53306fde21c.txt`（一字不差）
- **文件内容**：`0a985f58b6ccb3453930c53306fde21c`（32 字节，**末尾没有换行**）
- **上传位置**：站点**根目录**，即 `public_html/` 下面（和 `wp-content`、`wp-admin` 同级）

> ⚠️ **必须放根目录**。放在 `wp-content/uploads/` 下提交虽然也返回 200（「已接收」），但搜索引擎回抓校验会失败，结果是**静默无效**——看起来成功了，其实一个页面都没推到。

---

## 二、操作步骤（cPanel 文件管理器）

1. 登录 cPanel → 打开 **文件管理器（File Manager）**
2. 右上角设置里勾选 **「显示隐藏文件」**（可选，本步用不上）
3. 左侧进入 **`public_html`**（站点根目录）
4. 点顶部 **上传（Upload）**
5. 选择本地文件：`03-页面/站点文件/0a985f58b6ccb3453930c53306fde21c.txt`
6. 上传完成后，确认它在 `public_html/` 下，路径形如：
   ```
   /home/<用户名>/public_html/0a985f58b6ccb3453930c53306fde21c.txt
   ```

**如果用 FTP**：上传到 `/public_html/` 根目录即可，二进制/ASCII 都行（纯英文无换行）。

---

## 三、验证（上传后告诉我，或你自己跑这条）

在自己终端执行：

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36" \
  -L "https://theseventhrealm.com/0a985f58b6ccb3453930c53306fde21c.txt"
```

- 返回 **`200`** ✅ → 成功，告诉我一声，我立刻推送 43 条 URL
- 返回 **`404`** ❌ → 文件没在根目录，检查是不是传进了子目录
- 返回 **`403`** → Cloudflare 拦了，可能性很低；真遇到告诉我

> 💡 如果返回 404 但你明明传了，可能是 Cloudflare 缓存（TTL 4 小时，和上次 zip 那个一样）。可以去看 cPanel 里文件是否真的在 `public_html/` 下。

---

## 四、上传完成后我来做的事

你回一句「传好了」，我跑这两条（零积分）：

```bash
python3 11-运营/scripts/indexnow-push.py --dry    # 先自检 + 列出待推 URL
python3 11-运营/scripts/indexnow-push.py          # 正式推送（自动去重）
```

- 脚本会自动去重，已推过的不再重复提交
- 单次上限 10000 条，本站 43 条一次推完
- 推送目标：**Bing / Yandex / Seznam / Naver**（Bing 还给 DuckDuckGo 供索引）

---

## 五、预期与注意事项

- **IndexNow 只负责「来爬」，不保证收录**。内容单薄的页推了也可能不被索引。
- 这是**零账号**通道：不需要注册、不需要登录任何站长后台，符合 R-19 合规要求。
- 推完后 Bing 通常在 **几天到两周**内开始抓取，不是即时生效。
- 后续站点新增/删除页面后，先重跑 `11-运营/scripts/build-baidu-sitemap.py`，脚本才会看到新 URL。

---

## 附：为什么 Google 不走这条路

Google Search Console 需登录 google.com → 触 R-20 跨境信道，我们不能主动提交，只能靠 `robots.txt` 里已声明的 sitemap 被动发现。IndexNow 是绕开这条限制的合规通道。
