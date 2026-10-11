#!/usr/bin/env python3
"""把 16 个 <slug>.csv 合并成 all.csv（按年份升序），并做一次体检。

用法：
    /Users/billyhou/.workbuddy/binaries/python/versions/3.13.12/bin/python3 build-all.py

体检项：① 每行是否 4 列 ② 年份能否转整数 ③ 一句话是否超过 30 字
"""
import csv
import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["sanhuang", "xia", "shang", "zhou", "qin", "han", "sanguo", "jin",
         "sui", "tang", "wudai", "song", "yuan", "ming", "qing", "juexing"]

HEADER = ["年份", "事件", "一句话", "所属朝代"]


def main():
    rows = []
    counts = {}
    errors = []

    for slug in ORDER:
        path = os.path.join(HERE, slug + ".csv")
        if not os.path.exists(path):
            errors.append("缺少文件：" + slug + ".csv")
            continue
        # utf-8-sig：兼容可能被编辑器加过 BOM 的文件
        with open(path, encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            local = 0
            for i, row in enumerate(reader, start=1):
                if not row or row[0] == "年份":
                    continue
                if len(row) != 4:
                    errors.append(path + " 第" + str(i) + "行列数=" + str(len(row)))
                    continue
                try:
                    int(row[0])
                except ValueError:
                    errors.append(path + " 第" + str(i) + "行年份非整数：" + row[0])
                if len(row[2]) > 30:
                    errors.append(path + " 第" + str(i) + "行一句话超 30 字：" + row[2])
                rows.append(row)
                local += 1
        counts[slug] = local

    rows.sort(key=lambda r: int(r[0]))

    out = os.path.join(HERE, "all.csv")
    with open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(rows)

    print("朝代节点数：")
    for slug in ORDER:
        print("  %-10s %d" % (slug, counts.get(slug, 0)))
    print("合计节点：%d" % len(rows))
    print("输出：%s" % out)
    if errors:
        print("\n体检问题 %d 处：" % len(errors))
        for e in errors:
            print("  - " + e)
    else:
        print("\n体检通过：列数、年份、一句话长度全部合规。")


if __name__ == "__main__":
    main()
