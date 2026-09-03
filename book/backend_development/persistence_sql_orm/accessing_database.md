---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据库的访问

学完本节，你能回答：

- SQL 是一门什么样的语言，和 Python 这类命令式语言有何不同？
- 程序如何连上数据库，又如何发出读写命令？
- 增删改查四句 SQL 分别怎么写，参数化与事务各自守住哪条底线？
- SELECT、聚合、JOIN、子查询如何层层递进，把一张或几张表的数据查出来？

> 访问数据库像跟仓库管理员对话。进门先报身份（连接），之后按固定的话术说明要什么（SQL）：入库、出库、改货、查账，各有各的说法。学会这套话术，仓库里的事都可以交给你办。

上一节把四张表建好了。表是容器，但容器自己不会动。数据要写进去、要改、要查出来、要删掉，全靠程序向数据库发命令。发命令的语言就是 SQL。这一节不追求 SQL 的全貌，只把最常用的部分串起来：从连接数据库开始，到安全地写入数据，再到把数据层层查出来。查的部分是重点——单表、聚合、多表 JOIN、子查询，逐步递进。

## 声明式：只要结果，不说步骤

SQL 和 Python 有一个根本区别。Python 是一步步告诉程序“怎么做”，SQL 只告诉数据库“要什么”，怎么做由数据库自己决定。

同一个需求，两种写法放在一起对比就清楚了。Python 里要从一堆学生里找成绩最高的，你得自己遍历、比较、记录：

```python
best = None
for s in students:
    if best is None or s["score"] > best["score"]:
        best = s
```

SQL 里你直接说“按成绩降序取第一行”：

```sql
SELECT * FROM student ORDER BY score DESC LIMIT 1;
```

| 语言 | 表达方式 | 执行细节由谁负责 |
|---|---|---|
| Python | 命令式：一步步说怎么做 | 程序员 |
| SQL | 声明式：只说要什么 | 数据库 |

声明式的好处是简洁、意图清晰；代价是把“怎么做”交给了数据库。数据库打算怎么做，可以通过执行计划看到，这是本节末尾要讲的。

SQL 不止管查询。建表是它的一部分，增删改查也是它的一部分：

| 类别 | 作用 | 例子 |
|---|---|---|
| DDL | 定义表结构 | CREATE TABLE |
| DML | 读写数据 | INSERT、UPDATE、DELETE、SELECT |

上一节建表用的就是它，这一节用它的读写能力。

## 程序怎么连上数据库

访问数据库的第一步是建立连接。`sqlite3.connect` 打开一个数据库文件，`:memory:` 表示建在内存里。连接之后拿到游标，一切读写都通过它执行：

```python
import sqlite3

conn = sqlite3.connect("app.db")   # 连接一个库文件
cur = conn.cursor()                 # 游标，负责执行 SQL 与取结果
```

连接管资源，游标管操作。查询拿结果、写入后提交，都走游标。真实项目里连接会换成连接池、游标会换成 ORM 会话，但都建立在这套底子上。

## 四句 SQL：增删改查

读写的核心是四句 SQL：

| 操作 | SQL | 说明 |
|---|---|---|
| 增 | INSERT INTO ... VALUES (...) | 插入一行 |
| 查 | SELECT ... FROM ... WHERE ... | 按条件读数据 |
| 改 | UPDATE ... SET ... WHERE ... | 更新满足条件的行 |
| 删 | DELETE FROM ... WHERE ... | 删除满足条件的行 |

WHERE 是四句共有的关键，它圈定操作作用在哪些行上。不带 WHERE 的 UPDATE 和 DELETE 会作用到整张表——这是写 SQL 时最容易出问题的地方。

## 数据准备

先准备好四张表和示例数据，后续查询都基于这些数据运行：

