# Cloudflare · 缓存与性能

> 由 `.workbuddy/memory/MEMORY.md` v21 拆分（2026-10-17），**原文未改**。
> 这是「按需读取」层：MEMORY.md 只留索引＋红线摘要，命中本主题才读这里。

---

60/55b. ⚠️ **CF 缓存两条**：① uploads 下 zip 缓存 **4 小时**，覆盖后验证先看 `cf-cache-status`；② **改完页面必清 CDN 缓存**（`deploy-cosmos.py`／`publish.sh` **已内置自动清**，手工改线上用 `cf-cache-rules.py --purge`）。🔴 CF Cache Rules 是 **last-match-wins** ⇒ **bypass 规则必须排最后**。详见 `11-运营/reports/站点性能诊断与优化方案-2026-10-17.md`  

---

## CF token 权限现状（2026-10-20 更新 · 动手前先看，别撞 9109）

| 钥匙串服务名（账号均为 `theseventhrealm`） | 权限 | 能改 Zone Settings 吗 |
|---|---|---|
| **`cf-audit`** | Zone Settings **读写** + Zone Read | ✅ **能**（2026-10-20 用户升级） |
| `cf-cache-edit` | Cache Rules Edit + Cache Purge + Zone Read | 🔴 不能（`9109 Unauthorized`） |

Zone id：`1dbeff2d4400e264591b83de7d48a761`
复验脚本：`11-运营/scripts/check-cf-challenge.sh`（自动按 `cf-settings`→`cf-audit`→`cf-cache-edit` 找可用 token，**只读**）

## 🔴 移动／小众浏览器「打不开」= 多半是 CF 挑战页，不是站点故障（2026-10-20 事故）

**判别铁律**：先问用户要**截图或报错原文**，再谈技术推测。
- 症状 = 黑底绿字「**正在验证您的请求，请稍候...**」／「Just a moment...」⇒ **Cloudflare Managed Challenge**；
- 我这次就栽在这儿：先用 curl 测出 200 就排除了 CF —— **挑战页对 curl 根本不出现**，只有真浏览器才会被弹。

**为什么只有老/自带浏览器挂**：挑战脚本要跑 `fetch`/`Promise`/`WebCrypto`，厂商定制的老 WebView 跑不动 ⇒ 永久停在验证页。
Chrome 能过（新内核）；夸克/UC 也能过（**云加速，实际由它的服务器去取，压根没走客户端这道判定**）。

**2026-10-20 已修并复验**：`browser_check` on→**off**、`security_level` medium→**low**。
改动后三个页面 200，而 5 条 WAF 规则全部照旧拦（curl UA / python-requests / `/wp-login.php` / `/secrets.json` 均 403）⇒ **只开门，没丢锁**。

**用户侧还要做一步**：让他在手机上 **清除该浏览器的数据/缓存**（清掉卡死的 `cf_clearance` cookie）。
若仍卡 ⇒ 上兜底 WAF Skip 规则（GET 且非 `/wp-`）。

> 附带事实：本站 **未开 HSTS**（`security_header.strict_transport_security.enabled=false`）；
> `http://`→`https://`、`www`→根域 均已 301 正常。
> ⚠️ 排障注意：本机常驻代理会毒化 curl（`remote_ip=127.0.0.1`），**测站点必带 `--noproxy '*'`**。
