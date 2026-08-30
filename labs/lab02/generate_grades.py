#!/usr/bin/env python3
"""
生成 120 人的成绩表 grades.csv（公选课场景，含 10 个异常样本）

表头：学号,姓名,班级,课程代号,成绩,等级,备注
- 4 个班各 30 人：261041 / 261042 / 260851 / 260852（正常学号）
- 课程代号固定 6942083555982
- 学号 8 位：<年份2><学院2><专业1><班级1><序号2>
- 成绩 0-100 支持小数；等级/备注留空由学生脚本回填
- 异常：10 个离群低分 + 10 个未来年份学号（30xxxxxx，如 30994502），两者重合为同一批 10 行，便于备注标记
- 表格打乱顺序，不按学号排序
"""
import argparse
import csv
import random
from pathlib import Path

COURSE_ID = "6942083555982"

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

def assign_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"

def main():
    parser = argparse.ArgumentParser(description="生成 120 人成绩表（含10异常，打乱顺序）")
    parser.add_argument("--output", default="grades.csv", help="输出 CSV 路径")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    names = gen_names(120, args.seed + 1)

    students: list[tuple[str, str, str, str, float]] = []
    idx = 0
    for year, college, major, klass, class_name in CLASSES:
        for serial in range(1, 31):
            sid = gen_id(year, college, major, klass, serial)
            name = names[idx]
            idx += 1
            score = round(rng.gauss(76, 12), 1)
            score = max(0.0, min(100.0, score))
            if rng.random() < 0.35:
                score = round(score * 2) / 2
            students.append((sid, name, class_name, COURSE_ID, score))

    # 10 个异常：未来年份学号 + 离群低分，两者重合，替换 10 个正常样本以保持每班 30
    outlier_scores = [12.0, 15.5, 18.5, 22.3, 25.0, 27.0, 30.5, 33.0, 35.5, 37.0]
    abnormal_indices = rng.sample(range(len(students)), 10)
    for j, pos in enumerate(abnormal_indices):
        future_year = str(30 + (j % 10))
        fake_college = rng.choice(["10", "08"])
        fake_major = rng.choice(["4", "5"])
        fake_klass = str(rng.randint(1, 2))
        fake_serial = rng.randint(1, 30)
        sid = gen_id(future_year, fake_college, fake_major, fake_klass, fake_serial)
        while any(s[0] == sid for s in students):
            fake_serial = rng.randint(1, 30)
            sid = gen_id(future_year, fake_college, fake_major, fake_klass, fake_serial)
        _, _, class_name, _, _ = students[pos]
        name = students[pos][1]
        students[pos] = (sid, name, class_name, COURSE_ID, outlier_scores[j])

    rng.shuffle(students)
    all_students = students

    rows = []
    for sid, name, class_name, cid, score in all_students:
        rows.append([sid, name, class_name, cid, str(score), "", ""])

    with open(output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["学号", "姓名", "班级", "课程代号", "成绩", "等级", "备注"])
        w.writerows(rows)

    scores = [float(r[4]) for r in rows]
    import statistics
    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0
    threshold = mean - 2 * stdev
    dist = {g: 0 for g in ["A","B","C","D","F"]}
    for s in scores:
        dist[assign_grade(s)] += 1
    anomalies_score = [r for r in rows if float(r[4]) < threshold]
    anomalies_id = [r for r in rows if int(r[0][:2]) > 26]

    print(f"已生成 {len(rows)} 行 -> {output}（含10异常，打乱顺序）")
    print(f"课程 {COURSE_ID}  正常110+异常10")
    print(f"均分 {mean:.2f}  标准差 {stdev:.2f}  阈值 {threshold:.2f}")
    print(f"最高 {max(scores)}  最低 {min(scores)}  及格率 {sum(1 for s in scores if s>=60)/len(scores)*100:.1f}%")
    print(f"分布 {dist}")
    print(f"成绩离群 {len(anomalies_score)} 人  学号年份异常 {len(anomalies_id)} 人")
    print(f"异常示例 {[(r[0], r[4]) for r in rows if int(r[0][:2])>26][:3]}")

if __name__ == "__main__":
    main()
