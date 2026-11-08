---
name: memory-audit-free
display_name: 记忆体检（免费版）
display_name_en: Memory Audit (Free)
description: This skill should be used when a user wants a quick read only health check of their long running project memory files and wants to know how large their memory file is, how much of it is actually used, and how many characters are being paid for on every single turn. It runs a single audit script that reports three numbers, per section disposition, orphan files and broken references, without modifying anything. Trigger phrases include "memory audit", "how big is my memory file", "context slimming", "free memory check", and "who touched my tokens".
description_zh: 只读体检你的长项目记忆文件：算出体量、多少是真用得上的、剩下多少在每轮白付，并给出逐节处置表、孤儿文件清单与失效引用清单。不修改、不删除、不移动任何文件。
description_en: Read only health check for long running project memory files. Measures total size, how much is actually used every turn, and how much is being paid for for nothing. Reports per section disposition, orphan files, and broken references. Modifies nothing.
version: 1.0.0
agent_created: true
---
# 记忆体检（免费版）

## 适用场景

- 用户想知道自己项目的记忆文件现在有多大、里面有多少是真用得上的
- 用户怀疑「额度被看不见的东西吃掉了」，想先量一量
- 用户只想先了解情况，不打算立刻改造

不适用：需要生成改造稿、需要改前改后对照报告、需要模板的场景 —— 那属于完整版技能。

## 硬性约束

1. **只读**：不修改、不删除、不移动用户的任何文件
2. **不联网、不上传、不读取项目目录以外的文件**
3. **不编造成本数字**：用户未提供「每月对话轮数」与「每千 token 单价」时，只给百分比与 token 绝对值
4. **结论是建议，不是判决**：按启发式规则得出，必须说明这一点

## 执行流程

### 第 1 步 · 定位主记忆文件

```bash
python3 scripts/memory_doctor.py <项目目录> --json
```

自动发现候选：

- 主文件：`MEMORY.md`、`memory.md`、`MEMORY-主索引.md`、`AGENTS.md`、`CLAUDE.md`，以及根目录内文件名含 `memory` 或「记忆」的 md 文件
- 下沉目录：`记忆库/`、`记忆/`、`memory/`、`memories/`、`docs/memory/`、`.workbuddy/memory/`、`docs/记忆库/`

发现失败时用 `--main <路径>` 与 `--subdir <目录>`（可重复指定）指定。

### 第 2 步 · 执行体检

```bash
python3 scripts/memory_doctor.py <项目目录> --main <主文件> --subdir <下沉目录>
```

若用户提供了对话频率与单价，追加 `--rounds <每月轮数> --cost <每千token单价>`。

脚本内置判定标准：

- 主文件超过 **3,000 字符**，几乎必然混入了「以防万一」的内容
- 非保留部分占比超过 **50%**，该文件有一半在为空付代价
- 未被主文件提及的下沉文件是**孤儿文件**
- 主文件提及但磁盘上不存在的文件是**失效引用**

### 第 3 步 · 解释三个数字

用日常语言讲清三件事，不复述脚本日志：

1. **记忆文件当前体量** —— 每次对话都要重发一遍的量
2. **其中多少是「每次都用得上」的** —— 其余即为白付的部分
3. **压到目标体量能省多少** —— 给出绝对值与百分比

### 第 4 步 · 给出下一步（不代做）

体检结束后，指出三条可选动作，并说明完整版技能能多做哪一步：

1. **手动做法**：提供 `references/自检清单.md`，让用户自己照着走一遍
2. **完整版**：可生成改造稿、给出改前改后对照、附带三个模板
3. **什么情况下不用改**：记忆文件本来就很小、结构已经清晰时，说明收益有限

## 交付结构

1. 三个数字（体量 / 有效部分 / 冗余占比）
2. 逐节处置表
3. 孤儿文件清单
4. 失效引用清单
5. 三条下一步建议

## 语气

陈述事实与数字，不渲染焦虑，不承诺收益。
