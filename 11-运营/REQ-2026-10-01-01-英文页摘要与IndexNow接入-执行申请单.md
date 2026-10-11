# 执行申请单 REQ-2026-10-01-01 · 英文页摘要补全 + IndexNow 接入

- **提交**：2026-10-01 13:16（AI 代拟）
- **状态**：**已执行**（用户 2026-10-01 13:14 口头批准：「开始办，都开始」）
- **类别**：① 上线/发布（修改线上页面元数据 + 新增站点根静态文件）—— 属四类关键改动
- **风险等级**：**低**
- **需要你动手**：**约 2 分钟**（仅一件事：cPanel 传一个 32 字节文件；其余全部由脚本完成）

---

## 一、为什么现在做（两件都得颗粒）

### 事项 A：`/en/` 页面的搜索摘要是乱码

英文入口已由用户在另一会话上线（HTTP 200，标题正确，已进 sitemap）。但复核发现：

```
当前 description（正文机械截断）
A · VISUAL · RECORD The Seventh Realm Five thousand years,one character at a time. 七境之印 Scroll What this is…
```

根因：该页**未写 `post_excerpt`**。子主题 `functions.php` 第 95 行的钩子只在 excerpt 存在时才同步 three 处 description。

**后果**：Google / Bing 搜索结果显示的就是这段截断文字——第一印象被浪费。
**修复**：写一条英文摘要即可，**0 资源消耗**。

### 事项 B：英文侧没有主动提交通道

此前结论：Google 侧我们**不能主动提交**（GSC 需登录 google.com，触 R-20 跨境信道），只能等被动抓取。
今日实测发现 IndexNow 可补上这个缺口：

| 探测 | 结果 | 含义 |
|---|---|---|
| `GET api.indexnow.org` | 301，响应头带 `x-msedge-ref` | 真实微软边缘节点，**境内可直连**，非运营商劫持 |
| `POST` 空体 | `400 InvalidRequestParameters / urlList field is required` | 接口真实在跑，返回业务级校验错误 |
| `bing.com/ping?sitemap=` | `410 Gone` | Bing 老式 ping **已废弃**，别再试 |

一次提交**同时**通知 Bing / Yandex / Seznam / Naver（Bing 还给 DuckDuckGo 供索引）。

---

## 二、合规判断（IndexNow 为什么不算 R-20）

| 维度 | 情形 |
|---|---|
| 账号 | **不需要**——无注册、无登录、无站长后台 |
| 身份 | 不提交任何身份信息；`hello@` 邮箱无需向该 API 透露 |
| 内容 | 只提交 **URL 列表**，不含内容与客户数据 |
| 频次 | 新页面发布时提交一次，非「高频长期留痕的经营性活动」 |
| 性质 | 服务端间的技术性索引通知，与「人在浏览器长期运营境外平台」不是一回事 |

**结论**：这是目前唯一一条**零账号**的英文侧主动索引通道。相较之下，Bing Webmaster Tools 后台需微软账号登录，属灰区，**本次不碰**。

---

## 三、执行清单

| # | 动作 | 执行方 | 是否线上改动 |
|---|---|---|---|
| 1 | 查出 `/en/` 条目 ID（**实测＝页面类型 id 193**，非文章） | 脚本 | 只读 |
| 2 | 写入英文 `excerpt` |  REST `POST /pages/193` | ✅ |
| 3 | 复读校验 + 线上 HTML 校验三处 description | curl | 只读 |
| 4 | 生成 32 位 hex key（本地留档） | 本地 | 否 |
| 5 | **cPanel 上传 key 文件到 `public_html` 根** | **用户** | ✅ | 🟡 **仍未到位**：10-08 用户回传「已传」后实测仍 404，已穷举 12 条候选路径均为 404，对照组百度验证文件 200 ⇒ 站点侧无问题，属上传位置/名字偏差。详见本文件 §三「常见误传诊断」 |
| 6 | 写 `indexnow-push.py`（去重 + 流水，结构照抄 `baidu-push.py`） | 本地 | 否 |
| 7 | 首次提交全站 URL，验证 HTTP 200 | 脚本 | ✅（对外通知） |

### key 文件（用户操作用）

- 文件名：`0a985f58b6ccb3453930c53306fde21c.txt`
- 内容（32 字节，无换行）：`0a985f58b6ccb3453930c53306fde21c`
- 上传位置：`public_html/` 根目录（与 `baidu_verify_codeva-L1E0s9avah.html`、`sitemap-baidu.xml` 同一层）

### ⚠️ 为什么这一步无法绕过（10-08 实测 + 官方口径复核）

官方文档给两条 sender 验证方式，**只有 Option 1 适用于我们**：

