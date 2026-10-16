# MEMORY 归档快照 · 读法

> **为什么改成 `.gz`**：整月日志的归档是纯文本且很大（202610 曾达 **479 KB**），
> 放在 `reports/` 根目录会被宽范围检索命中——一次 accidental Read 就能吃掉会话上下文的一大块。
> 压缩**不是删除**：内容一字不少地完整可读，只是不再对外裸露。这笔账来自
> `上下文成本诊断-20261016.md` 的「自产风险点」。

## 现有归档

| 压缩文件 | 原明文大小 | 压缩后 |
|---|---|---|
| `MEMORY快照-202609-归档.md.gz` | 334 KB | 157 KB |
| `MEMORY快照-202610-归档.md.gz` | 479 KB | 223 KB |

轻量版**不压缩**、保持明文 `MEMORY快照-<YYYYMM>.md`（约 29 KB），因为它才是日常会读的那份。

## 读取方式（不要解包另存）

```
gunzip -c "11-运营/reports/MEMORY快照-202610-归档.md.gz" | head -60        # 只看开头
gunzip -c "11-运营/reports/MEMORY快照-202610-归档.md.gz" | grep -n "关键词"  # 定向捞某一件事
```

## 🔴 纪律

- 日常只需要 `.workbuddy/memory/MEMORY.md` 本体，用不上归档。
- 归档**只在「要查某月某件往事」时**按需 gunzip 定向检索，**绝不整篇读进会话**。
- 每月 1 日 05:45 的 monthly automation 会重新生成明文归档 → 步骤里必须跟着 gzip，
  否则这份 479 KB 每月都会长回来一次。

## 生成链路

`export-memory-snapshot.py --full --month <上年月>` → gzip → `qj-sync.sh auto` 推 Git。
生成的归档 version 入 Git 后就是异地备份，**`.gz` 不被 `.gitignore` 排除**（已实测）。
