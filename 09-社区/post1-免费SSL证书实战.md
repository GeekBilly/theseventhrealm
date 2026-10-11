# 主机商不给免费 SSL？三条命令诊断 + 2 小时切 Cloudflare 零成本解决（实测）

> 适合人群：用 cPanel / GoDaddy 系主机 + WordPress 的建站新手。全程零代码基础，会复制粘贴就行。

## 我的坑

新站上线后 https 打开报「不安全」，进 cPanel 的 SSL/TLS Status 一看，提示：

> Expires on 2027-09-26. The certificate will not renew via AutoSSL because it was not issued via AutoSSL.

更坑的是：**这个页面既没有勾选框，也没有 Run AutoSSL 按钮**——GoDaddy 系主机常把免费 AutoSSL 入口裁掉，为的是卖自家 70+ 美元/年的付费证书。提工单？这家转售商只有 FAQ 和一条打不通的电话。

## 第一步：三条命令搞清证书真相

```bash
# 谁签发的？（issuer 和 subject 相同 = 自签名 = 等于没有 SSL）
echo | openssl s_client -connect 你的域名:443 -servername 你的域名 2>/dev/null \
  | openssl x509 -noout -issuer -subject -dates

# http 是否强制跳转 https
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}" http://你的域名/

# 证书校验是否通过（curl 退出码 60 = 证书不被信任）
curl -v https://你的域名/ 2>&1 | grep -i "ssl\|expire"
```

我的结果：`issuer = subject = CN=我的域名`——**自签名证书占了位**，这就是「不会自动续期」的根因。

## 第二步：切 Cloudflare（免费证书 + CDN，2 小时含等待）

1. **先查 DNSSEC**（开着就换 NS 会断解析）：`dig +short DS 你的域名` 为空 = 没开，安全
2. cloudflare.com 注册（免费）→ Add a site → 选 **Free $0 计划**
3. 核对扫描出的记录：A → 源站 IP、www 的 CNAME、TXT（SPF/DMARC）三条齐全就能过
4. **SSL/TLS → Overview 先设成 Full**（源站是自签名时千万别选 Full strict，会报 526）
5. 到域名商把 NS 改成 Cloudflare 分配的两条
6. 等激活（几分钟~1小时）→ 确认 DNS 里 A/www 是**橙云** → Edge Certificates 打开 **Always Use HTTPS**

## 验收

```bash
dig +short A 你的域名        # 变成 104.x / 172.67.x 开头 = 代理生效
echo | openssl s_client -connect 你的域名:443 2>/dev/null | openssl x509 -noout -issuer -dates
# issuer 变成 Let's Encrypt，90 天自动续期，收工
```

## 三个容易踩的点

- **cPanel 里那行 Self-signed 会一直显示**——那是源站证书，访客走 Cloudflare 边缘证书，永远摸不到它，属正常现象不用管
- **Always Use HTTPS 开了之后注意**：只有「Cloudflare 强制 https」+「源站也强制 https」同时开才会循环跳转，只开一边没事
- 域名若有 MX 邮件记录，切之前要先搬好邮件记录（我查过没有，所以零风险）

**成本：0 元。** 对比主机商付费 SSL 报价约 70 美元/年。

（本文整理自我的建站实录，网站：theseventhrealm.com，欢迎交流）
