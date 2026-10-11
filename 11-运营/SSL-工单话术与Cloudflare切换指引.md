# SSL 解决指引：①工单话术（今天做） ②Cloudflare 切换（两天后备用）

站点：theseventhrealm.com · 主机：GoDaddy 系 cPanel（sin2.secureserver.net，新加坡）
现状：SSL/TLS Status 里是自签名证书；该版 cPanel **无勾选框、无 Run AutoSSL 按钮**（主机商关闭了 AutoSSL 入口）
DNS 现状（已体检）：NS=GoDaddy domaincontrol.com ｜ **无 MX 记录（无邮件风险）** ｜ A=118.139.183.234 ｜ www=CNAME→根域 ｜ 1 条 SPF TXT

---

## 进展记录

- **2026-09-27 10:00**：查 US Domain Center「联系我们」页——左侧仅 FAQ 自助，右侧客户支持只有电话 (86) 400-842-8290（仅英文，实测打不通），**没有在线工单/邮件/聊天入口** → 工单路线不可用，**决定直接执行 Cloudflare 方案**。第一步话术保留备用（日后若联系上客服或改走 GoDaddy 在线聊天可直接用）。

---

## 第一步：提工单（已确认不可用，保留话术备用）

### 提交入口（二选一，先试哪个都行）

| 渠道 | 位置 | 说明 |
|---|---|---|
| 购买渠道客服 | US Domain Center 官网 → Support / Contact（工单或在线聊天） | 域名/主机是在这里买的，客服管得到 |
| 面板服务商 | GoDaddy 账户 → Help / Contact Us → 提交工单 | cPanel 面板实际是 GoDaddy 的 |

### 工单正文（中文版，直接粘贴）

> 标题：请为我的域名启用 AutoSSL 或签发免费 SSL 证书
>
> 正文：
> 我的域名 theseventhrealm.com 托管在 cPanel（主机 sin2.secureserver.net）上。
> 当前该域名安装的是一张自签名证书（issuer 与 subject 均为 CN=theseventhrealm.com），浏览器访问 https://theseventhrealm.com 会提示证书不安全。
> 我在 cPanel → SSL/TLS Status 页面中没有找到 Run AutoSSL 选项，页面也没有域名勾选框，因此无法自行签发。
> 请协助：为 theseventhrealm.com 与 www.theseventhrealm.com 启用 AutoSSL，或签发并安装一张免费 SSL 证书（Let's Encrypt / Sectigo）。
> 谢谢。

### 英文版（客服响应可能更快的备用版本）

