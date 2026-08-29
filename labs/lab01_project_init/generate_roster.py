#!/usr/bin/env python3
"""
生成 20 份学生作业与 roster.xlsx

学号规则：<年份后两位:2><学院编号:2><专业代号:1><班级号:1><序号:2> = 8 位
本实验：年份 26，学院 10，专业 4，班级 1/2，序号 01-10/班
表头：学号 | 姓名 | 班级 | 原始作业文件名 | 修改后作业文件名（后两列留空）
约束：姓名唯一、源文件名不含学号、修改后格式 学号_姓名_班级.扩展名
"""
import argparse
import random
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

# 20 个唯一姓名（常见中文名）
NAMES = [
    "张伟","王芳","李娜","刘洋","陈静","杨敏","赵磊","黄丽",
    "周强","吴娟","徐明","孙杰","马丽","朱军","胡英","郭婷",
    "林涛","何晶","高鹏","罗丹",
]

EXTS = [".pdf", ".docx", ".zip"]
PATTERNS = [
    "{name}_作业{id}.pdf",        # 下划线
    "{name}-实验报告.docx",       # 短横线
    "{name}的作业.zip",           # 的字
    "作业_final_{name}.pdf",      # 末尾匹配
]


def gen_id(year: str, college: str, major: str, klass: str, serial: int) -> str:
    return f"{year}{college}{major}{klass}{serial:02d}"


def main():
    parser = argparse.ArgumentParser(description="生成 20 份作业与 roster.xlsx")
    parser.add_argument("--output", default="data/roster.xlsx", help="roster.xlsx 输出路径")
    parser.add_argument("--source", default="data/source", help="作业源目录")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，保证可复现")
    args = parser.parse_args()

    random.seed(args.seed)

    output = Path(args.output)
    source = Path(args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    source.mkdir(parents=True, exist_ok=True)

    # 洗牌后分配班级（各 10 人）
    names = NAMES.copy()
    random.shuffle(names)
    class1 = sorted(names[:10])
    class2 = sorted(names[10:])
    # 为保证学号有序，按姓名排序后编序号
    students = []
    for idx, name in enumerate(class1, start=1):
        sid = gen_id("26", "10", "4", "1", idx)
        students.append((sid, name, "1"))
    for idx, name in enumerate(class2, start=1):
        sid = gen_id("26", "10", "4", "2", idx)
        students.append((sid, name, "2"))

    # 生成源文件（文件名含姓名、不含学号）
    for sid, name, klass in students:
        # 随机选扩展名与模式（保证不含学号）
        ext = random.choice(EXTS)
        # 从模板随机选一个并替换扩展名
        tmpl = random.choice(PATTERNS)
        # 统一扩展名：模板自带扩展名需替换为随机 ext
        raw = tmpl.format(name=name, id=random.randint(1, 5))
        # 去掉原扩展名再拼 ext
        raw_stem = Path(raw).stem
        # 保留分隔符示例的多样性：raw 已含分隔符
        filename = raw_stem + ext
        # 校验：不得含学号
        assert sid not in filename, f"文件名不应含学号: {filename}"
        (source / filename).write_text("", encoding="utf-8")
        # 记录原始文件名到内存（暂不写入 Excel 该列，留空）
        # 但可在控制台展示映射以便自检
        # print(f"{filename} -> {sid}_{name}_{klass}{ext}")

    # 生成 roster.xlsx（5 列，后两列留空）
    wb = Workbook()
    ws = wb.active
    ws.title = "roster"
    headers = ["学号", "姓名", "班级", "原始作业文件名", "修改后作业文件名"]
    ws.append(headers)
    # 样式：表头加粗
    for col in range(1, 6):
        c = ws.cell(row=1, column=col)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
    for sid, name, klass in students:
        ws.append([sid, name, klass, "", ""])
    # 列宽
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 8
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 26
    wb.save(output)
    print(f"已生成 {len(students)} 名学生")
    print(f"roster: {output}（5 列，后两列留空）")
    print(f"source: {source}（{len(list(source.iterdir()))} 个文件，文件名不含学号）")
    # 校验：修改后文件名格式示例
    print("修改后文件名示例：学号_姓名_班级.扩展名，如 26104101_张伟_1.pdf")


if __name__ == "__main__":
    main()