```{code-cell} python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript("""
CREATE TABLE teacher (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    office TEXT NOT NULL
);
CREATE TABLE student (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    dept TEXT NOT NULL
);
CREATE TABLE course (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL,
    teacher_id TEXT NOT NULL REFERENCES teacher(id)
);
CREATE TABLE enrollment (
    student_id TEXT NOT NULL REFERENCES student(id),
    course_id TEXT NOT NULL REFERENCES course(id),
    score INTEGER,
    semester TEXT NOT NULL,
    PRIMARY KEY (student_id, course_id)
);
INSERT INTO teacher VALUES
    ('T001', '李国华', '理科楼301'),
    ('T002', '王慧', '理科楼205'),
    ('T003', '陈明', '工科楼410');
INSERT INTO student VALUES
    ('20240101', '张三', '计算机'),
    ('20240102', '李四', '软件'),
    ('20240103', '王五', '计算机'),
    ('20240201', '赵六', '软件'),
    ('20240202', '孙七', '计算机');
INSERT INTO course VALUES
    ('C101', '数据库原理', 3, 'T001'),
    ('C102', '操作系统', 4, 'T002'),
    ('C103', '编译原理', 3, 'T003');
INSERT INTO enrollment VALUES
    ('20240101', 'C101', 88, '2025春'),
    ('20240102', 'C101', 92, '2025春'),
    ('20240101', 'C102', 78, '2025春'),
    ('20240103', 'C102', 60, '2025春'),
    ('20240201', 'C103', 85, '2025秋');
""")
conn.commit()
print("students:", conn.execute("SELECT COUNT(*) FROM student").fetchone()[0])
print("courses:", conn.execute("SELECT COUNT(*) FROM course").fetchone()[0])
print("enrollments:", conn.execute("SELECT COUNT(*) FROM enrollment").fetchone()[0])
```

注意孙七（20240202）一门课都没选，这个细节在后面 JOIN 的演示里会用到。

## 参数化：值永远与 SQL 分离

把用户输入拼进 SQL 字符串是数据库访问里最危险的操作。攻击者输入一段精心构造的字符串，就能改变 SQL 的语义。看一个具体的场景：

```python
# 危险：字符串拼接
user_input = "20240101' OR '1'='1"
cur.execute(f"SELECT * FROM student WHERE id = '{user_input}'")
# 实际执行的 SQL 变成了：
# SELECT * FROM student WHERE id = '20240101' OR '1'='1'
# '1'='1' 永远为真，所以返回了所有学生
```

用户输入变成了 SQL 的一部分。如果输入里包含 `; DROP TABLE student; --`，后果更严重。

参数化把“值”和“SQL 语句”拆成两块：SQL 里用 `?` 占位，值单独作为参数传入，由驱动安全地填入。无论用户输入什么，它都只是一个普通的值，不可能变成指令：

```python
# 安全：占位符
cur.execute("SELECT * FROM student WHERE id = ?", (user_input,))
```

## 事务：要么全做，要么全不做

一组相关操作往往不可分割。选课要同时写入选课记录并更新课程统计，两步少一步就乱了。事务把一组操作打包：全部成功才提交，任一步失败就整体回滚。

`sqlite3` 里 `with conn:` 帮你管好了这件事：块内正常结束自动提交，抛出异常自动回滚：

```python
with conn:
    conn.execute("INSERT INTO enrollment VALUES (?, ?, ?, ?)", ("20240103", "C103", 70, "2025秋"))
    conn.execute("INSERT INTO enrollment VALUES (?, ?, ?, ?)", ("20240101", "C101", 95, "2025春"))
# 块内任一句失败，两笔写入一起回滚
```

## 单表查询：从一张表里挑数据

最基础的查询由几个子句拼成，每个子句负责一道筛选：

| 子句 | 作用 |
|---|---|
| SELECT 列 | 选哪些列 |
| FROM 表 | 从哪张表 |
| WHERE 条件 | 留下哪些行 |
| ORDER BY 列 | 按什么排序 |
| LIMIT 数量 | 最多取多少行 |

顺序是固定的。一条查询从左到右读下来，就是一道一道筛下去：

```{code-cell} python
rows = conn.execute("""
SELECT * FROM enrollment WHERE course_id = 'C101' ORDER BY score DESC LIMIT 2
""").fetchall()
print([dict(r) for r in rows])
```

`WHERE course_id = 'C101'` 选出 C101 的选课记录，`ORDER BY score DESC` 按分数从高到低排，`LIMIT 2` 只取前两条。

## 聚合：把行压成统计值

单表查询返回的是一行行的原始数据，聚合则把一组行压成一个统计值。

常用聚合函数：

| 函数 | 作用 |
|---|---|
| COUNT(*) | 数行数 |
| SUM(列) | 求和 |
| AVG(列) | 平均值 |
| MAX / MIN | 最大 / 最小值 |

聚合常和 GROUP BY 配合：先按某列分组，再对每组做聚合。统计每门课的选课人数与平均分：

```{code-cell} python
rows = conn.execute("""
SELECT course_id, COUNT(*) AS cnt, AVG(score) AS avg_score
FROM enrollment GROUP BY course_id ORDER BY cnt DESC
""").fetchall()
print([dict(r) for r in rows])
```

按课程分组，数出每门课的人数并算平均分，再按人数排序。五条选课记录被压成了三条统计行。

## JOIN：把散在多张表的数据连起来