> Subject: Please enable AutoSSL or issue a free SSL certificate for my domain
>
> Hello, my domain theseventhrealm.com is hosted on my cPanel account (server sin2.secureserver.net).
> The domain currently has a **self-signed** certificate (issuer = subject = CN=theseventhrealm.com), so browsers show a security warning on https://theseventhrealm.com.
> The SSL/TLS Status page in cPanel has no "Run AutoSSL" option and no domain checkboxes, so I cannot issue one myself.
> Could you please enable AutoSSL for theseventhrealm.com and www.theseventhrealm.com, or issue and install a free SSL certificate (Let's Encrypt / Sectigo)?
> Thank you.

### 拿到回复后

把工单号或客服回复贴给我，我远程验证证书是否已变成 CA 签发。

---

## 第二步：切换 Cloudflare（免费证书，约 15 分钟）— **当前执行路线**

### 为什么这条路可行（对你的好处）
- 免费，证书自动续期，永久免维护
- 顺带获得 CDN 加速（对国内/海外访客都更快）和基础安全防护
- **你的域名没有 MX 邮件记录**，迁移只搬 3 条记录，不存在邮件中断风险

### 操作步骤

**1. 注册并添加站点**
- 打开 cloudflare.com → Sign up（免费）→ 登录后 Add a site → 输入 `theseventhrealm.com` → 选 **Free** 计划

**2. 核对扫描到的记录**（Cloudflare 会自动扫描，逐条核对）
- A 记录：`theseventhrealm.com` → `118.139.183.234`
- CNAME：`www` → `theseventhrealm.com`
- TXT：`v=spf1 include:secureserver.net ~all`
- 三条都在就继续；缺哪条手动补上

**3. 去域名商换 NS**
- 登录 US Domain Center / GoDaddy → 找到 theseventhrealm.com 的域名设置 → Nameservers → 改为**自定义 NS**
- 填入 Cloudflare 给的两条（形如 `xxx.ns.cloudflare.com`）→ 保存
- 生效时间：几分钟到 24 小时（通常 10 分钟内）

**4. 回 Cloudflare 里设置**
- 等 Cloudflare 提示 "Site is active"（NS 已生效）
- **DNS 记录确认代理已开启（橙色云朵）**——免费证书只在代理开启时生效
- SSL/TLS → Overview → 加密模式选 **Full**（源站是自签名证书，**不能选 Full (strict)**，会报 526）
- SSL/TLS → Edge Certificates → 打开 **Always Use HTTPS**
- 可选优化：打开 Brotli 压缩、Automatic HTTPS Rewrites

**5. 验证（把结果发我，我复核）**
```bash
dig +short NS theseventhrealm.com          # 应显示 .ns.cloudflare.com
echo | openssl s_client -connect theseventhrealm.com:443 -servername theseventhrealm.com 2>/dev/null \
  | openssl x509 -noout -issuer -dates      # issuer 应是 Cloudflare/Google Trust 等 CA，不再是自身域名
curl -s -o /dev/null -w "%{http_code}\n" https://theseventhrealm.com/   # 应返回 200 且无证书错误
```

**6. 生效后再做**（顺序别反）
- WordPress 后台 → 设置 → 常规 → 确认 WordPress 地址与站点地址均为 `https://theseventhrealm.com`
- 再考虑开启强制 https

### 风险与回滚
- 切 NS 期间有短暂解析波动，属正常
- 想回退：把 NS 改回 GoDaddy 原名服务器，DNS 记录恢复原状即可
- 不影响 WordPress 数据、不影响主机上的文件
- 注意：开启橙云代理后，cPanel 侧 AutoSSL 的 HTTP 验证会失效——但你这台主机本来就没有 AutoSSL 入口，无影响

---

## 判断口径（两天后自动检查用）
- 证书 issuer 若变为 Sectigo / Let's Encrypt / Google Trust / Cloudflare → 已解决
- 若 issuer 仍是 `CN=theseventhrealm.com`（自签名）→ 走第二步

---

## 附：Cloudflare 扫描到的记录清单（2026-09-27 核对通过）

| Type | Name | Content | Proxy | 备注 |
|---|---|---|---|---|
| A | theseventhrealm.com | 118.139.183.234 | 橙云 | 主机 IP，正确 |
| CNAME | www | theseventhrealm.com | 橙云 | 正确 |
| CNAME | _domainconnect | _domainconnect.gd.domaincontrol.com | 建议改**灰云** | GoDaddy 验证用 |
| TXT | _dmarc | v=DMARC1; p=… | DNS only | 保留 |
| TXT | theseventhrealm.com | v=spf1 include:secureserver.net ~all | DNS only | 保留 |

无 MX 记录（该域名未启用邮箱）。

**回滚**：把 NS 改回 `ns11.domaincontrol.com` / `ns12.domaincontrol.com` 即恢复原状。

### 切换执行记录

- **2026-09-27 12:40**：Cloudflare 分配 NS = `alan.ns.cloudflare.com`、`braelyn.ns.cloudflare.com`（原 GoDaddy NS 为 ns11/ns12.domaincontrol.com，Cloudflare 页面显示的 ns47/ns48 为其缓存）
- **DNSSEC 检查**：无 DS 记录 → 未开启，切换安全
- **2026-09-27 20:50 验证**：8.8.8.8 已返回 Cloudflare NS，Cloudflare 权威 NS 已应答本域名 SOA，站点 http/https 均 200 无中断；A 记录仍直连源站 → 站点处于 Pending，待激活后橙云代理与免费证书才会生效
- **2026-09-27 22:13 ✅ 激活完成**（用户截图确认 Cloudflare 显示 "Your domain is now protected by Cloudflare"）：
  - 解析已走代理：A = `104.21.21.106` / `172.67.197.244`（橙云生效）
  - 证书已签发：`issuer = Let's Encrypt (YE1)`，**有效期 2026-09-27 → 2026-12-26，自动续期**
  - `https://theseventhrealm.com/` → **200**，响应头 `server: cloudflare`，证书链校验通过（自签名时代结束）
  - `https://theseventhrealm.com/5000years/` → **200**
  - 全站无 `http://` 混合内容（Cloudflare 自动 HTTPS 改写生效；本地源文件已同步改为 https 引用）

### 常见疑问：cPanel 的 SSL/TLS Status 仍显示 "Self-signed"，正常吗？

**正常，且无需处理。** 那个面板检查的是**源站服务器**上的证书，不是访客看到的证书。Cloudflare 代理模式下，访客流量在边缘就由 Cloudflare 的证书终结（Let's Encrypt，自动续期），**永远不会直接摸到源站证书**。

实测对照（2026-09-27 22:20）：

| 查看对象 | 证书签发者 | 有效期 | 是否要紧 |
|---|---|---|---|
| 访客看到（`theseventhrealm.com:443`） | **Let's Encrypt (YE1)** | 90 天，自动续期 | ✅ 有效，浏览器无警告 |
| 源站自己（`118.139.183.234:443`） | `CN=theseventhrealm.com`（自签名） | 2027-09-26 | ⚪ 已被 Cloudflare 屏蔽，无所谓 |

**可选升级（非必需）**：若想让 cPanel 面板也变绿、并把加密模式升级到 Full (strict)，可在 Cloudflare → SSL/TLS → Origin Server → **Create Certificate** 生成一张 **15 年有效期的免费源站证书**，再把证书内容粘贴进 cPanel 的 SSL/TLS 安装。价值有限（访客体验毫无变化），建议留到以后有需要时再做。

### 收尾清单（✅ 2026-09-27 22:34 全部完成）

1. ✅ **Always Use HTTPS 已打开** —— `http://` 现在 301 跳 `https://`
2. ✅ **SSL/TLS 加密模式 = Full**（已确认；不可选 Full (strict)——源站仍是自签名证书，选 strict 会 526）
3. ✅ `_domainconnect` CNAME 已设为 DNS only（灰云）
4. ⏳ 待确认：WordPress 后台 → 设置 → 常规 → 站点地址与 WordPress 地址均为 `https://theseventhrealm.com`

**完成后的实测（22:34）**：

| 链路 | 结果 |
|---|---|
| `http://` 首页 | 301 → https（跳转 1 次），最终 **200** |
| `http://` /5000years | 301 → https，最终 **200** |
| `https://www.` | 301 → 根域，最终 **200** |
| 证书 | Let's Encrypt，2026-12-26 到期，自动续期 |
| 跳转次数 | 均为 1 次，**无重定向循环**（`ERR_TOO_MANY_REDIRECTS` 未出现） |

> 提示：Cloudflare 的 Always Use HTTPS 与「源站自己也在强制 https」同时开启才会造成循环。本站在 Full 模式下由 Cloudflare 用 https 回源、WordPress 的站点地址同为 https，因此只有一次 301，无循环。若将来更换主机并出现 `ERR_TOO_MANY_REDIRECTS`，优先关掉**源站侧**的 http→https 强制规则。
