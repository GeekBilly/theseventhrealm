#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社区发帖备料与体检：只出工单，绝不自动发布。

用法：
  python3 prepare-post.py --post post3        # 体检并生成发布工单（状态：待批）
  python3 prepare-post.py --post post3 --check  # 只体检，不出工单

体检项（对应腾讯云社区过审硬条件）：
  中文字数 ≥800 / 配图 ≥3 且文件存在 / 标题含 WorkBuddy / 无商业与身份敏感词 / 域名出现次数提示
"""
import argparse
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMUNITY = ROOT / "09-社区"
REPORTS = COMMUNITY / "配图"
REQ_DIR = ROOT / "11-运营"

MIN_CHARS = 800
MIN_IMGS = 3
DOMAIN = "theseventhrealm.com"
SENSITIVE = ["卖", "售价", "定价", "收入", "月入", "客户", "买家", "副业", "创业", "盈利", "利润"]


def split_body(text):
    """正文 = 「发布清单」之前的部分"""
    return text.split("## 发布清单")[0]


def cjk_count(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def find_post(name):
    hits = sorted(COMMUNITY.glob(f"{name}-*.md"))
    return hits[0] if hits else None


def next_req_no(today):
    mx = 0
    for p in REQ_DIR.glob(f"REQ-{today}-*.md"):
        m = re.match(rf"REQ-{today}-(\d{{2}})-", p.name)
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{mx + 1:02d}"


def check(path):
    raw = path.read_text(encoding="utf-8")
    body = split_body(raw)
    title = (body.lstrip().split("\n", 1)[0] or "").lstrip("# ").strip()
    imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", body)
    miss = [i for i in imgs if not (COMMUNITY / i).exists()]
    hits = [w for w in SENSITIVE if w in body]
    return {
        "path": path,
        "title": title,
        "chars": cjk_count(body),
        "imgs": imgs,
        "missing": miss,
        "has_workbuddy": "WorkBuddy" in title,
        "domain_hits": body.count(DOMAIN),
        "sensitive": hits,
        "body": body,
    }


def build_req(r, note=""):
    today = dt.date.today().isoformat()
    no = next_req_no(today)
    name = f"REQ-{today}-{no}-社区发文{r['path'].name.split('-')[0]}-执行申请单.md"
    out = REQ_DIR / name
    imgs_md = "\n".join(
        f"| `{i}` | {'✅ 存在' if (COMMUNITY / i).exists() else '❌ 缺失'} |"
        for i in r["imgs"]) or "| （无） | — |"

    doc = f"""# 状态：待批

# REQ-{today}-{no} · 社区发文 · {r['path'].name.split('-')[0]}

> 由 `11-运营/scripts/prepare-post.py` 自动生成。**本工单只做备料与体检，发布动作由用户在平台手动完成**——
> 登录态无法自动化（微信/手机号扫码），且公开发文不可逆，按「上线类改动必须批准」的规矩保留在用户手里。

## 一、发布内容

| 项 | 值 |
|---|---|
| 标题 | {r['title']} |
| 中文字数 | {r['chars']}（门槛 {MIN_CHARS}） |
| 配图 | {len(r['imgs'])} 张（门槛 {MIN_IMGS}） |
| 标签 | **#WorkBuddy**（必带）+ AI 办公 + 效率工具 |
| 来源 | 原创 |
| 专栏 | AI 与大数据 / 云+社区 |
| 入口 | https://cloud.tencent.com/developer → 右上角「写文章」 |
| 稿件 | `{r['path'].relative_to(ROOT)}` |

## 二、配图清单（发布时手动上传，替换正文里的占位链接）

| 文件 | 状态 |
|---|---|
{imgs_md}

## 三、体检结果

| 项 | 结果 |
|---|---|
| 中文字数 ≥{MIN_CHARS} | {'✅' if r['chars'] >= MIN_CHARS else '❌'} {r['chars']} |
| 配图 ≥{MIN_IMGS} 且文件存在 | {'✅' if len(r['imgs']) >= MIN_IMGS and not r['missing'] else '❌ 缺 ' + str(len(r['missing'])) + ' 张'} |
| 标题含 WorkBuddy | {'✅' if r['has_workbuddy'] else '❌'} |
| 无商业/身份敏感词 | {'✅' if not r['sensitive'] else '⚠️ 命中：' + '、'.join(r['sensitive'])} |
| 域名出现次数 | {r['domain_hits']} 处（R-19：出现即建立「个人账号 ↔ 商业项目」的公开连接，保留前请确认） |

## 四、发布步骤（用户执行，约 3 分钟）

1. 浏览器打开 https://cloud.tencent.com/developer，**用与 WorkBuddy 同一微信 / 手机号登录**
2. 右上角「写文章」→ 粘贴正文（`{r['path'].relative_to(ROOT)}` 中「发布清单」以上的全部内容）
3. 上传上表 {len(r['imgs'])} 张配图，替换正文里的 `配图/...` 占位链接
4. 标签填 **WorkBuddy / AI 办公 / 效率工具**；来源选**原创**；专栏选 **AI 与大数据 / 云+社区**
5. 点发布，把文章链接回填本工单「六、验收」

## 五、影响与风险

- **不可逆**：公开发文后可删除，但已被抓取/转载的部分无法收回。
- **R-19（在职金融从业）**：发文会把个人社区账号与商业项目绑定，正文已弱化商业表述（不写卖/收入/销量）；文中含域名 {r['domain_hits']} 处，**是否保留域名由用户拍板**。
- **正收益**：带品牌名 + 平台时间戳＝商标在先使用证据，发布后应截图归档到 `11-运营/风险管控/商标证据/`。
- 审核与到账：**1–3 个工作日**，未到账先查标签与账号一致性，别重复投稿。

## 六、验收

- [ ] 文章已发布，链接：____________
- [ ] 标签含 #WorkBuddy、来源原创、专栏已选
- [ ] 配图 {len(r['imgs'])} 张已正确显示
- [ ] 满 3 个工作日后核对积分是否到账（1000/篇，精选再 +2000）
- [ ] 发布页截图归档至 `11-运营/风险管控/商标证据/`
{note}
"""
    out.write_text(doc, encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", required=True, help="稿件前缀，如 post3")
    ap.add_argument("--check", action="store_true", help="只体检，不出工单")
    args = ap.parse_args()

    path = find_post(args.post)
    if not path:
        print(f"❌ 未找到 09-社区/{args.post}-*.md")
        return 1
    r = check(path)
    print(f"稿件：{path.name}")
    print(f"标题：{r['title']}")
    print(f"中文字数：{r['chars']}（门槛 {MIN_CHARS}）{'✅' if r['chars'] >= MIN_CHARS else '❌'}")
    print(f"配图：{len(r['imgs'])} 张（门槛 {MIN_IMGS}），缺失 {len(r['missing'])} 张"
          f"{'✅' if len(r['imgs']) >= MIN_IMGS and not r['missing'] else '❌'}")
    print(f"标题含 WorkBuddy：{'✅' if r['has_workbuddy'] else '❌'}")
    print(f"域名出现：{r['domain_hits']} 处")
    print(f"敏感词：{'✅ 无' if not r['sensitive'] else '⚠️ ' + '、'.join(r['sensitive'])}")
    if args.check:
        return 0
    out = build_req(r)
    print(f"\n已生成工单：{out.relative_to(ROOT)}（状态：待批）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
