# Mac mini 端 · 每日自动备份安装指南

> 目标：把 Mac mini 变成**纯备份机** —— 外接移动硬盘，每天凌晨自动从 GitHub 拉一次。  
> 全程约 10 分钟。**所有命令都在 Mac mini 的「终端」里执行**，不是在 📱 手机上。

---

## 零、先确认一件事

这份指南假设你已经把项目推送到了 GitHub。如果还没有，先在 **MacBook** 上完成：  
`sh 11-运营/scripts/qj-sync.sh push "首次提交"`。

---

## 一、准备三样东西

| 项                   | 怎么拿                  | 示例                                              |
| ------------------- | -------------------- | ----------------------------------------------- |
| **仓库地址**            | 已确定，**直接抄**          | `git@github.com:GeekBilly/theseventhrealm.git`  |
| **移动硬盘路径**          | 插上硬盘后跑 `ls /Volumes` | `/Volumes/Backup`                               |
| \** mini 上的项目路径\*\* | 你要把脚本放哪              | `~/WorkBuddy/2026-09-25-15-56-17/11-运营/scripts` |

---

## 二、让 Mac mini 能读 GitHub（二选一）

### 方案 A：SSH（推荐，一次配好不用再管）

```bash
# 1. 生成密钥（一路回车即可）
ssh-keygen -t ed25519 -C "macmini-backup"

# 2. 复制公钥
cat ~/.ssh/id_ed25519.pub
```

把输出整段贴到 GitHub → Settings → SSH and GPG keys → New SSH key。

```bash
# 3. 验证
ssh -T git@github.com
# 看到 Hi xxx! You've successfully authenticated 就成了
```

### 方案 B：HTTPS + Token

GitHub → Settings → Developer settings → Personal access tokens → 生成 **repo** 权限的 token，  
然后 `git clone https://<token>@github.com/用户名/仓库.git`。

---

## 三、把脚本放到 mini 上

mini 上有两种取到脚本的方式：

- **A（推荐）**：直接从 GitHub clone（这一步本身就验证了认证能用）
- **B**：用 U 盘从 MacBook 拷过来

选 A 的话：

```bash
git clone <你的仓库地址> ~/WorkBuddy/2026-09-25-15-56-17
cd ~/WorkBuddy/2026-09-25-15-56-17
```

---

## 四、改配置

编辑 `11-运营/scripts/com.theseventhrealm.backup.plist`，只改两处：

```xml
<key>REPO_URL</key>
<string>git@github.com:GeekBilly/theseventhrealm.git</string>   ← 已定，无需改

<key>BACKUP_ROOT</key>
<string>/Volumes/Backup/第七境备份</string>                ← 你的硬盘

<key>ProgramArguments</key>
<array>
  <string>/bin/zsh</string>
  <string>/Users/billy/WorkBuddy/2026-09-25-15-56-17/11-运营/scripts/backup-pull.sh</string>  ← 实际路径
</array>
```

⚠️ **XML 里不能写 `--` 开头的注释**（会导致 `ExpatError: not well-formed`），改的时候别加注释。

---

## 五、手动跑一次（必须先成功）

```bash
cd ~/WorkBuddy/2026-09-25-15-56-17
sh 11-运营/scripts/backup-pull.sh --once
```

期望看到：

```
→ 首次备份：clone 到 /Volumes/Backup/第七境备份/repo
✅ 首次备份完成
```

### 🔴 如果报错

| 报错                              | 原因                 | 怎么修                 |
| ------------------------------- | ------------------ | ------------------- |
| `移动硬盘未挂载`                       | 硬盘没插好，或路径写错        | `ls /Volumes` 看真实名字 |
| `Permission denied (publickey)` | SSH key 没加到 GitHub | 回第二节重配              |
| `repository not found`          | 地址错，或私有仓库没权限       | 核对 SSH 地址           |

---

## 六、装定时任务（每天 03:00 自动跑）

```bash
# 复制到 LaunchAgents
cp 11-运营/scripts/com.theseventhrealm.backup.plist ~/Library/LaunchAgents/

# 装载
launchctl load -w ~/Library/LaunchAgents/com.theseventhrealm.backup.plist

# 自检（能看到就是装上了）
launchctl list | grep theseventhrealm.backup
```

### 其他命令

```bash
launchctl unload -w ~/Library/LaunchAgents/com.theseventhrealm.backup.plist  # 停
launchctl kickstart gui/$(id -u)/com.theseventhrealm.backup                   # 立刻跑一次
tail -20 /Volumes/Backup/第七境备份/backup.log                                # 看日志
cat /tmp/theseventhrealm-backup.err                                           # 看 launchd 的错误
```

---

## 七、两个必须知道的设定

### 1. mini 必须是「只读」的

脚本会自检：如果发现 `/Volumes/.../repo` 里有人改过文件，会**立刻停止并告警**。

因为架构是 **MacBook 唯一写入端**，mini 一旦也改，pull 就会产生冲突，`--ff-only` 会失败，  
每日备份从此卡住。**所以：别在 mini 的备份目录里改东西。**

### 2. 硬盘没拔/没挂载时会失败

这是**故意的**——宁可让 launchd 重试几次并留下错误日志，也不要「看起来成功其实没备份」。

如果某天硬盘不在，日志会写 `移动硬盘未挂载`，第二天插上就自动恢复。

---

## 八、验证备份真的能用

隔天早上跑一次：

```bash
cd /Volumes/Backup/第七境备份/repo
git log -1 --format='%h %ad %s' --date=format:'%m-%d %H:%M'
du -sh .
```

能看到昨天的 commit 就说明链路通了。

🔑 **终极检验**：把其中一个文件的内容改回一个月前的版本，看能不能 `git checkout` 出来。  
**没做过恢复演练的备份，不算备份。**

---

## 九、⚠️ 恢复时必须知道：脱敏是单向的

仓库里的 `*.md / *.csv / *.txt` 经过了 **clean 过滤器**——苹果中转邮箱在入库瞬间被换成了 `[relay-redacted]`。  
所以你 clone 下来、或从备份恢复出来的，一律是**脱敏版**：

```
[relay-redacted]   →   [relay-redacted]
```

**日常操作不受影响**（MacBook 上跑的是本地原件，一个字没改）。  
但如果有一天真的要从仓库/移动硬盘恢复 MacBook，恢复后必须手工把邮箱填回去——  
真值只有一处权威来源：`11-运营/风险管控/账号与邮箱链路清单.md` 的**本地原件**。

⇒ 这条也意味着：**那份本地原件永远不能删**（它不在 Git 的保护范围内，是唯一的活水源）。

要确认某个是真值还是占位符，看 `grep -c privaterelay` 的结果：`0` 就是脱敏版，`>0` 才是原件。
