---
name: memory-token-doctor
display_name: 谁动了我的Token
display_name_en: TokenDoctor
description: This skill should be used when a user is running a long-running AI project and reports that the assistant keeps forgetting earlier decisions, conversations get slower as the project ages, or token and credit consumption keeps rising without an obvious reason. It measures the size and composition of the project's memory files, identifies the portion that gets injected into every turn but is rarely used, and produces a refactoring draft that converts a bloated memory file into a lean index plus topic files structure, together with a before and after token comparison. Trigger phrases include "who touched my tokens", "memory audit", "memory refactor", "context slimming", "memory index", "project memory compression", and "long project context management".
description_zh: 体检并改造你的长项目记忆文件：算出三个数字，分清「每次都用得上」与「以防万一」，生成「保留／下沉／归档」三段式改造稿，并给出改前改后的 token 对照与三个模板。全程只读，绝不碰你的原文件。
description_en: Diagnose and refactor a long running project's memory files. Reports three numbers, separates what is used every turn from what is paid for nothing, produces a keep, sink, and archive refactoring draft, and gives a before and after token comparison plus three templates. Fully read only, never touches your original files.
version: 1.0.0
agent_created: true
---
# 谁动了我的Token · 记忆体体检与改造

## 适用场景

在以下情况启用本技能：

- 用户反馈「AI 老是忘事」「每次都要重新交代背景」「越聊越慢」「额度掉得莫名其妙」
- 用户询问自己的记忆文件或规则文件该有多大、该怎么组织
- 用户想估算长项目的上下文成本，或想比较改造前后的开销
- 用户提到本技能名称，或说出上述任一触发短语

不适用：单次问答、没有长期记忆需求的场景。此时直接回答，不要运行体检。

## 硬性约束（优先于本文件其余全部内容）

1. **绝不修改、删除、移动用户的原文件**，除非用户明确要求直接改，并逐条列出待改内容请其确认
2. **不联网、不上传、不读取项目目录以外的文件**
3. **不编造成本数字**：用户未提供「每月对话轮数」与「每千 token 单价」时，只给百分比与 token 绝对值
4. **分类结论是建议，不是判决**：判定按启发式规则得出，交付时必须说明这一点
5. **不承诺任何收益**，不出现「每月省 X 元」「一定降到 X」这类话术

## 执行流程

### 第 1 步 · 定位主记忆文件

优先用脚本自动发现；发现失败时向用户询问路径，不要猜测。

```bash
python3 scripts/memory_doctor.py <项目目录> --json
```

自动发现的候选：

- 主文件：`MEMORY.md`、`memory.md`、`MEMORY-主索引.md`、`AGENTS.md`、`CLAUDE.md`，以及根目录内文件名含 `memory` 或「记忆」的 md 文件
- 下沉目录：`记忆库/`、`记忆/`、`memory/`、`memories/`、`docs/memory/`、`.workbuddy/memory/`、`docs/记忆库/`

发现失败时用 `--main <路径>` 与 `--subdir <目录>`（可重复指定）明确指定。

### 第 2 步 · 执行体检

```bash
python3 scripts/memory_doctor.py <项目目录> --main <主文件> --subdir <下沉目录>
```

若用户提供了对话频率与单价，追加 `--rounds <每月轮数> --cost <每千token单价>`，脚本会直接算出每月与每年的节省额。

脚本判定标准（已内置）：

- 主文件超过 **3,000 字符**，几乎必然混入了「以防万一」的内容
- 非保留部分占比超过 **50%**，该文件有一半在为空付代价
- 下沉目录中未被主文件提及的文件是**孤儿文件**，纯占空间
- 主文件提及但磁盘上不存在的文件是**失效引用**，指针已断

### 第 3 步 · 用大白话解释三个数字

体检输出之后，用日常语言讲清三件事，不要复述脚本日志：

1. **记忆文件当前体量** —— 每次对话都要重发一遍的量
2. **其中多少是「每次都用得上」的** —— 其余即为白付的部分
3. **压到目标体量能省多少** —— 同时给绝对值与百分比

成本模型与判断依据见 `references/方法论.md`，第 3 步解释时读取。

### 第 4 步 · 生成改造稿

```bash
python3 scripts/make_index_draft.py <项目目录> --main <主文件> --out <输出路径>
```

产出分为三段：**保留在上层** / **下沉成一行摘要** / **归档**。
每节附体量、建议文件名、存放位置，以及摘要填空位。

脚本只新建文件，绝不触碰原文件。必须在回复中明确告知用户这一点。

### 第 5 步 · 复验（不可省略）

用户完成修改后重新执行第 2 步，将改造前后的第一个数字并列呈现。

**没有前后对照，不算完成交付。**

## 交付给用户的报告结构

1. **三个数字**（体量 / 有效部分 / 冗余占比）
2. **逐节处置表**（保留 / 下沉 / 归档，附体量）
3. **孤儿文件清单**
4. **失效引用清单**
5. **改造前后对照**（字符数、token 数、降幅）
6. **改造稿文件路径**

## 资源使用方式

| 资源 | 用途 | 何时加载 |
|---|---|---|
| `scripts/memory_doctor.py` | 体检，只读 | 第 2 步执行 |
| `scripts/make_index_draft.py` | 生成改造稿，只新建 | 第 4 步执行 |
| `references/方法论.md` | 成本模型、上下文机制、索引模式三原则 | 第 3 步解释时读取 |
| `references/自检清单.md` | 用户自查用清单 | 用户想手动做一遍时提供 |
| `assets/` | 三个模板：索引层 / 单主题档案 / 每日待办 | 交付改造稿时一并给出 |

## 语气

陈述事实与数字，不渲染焦虑，不承诺收益。
用户表达不满时，先承认现象成立，再说明机制与可做的动作。
