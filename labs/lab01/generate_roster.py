#!/usr/bin/env python3
"""
生成 120 份学生作业与 roster.xlsx（公选课 4 班）

学号规则：<年份后两位:2><学院编号:2><专业代号:1><班级号:1><序号:2> = 8 位
班级：261041 / 261042（学院10 专业4）+ 260851 / 260852（学院08 专业5），各 30 人
表头：学号 | 姓名 | 班级 | 原始作业文件名 | 修改后作业文件名（后两列留空）
约束：姓名唯一、源文件名不含学号、修改后格式 学号_姓名_班级.扩展名
"""

import argparse
import random
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

SURNAMES = [
    "张","王","李","刘","陈","杨","赵","黄","周","吴","徐","孙","马","朱","胡","郭","林","何","高","罗",
    "郑","梁","谢","韩","唐","冯","于","杜","董","程","曹","袁","邓","许","傅","沈","曾","彭","吕","苏",
    "魏","蒋","贾","丁","任","姚","卢","姜","崔","钟","谭","陆","汪","范","金","石","廖","夏","韦","付",
]
GIVEN = [
    "伟","芳","娜","洋","静","敏","磊","丽","强","娟","明","杰","英","军","婷","涛","晶","鹏","丹","超",
    "欣","浩","雪","宇","佳","琳","慧","波","勇","艳","晨","阳","涵","熙","睿","琪","轩","梓","妍","怡",
    "萱","烨","豪","瑶","俊","颖","哲","博","涵","玥","彤","萱","烨",
]

EXTS = [".pdf", ".docx", ".zip"]
PATTERNS = [
    "{name}_作业{id}.pdf",
    "{name}-实验报告.docx",
    "{name}的作业.zip",
    "作业_final_{name}.pdf",
]

CLASSES = [
    ("26", "10", "4", "1", "261041"),
    ("26", "10", "4", "2", "261042"),
    ("26", "08", "5", "1", "260851"),
    ("26", "08", "5", "2", "260852"),
]

def gen_id(year: str, college: str, major: str, klass: str, serial: int) -> str:
    return f"{year}{college}{major}{klass}{serial:02d}"

def gen_names(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    pool = set()
    while len(pool) < n:
        s = rng.choice(SURNAMES) + rng.choice(GIVEN) + (rng.choice(GIVEN) if rng.random() < 0.3 else "")
        if 2 <= len(s) <= 3:
            pool.add(s)
    lst = sorted(pool)
    rng.shuffle(lst)
    return lst[:n]

def main():
    parser = argparse.ArgumentParser(description="生成 120 份作业与 roster.xlsx（4班×30）")
    parser.add_argument("--output", default="data/roster.xlsx", help="roster.xlsx 输出路径")
    parser.add_argument("--source", default="data/source", help="作业源目录")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    random.seed(args.seed)

    output = Path(args.output)
    source = Path(args.source)
    output.parent.mkdir(parents=True, exist_ok=True)
    source.mkdir(parents=True, exist_ok=True)
    for p in source.iterdir():
        if p.is_file():
            p.unlink()

    selected = gen_names(120, args.seed + 1)

    students: list[tuple[str, str, str]] = []
    idx = 0
    for year, college, major, klass, class_name in CLASSES:
        for serial in range(1, 31):
            sid = gen_id(year, college, major, klass, serial)
            name = selected[idx]
            idx += 1
            students.append((sid, name, class_name))

    # 打乱文件与表格的对应顺序，但保持班级内学号递增与名单一致
    # 源文件顺序打乱，Excel 按学号排序，便于学生练习“按姓名匹配”而非按行号
    shuffled = students.copy()
    random.shuffle(shuffled)
    for sid, name, klass in shuffled:
        ext = random.choice(EXTS)
        tmpl = random.choice(PATTERNS)
        raw = tmpl.format(name=name, id=random.randint(1, 5))
        raw_stem = Path(raw).stem
        filename = raw_stem + ext
        assert sid not in filename, f"文件名不应含学号: {filename}"
        (source / filename).write_text("", encoding="utf-8")

    students_sorted = sorted(students, key=lambda x: x[0])
    wb = Workbook()
    ws = wb.active
    ws.title = "roster"
    headers = ["学号", "姓名", "班级", "原始作业文件名", "修改后作业文件名"]
    ws.append(headers)
    for col in range(1, 6):
        c = ws.cell(row=1, column=col)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center")
    for sid, name, klass in students_sorted:
        ws.append([sid, name, klass, "", ""])
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 28
    wb.save(output)
    print(f"已生成 {len(students)} 名学生（4班×30）")
    print(f"roster: {output}（5 列，后两列留空，按学号排序）")
    print(f"source: {source}（{len(list(source.iterdir()))} 个文件，文件名不含学号，已打乱）")
    print("班级：261041 / 261042 / 260851 / 260852 各 30 人")
    print("修改后文件名示例：学号_姓名_班级.扩展名，如 26104101_张伟_261041.pdf")

if __name__ == "__main__":
    main()
