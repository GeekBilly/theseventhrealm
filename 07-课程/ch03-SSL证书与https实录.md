# 第 03 章 · HTTPS 踩坑实录：自签名证书与 AutoSSL 接管（草稿）

> 实录时间：2026-09-27 · 站点 theseventhrealm.com（GoDaddy cPanel 主机 + WordPress）

## 现象（课程开场用真实截图）

cPanel 里 SSL 状态提示：
> Expires on 2027年9月26日. The certificate will not renew via AutoSSL because it was not issued via AutoSSL.

翻译成人话：**现在装的这张证书不是 AutoSSL 签发的，所以系统不会帮你自动续期**。当时以为"证书没问题，只是不会自动续"，远程一测才发现真相更严重。

## 远程诊断命令（可直接抄）

```bash
# 1. 看证书是谁签发的、有效期
echo | openssl s_client -connect 域名:443 -servername 域名 2>/dev/null \
  | openssl x509 -noout -issuer -subject -dates
```

本次输出：

```
issuer= /CN=theseventhrealm.com     ← 签发者就是自己 = 自签名证书！
subject= /CN=theseventhrealm.com
notBefore=Sep 26 00:26:26 2026 GMT
notAfter= Sep 26 00:26:26 2027 GMT
```

**判断要点**：正规证书的 issuer 是 CA 机构（Sectigo / Let's Encrypt / R3…），issuer 与 subject 完全相同就是自签名——浏览器必然弹"不安全"，等于没有 SSL。

```bash
# 2. 验证 https 是否真的可用（curl 退出码 60 = 证书校验失败）
curl -s -o /dev/null -w "%{http_code}\n" https://域名/

# 3. 排查 AutoSSL 验证卡点
dig +short 域名 A                                   # A 记录是否指向本主机
curl -s -o /dev/null -w "%{http_code}\n" http://域名/.well-known/acme-challenge/test
curl -s -o /dev/null -w "%{http_code}\n" http://域名/.well-known/pki-validation/test
```

本次结果：A 记录 `118.139.183.234`（正常指向主机）、www 为 CNAME 也正常、两条验证路径返回 404（文件不存在属正常）、**无强制 https 跳转**。

## 结论与修复路径

1. **根因**：该域名上装的是 cPanel 自动生成的自签名证书（不是付费证书，也不是 CA 签发的），所以 AutoSSL 拒绝接管
2. **修复**：在 cPanel → **SSL/TLS Status** 勾选域名（含 www）→ **Run AutoSSL**，系统会签发正规证书（Sectigo/Let's Encrypt，约 90 天）并**替换**自签名那张，之后自动续期
3. **失败时的排查顺序**：DCV（域名验证）能否通过 → A 记录是否指向本主机 → 是否开了 Cloudflare 代理（橙云）→ 安全插件是否拦截 `.well-known` 路径
4. **备选**：用 Cloudflare 免费证书接管（改 NS 到 Cloudflare，一趟解决证书+加速+防护，但会增加一层复杂度）

## ⚠️ 后续实况（同日更新）：主机商把 AutoSSL 入口藏了

进 cPanel → SSL/TLS Status 后发现：**列表里既没有勾选框，也没有 "Run AutoSSL" 按钮**，只有域名和证书状态两列（两个域名都显示 Self-signed）。这是 GoDaddy 系主机的常见做法——**关闭 AutoSSL 功能入口，主推自家付费 SSL**。所以上面第 2 步的"点一下就好"在这台主机上走不通。

**这是一条重要教训**：教程里写"在 cPanel 跑 AutoSSL"之前，先确认主机商有没有把功能放出来；不同主机商（尤其 GoDaddy/US Domain Center 这类）会裁剪 cPanel 功能。

### 绕行方案对比（实测准备）

| 方案 | 成本 | 维护 | 说明 |
|---|---|---|---|
| 开 GoDaddy 工单要求启用 AutoSSL/免费签发 | 免费 | 零 | 先试，话术：请为我的域名启用 AutoSSL 或签发免费证书 |
| **Cloudflare 免费证书** | 免费 | 零（自动续） | 改 NS 到 Cloudflare，边缘证书 + Full 模式；顺带 CDN 与防护 |
| 手动装 90 天免费证书 | 免费 | 每 90 天手动续 | 不推荐，纯运维负担 |

### 迁移前的 DNS 体检（切 Cloudflare 前必做）

```bash
dig +short NS 域名      # 域名服务器在谁家
dig +short MX 域名      # 有邮箱记录？有则迁移时不能漏
dig +short A 域名       # 源站 IP（要原样搬进 Cloudflare）
dig +short TXT 域名     # SPF 等验证记录
```

本次结果：NS 在 GoDaddy（domaincontrol.com）；**无 MX 记录（域名没有在用邮箱）**；A = 118.139.183.234；www 为 CNAME 指向根域；有一条 SPF TXT。→ 结论：迁移只涉及 3 条记录，**没有邮件中断风险**，是低风险操作。

## 结局（2026-09-27 22:13）

原计划「先提工单，两天无果再切 Cloudflare」——**工单路线当天就作废**：US Domain Center（GoDaddy 转售商）只有 FAQ 自助页和一条打不通的英文电话，没有在线工单/邮件/聊天入口。于是当天直接执行 Cloudflare 方案，全程约 9 小时（含等待解析生效）：

| 时间 | 动作 | 结果 |
|---|---|---|
| 12:37 | Cloudflare 分配 NS | `alan/braelyn.ns.cloudflare.com` |
| 12:40 | 查 DNSSEC（无 DS 记录） | 确认切换安全 |
| 20:48 | 域名商改 NS 完成 | 8.8.8.8 已返回 Cloudflare NS，站点无中断 |
| 22:13 | Cloudflare 状态 Active | A 记录变成 `104.21.21.106`（橙云代理生效） |
| 22:13 | 证书签发 | `Let's Encrypt (YE1)`，90 天有效期，**自动续期** |

**最终验证**：`https://theseventhrealm.com/` → 200，`server: cloudflare`，证书链校验通过；`/5000years/` → 200；全站无混合内容。

**成本对比**：GoDaddy 付费 SSL 约 70+ 美元/年 → Cloudflare 免费版 **0 元**，且白送 CDN 加速 + 基础 DDoS 防护。

**本章最大教训**：主机商把免费 SSL 入口裁掉时（GoDaddy 系常见），**不要跟客服耗时间**——域名指向没变的情况下，把 NS 交给 Cloudflare 是性价比最高的解法：免费证书 + 永久免维护 + 当场见效。前提是动手前必须确认 ①DNSSEC 未开启 ②无 MX 邮箱记录（或有 MX 也能迁移，只是要一并搬过去）。

## 成本与时长记录

- AI 诊断（3 条命令 + 判断）：约 2 分钟，几乎无成本
- 人工操作：cPanel 找入口（失败）→ 提工单（此商家无入口）→ Cloudflare 注册/核对记录/改 NS，累计约 30 分钟人工
- 金钱成本：**0 元**（Cloudflare 免费版；GoDaddy 付费 SSL 约 70+ 美元/年，差价即课程里的真实省钱账）

## 可套用交付物

- 「SSL 状态自查」三命令清单（见上）
- 一条铁律：**先确认证书签发成功，再改 WordPress 站点 URL**（顺序颠倒会把自己锁在后台外，见第 01 章预告）
