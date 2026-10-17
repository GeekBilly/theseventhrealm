# Cloudflare · 缓存与性能

> 由 `.workbuddy/memory/MEMORY.md` v21 拆分（2026-10-17），**原文未改**。
> 这是「按需读取」层：MEMORY.md 只留索引＋红线摘要，命中本主题才读这里。

---

60/55b. ⚠️ **CF 缓存两条**：① uploads 下 zip 缓存 **4 小时**，覆盖后验证先看 `cf-cache-status`；② **改完页面必清 CDN 缓存**（`deploy-cosmos.py`／`publish.sh` **已内置自动清**，手工改线上用 `cf-cache-rules.py --purge`）。🔴 CF Cache Rules 是 **last-match-wins** ⇒ **bypass 规则必须排最后**。详见 `11-运营/reports/站点性能诊断与优化方案-2026-10-17.md`  