数据按建模拆散在多张表里，查询时却常要拼出完整视图。比如“张三的数据库原理是哪位老师教的”，需要同时看到学生、课程、教师三张表。JOIN 就是按关联列把它们连起来。

INNER JOIN 是交集——只返回两边都匹配的行。先看它如何拼出完整视图：

```{code-cell} python
rows = conn.execute("""
SELECT s.name, c.title, t.name AS teacher
FROM enrollment e
JOIN student s ON e.student_id = s.id
JOIN course c ON e.course_id = c.id
JOIN teacher t ON c.teacher_id = t.id
WHERE e.score >= 85
ORDER BY e.score DESC
""").fetchall()
print([dict(r) for r in rows])
```

三次 JOIN 把选课、学生、课程、教师四张表连成一条完整视图。建模时拆出去的外键，正是 JOIN 的连接点。

LEFT JOIN 保左全——左表全部行都保留，右表没有匹配的填空值。它和 INNER JOIN 的差别很直观：

```{code-cell} python
inner = conn.execute("""
SELECT s.name, COUNT(*) AS cnt
FROM student s
JOIN enrollment e ON s.id = e.student_id
GROUP BY s.id ORDER BY s.id
""").fetchall()
print("INNER JOIN 只统计选过课的学生:", [dict(r) for r in inner])

left = conn.execute("""
SELECT s.name, COUNT(e.course_id) AS cnt
FROM student s
LEFT JOIN enrollment e ON s.id = e.student_id
GROUP BY s.id ORDER BY s.id
""").fetchall()
print("LEFT JOIN 保留没选课的学生:", [dict(r) for r in left])
```

孙七一门课没选，INNER JOIN 把他整个丢掉，LEFT JOIN 保留他并把选课数记成 0。

## 子查询：把查询结果当值用

WHERE 的条件除了常量，还可以是另一条查询的结果。子查询就是把查询当值用。典型场景是 EXISTS，判断“是否存在满足条件的行”：

```{code-cell} python
rows = conn.execute("""
SELECT name FROM student s
WHERE EXISTS (
    SELECT 1 FROM enrollment e WHERE e.student_id = s.id
)
""").fetchall()
print([r["name"] for r in rows])
```

外层查询遍历每个学生，内层查询回答“他有没有选课记录”，EXISTS 只要存在就放行。同样的结果用 JOIN 也能拼出来，但 EXISTS 表达的是“是否存在”，不会因关联表出现重复行而膨胀结果。

## 索引：为高频查询加速

索引是数据库内部的一张目录，记录某列的值到行位置的映射。查询条件命中索引，就不用全表扫描，直接按目录定位。

- **为什么快**：按目录定位，而非一行行翻
- **代价**：占空间，且每次写入要同步维护索引
- **常见误用**：对几乎每列都建索引，写入变慢却用不上

经验法则：为 WHERE、JOIN、ORDER BY 里高频出现的列建索引。枚举值极少的列（如性别）不必建。索引建没建对不能凭感觉，用执行计划验证。

## 执行计划：看查询到底怎么跑

SQLite 用 EXPLAIN QUERY PLAN 告诉你一条查询会怎么执行——是走索引定位，还是整表扫描：

```{code-cell} python
for label, sql in [
    ("按学号查（有索引）", "SELECT * FROM enrollment WHERE student_id = '20240101'"),
    ("按成绩查（无索引）", "SELECT * FROM enrollment WHERE score >= 85"),
]:
    plan = conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
    print(label, "->", [dict(r)["detail"] for r in plan])
conn.close()
```

带索引的列走 SEARCH（用索引定位），无索引的列只能 SCAN（逐行扫描整表）。索引不是玄学，是执行计划里看得见的路线选择。

## 本节小结

- SQL 是声明式语言，只说要什么结果，怎么做由数据库决定。
- 程序通过连接和游标访问数据库，增删改查四句 SQL 撑起读写，WHERE 决定作用范围。
- 参数化把值和语句分离，防住注入攻击；事务把一组操作打包，保证要么全做要么全不做。
- 单表查询由 SELECT、FROM、WHERE、ORDER BY、LIMIT 层层筛选；聚合与 GROUP BY 把行压成统计值。
- JOIN 按外键把多张表连回完整视图，INNER 取交集、LEFT 保左全；子查询把“是否存在”变成可嵌套的表达。
- 索引以读加速换写成本，为高频查询列建；执行计划能看见查询怎么跑，走索引是 SEARCH、不走是 SCAN。

> 表把数据拆开存，SQL 把它们连起来用；值永远与语句分离，一组操作永远打包，访问数据库才既安全又一致。