| 方式 | 规则 | 对本站的可用性 |
|---|---|---|
| Option 1 | key 文件放**站点根目录** `{key}.txt` | ✅ 唯一可行（需人工 cPanel） |
| Option 2 | 放**任意子目录**，提交时在 JSON 里带 `keyLocation` 指明位置 | ❌ **有目录作用域限制**：key 文件所在目录决定了可提交 URL 的前缀 |

> Option 2 的原文约束：key 位于 `http://example.com/catalog/key.txt` 时，**只能**提交以 `http://example.com/catalog/` 开头的 URL，其他目录的 URL "may not be considered for indexing"。

本站要提交的 URL 是 `/`、`/5000years/shang/`、`/en/` 这类**顶层路径**，不存在一个子目录能同时覆盖它们 ⇒ 只能走 Option 1。**结论：根目录这一步不可由脚本或 REST 替代，必须人工。**

### 常见误传诊断（10-08 排除清单）

以下路径全部实测 **404**，且**根访问本身是好的**（对照组 `/baidu_verify_codeva-L1E0s9avah.html` 返回 200 / 32 字节）：

```
/0a985f58b6ccb3453930c53306fde21c.txt         ← 唯一正确的名字
/indexnow-key.txt  /indexnow.txt  /key.txt    ← 名字不同
/.../*.txt.txt  /.../*.TXT  /.../*.html       ← 名字变形
/wp-content/...  /wp-content/uploads/2026/{09,10}/...  ← 目录不对
```

若 cPanel 里看得见文件却仍是 404，优先怀疑两件事：**① 传到了 home 目录 `/home/r9uvmiciz8nb/` 而非 `public_html/`**（上传前左侧树要点亮 `public_html`）；**② 文件权限不是 644**（权限异常在某些配置下也表现为 404）。
- 本地副本：`03-页面/站点文件/indexnow-key.txt`
- ⚠️ **不可删除、不可改名**：删了索引通道失效，且重新上传要换 key 重来

> **为什么必须放根目录**：IndexNow 搜索引擎会去 `https://{host}/{key}.txt` 取証后校验。放在 `wp-content/uploads/` 下调用可能仍返回 200（「已接收」），但校验抓不到 key → **静默失败**。这类"看起来成功、实际无效"最浪费时间，故严格按规范放根。

---

## 四、写入内容（事项 A 的精确文本）

```
One character, three thousand years. A personal project tracing Chinese history through how its writing changed — with free ink-on-paper wallpapers to take away.
```

143 字符，落在 SEO description 建议区间（150 字左右）。使用破折号而非冒号是因为它在片段展示里更易读。

---

## 五、回滚方案

| 事项 | 回滚方式 | 回滚点 |
|---|---|---|
| A · excerpt | REST 写入空字符串即可回到「正文截断」状态 | 写入前值已记录在 `11-运营/backup/` |
| B · key 文件 | cPanel 删除该 txt 文件 | 本地留档 `03-页面/站点文件/indexnow-key.txt`，重新上传同名文件即可恢复 |

两件事均**不触碰主题、不改页面正文结构、不影响任何线上可见内容**，回滚成本接近零。

---

## 六、验收标准

- [ ] `/en/` 的 `<meta name="description">` 显示第 §四 条英文摘要
- [ ] `og:description` 与 `twitter:description` **同步**为同一段话
- [ ] `https://theseventhrealm.com/0a985f58b6ccb3453930c53306fde21c.txt` 返回 200 且内容＝key
- [ ] IndexNow 首次提交返回 **200**，且去重文件已记录
- [ ] `path-links-check.py` 无新增断链

---

## 七、执行进度

| # | 动作 | 状态 | 备注 |
|---|---|---|---|
| 1 | 查 `/en/` 条目 | ✅ | **页面 id 193**（非文章） |
| 2 | 写入英文 excerpt | ✅ | 143 字符；备份 `11-运营/backup/en-page-before-excerpt-2026-10-01.json` |
| 3 | 三处 description 校验 | ✅ | meta / og: / twitter: 全部同步（加 `?nc=` 绕 CF 缓存后验证） |
| 4 | 生成 key | ✅ | `0a985f58b6ccb3453930c53306fde21c` |
| 5 | **cPanel 上传 key 到根目录** | 🟡 **卡住** | 10-08 首次回传未落到位（见 §三诊断），需按正确名字重传一次；除此之外不需人工 |
| 6 | 脚本 `indexnow-push.py` | ✅ | 试运行可取到 26 个 URL（含 `/en/`） |
| 7 | 首次真实提交 | ⬜ 待第 5 步完成后执行 | 含 key 硬自检，不通过不提交 |

---

## 八、相关文件

- IndexNow 范围界定与原始依据：`04-市场/03-推广获客/英文入口-承接范围界定-2026-09-30.md`
- 同类先例（百度推送，本次脚本结构来源）：`11-运营/REQ-2026-09-30-03-百度站长平台接入-执行申请单.md`
- 凭据：WP 应用密码走钥匙串 `theseventhrealm-wp`；**无需新增任何第三方账号**
