---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据库的建立

学完本节，你能回答：

- 如何把一张 ER 图变成数据库里真实存在的表？
- 主键、外键、非空、CHECK 这些约束分别在哪里声明？
- 表结构之后要改，正确的方式是什么？

> 建库像隔房间。先砌墙把空间划开（建表），再标好门牌与通道（主键外键）。墙和门牌各有各的位置，先把它们立稳，再谈别的。隔好了，东西才不会堆成一片，将来加人加物，也知道往哪放。

上一节拆出了四张表——学生、教师、课程、选课——每一份事实各归其位。但这只是画在纸上的图。要让数据库真的接受这些数据，还有一步要走：你得用数据库听得懂的语言，把表“说”出来。

这个语言叫 SQL（结构化查询语言）。你告诉它表的名称、有哪些列、每列存什么类型，它就按这个格式接收数据。

这一节不做 SQL 的系统讲解，只把建表当成一项工具来用：用最轻量的 SQLite 演示，把 ER 图落成真实存在的表。

## 先建表，再存数

建库做的核心一件事：把各表的列、类型、约束定下来，这叫表结构。表结构在建表语句里一次定义完成，之后表就按这个结构接收数据。数据可以增删改，但结构是“骨架”，轻易不变。

SQLite 是 Python 标准库自带的轻量数据库，无需安装、无需服务进程，数据存进一个文件或直接放在内存里，最适合教学与本地工具。下面的表结构沿用 5.1 拆出的四张表：学生、教师、课程、选课。

## 把图画进数据库

直接把四张表建出来，这一步只做定义，不写任何数据。看建表语句比读长篇解释来得快：

```{code-cell} python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("PRAGMA foreign_keys = ON")

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
    credits INTEGER NOT NULL CHECK (credits > 0),
    teacher_id TEXT NOT NULL REFERENCES teacher(id)
);

CREATE TABLE enrollment (
    student_id TEXT NOT NULL REFERENCES student(id) ON DELETE CASCADE,
    course_id TEXT NOT NULL REFERENCES course(id) ON DELETE CASCADE,
    score INTEGER CHECK (score BETWEEN 0 AND 100),
    semester TEXT NOT NULL,
    PRIMARY KEY (student_id, course_id)
);
""")
conn.commit()

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print("tables:", tables)
```

四行建表语句对应四张表。语句本身是人读的，但含义清楚：`CREATE TABLE teacher` 就是建一张教师表，括号里写它的列与约束。建完查看 `tables` 列表，确认四张表都在库里了。

## 约束：写在表上的规则

表建好了，但还有一层关键设计藏在建表语句的细节里：约束。它不是文档里的口号，而是数据库在写入数据时会真正执行的门卫。每一条约束都在拒绝“不该进来的东西”。

**主键**：`PRIMARY KEY` 声明这一列的值能唯一标识一行。学号能唯一标识一个学生，课程号能唯一标识一门课。主键是一行的身份证，不能重复，不能为空。

**外键**：`REFERENCES` 声明这一列的值必须在另一张表的主键里存在。`enrollment.student_id` 引用了 `student.id`，意思是任何一条选课记录里的学号，必须在学生表里找得到。如果试图插入一个不存在的学生，数据库直接拒绝。`ON DELETE CASCADE` 的意思是：如果学生被删了，他所有的选课记录也跟着删——不需要你手动清理。

**非空**：`NOT NULL` 声明这一列必须有值，不能留空。课程名不能为空，学分不能为空——没有名字的课程进不来。

**约束检查**：`CHECK` 声明列的值必须满足某个条件。`credits > 0` 保证学分不会出现负数或 0，`score BETWEEN 0 AND 100` 保证成绩在合法区间。

## 试一试：约束真的会拦人

光看声明不够。约束到底会不会拦人？写几条违反约束的插入语句试一下：

```{code-cell} python
# 先插入一条正常数据做基础
conn.execute("INSERT INTO teacher VALUES (?, ?, ?)", ("T001", "李国华", "理科楼301"))
conn.execute("INSERT INTO student VALUES (?, ?, ?)", ("20240101", "张三", "计算机"))
conn.execute("INSERT INTO course VALUES (?, ?, ?, ?)", ("C101", "数据库原理", 3, "T001"))
conn.execute("INSERT INTO enrollment VALUES (?, ?, ?, ?)", ("20240101", "C101", 88, "2025春"))
conn.commit()
```

```{code-cell} python
# 外键拦截：选课引用一个不存在的学生
try:
    conn.execute("INSERT INTO enrollment VALUES (?, ?, ?, ?)", ("20240999", "C101", 90, "2025春"))
    conn.commit()
    raise AssertionError("外键应拦截")
except sqlite3.IntegrityError as e:
    print("外键拦截（学生不存在）:", e)
    conn.rollback()
```

```{code-cell} python
# 外键拦截：课程引用一个不存在的教师
try:
    conn.execute("INSERT INTO course VALUES (?, ?, ?, ?)", ("C999", "离散数学", 3, "T999"))
    conn.commit()
    raise AssertionError("教师外键应拦截")
except sqlite3.IntegrityError as e:
    print("外键拦截（教师不存在）:", e)
    conn.rollback()
```

```{code-cell} python
# 联合主键拦截：同一学生同一课程重复选课
try:
    conn.execute("INSERT INTO enrollment VALUES (?, ?, ?, ?)", ("20240101", "C101", 70, "2025春"))
    conn.commit()
    raise AssertionError("联合主键应拦截")
except sqlite3.IntegrityError as e:
    print("联合主键拦截:", e)
    conn.rollback()
conn.close()
```

观测结果：外键拦下了不存在的学生和教师引用，联合主键拦下了同一学生同一课程的重复选课。约束不是写在文档里的口号，而是写入时数据库真的会执行的那道门。

## 表结构会演进

表建好了不代表一劳永逸。业务在变，需求在变，表的结构也会跟着变。

最常见的变更是加列。比如后来发现需要记录课程的开设学期，想给 `course` 表加一列 `semester`。正确的方式是 `ALTER TABLE course ADD COLUMN semester TEXT`——这条语句保留已有数据，只做增量变更。生产环境中，这类变更不会手敲 SQL，而是写成带版本号的迁移脚本，可重放、可回滚。迁移脚本的具体形态，到讲 ORM 那一节再对照。

这里只记住一点：**表结构会变，但变要有规矩。** 不要删库重建，不要手动改表结构。加列用 `ALTER TABLE ADD`，删列、改名、改类型要慎重——很多数据库根本不支持这些操作，需要建新表、迁数据、删旧表三步走。

## 本节小结

- 建表语句把 ER 图翻译成数据库能理解的结构，列、类型、约束一次定好。
- 主键标识行的唯一身份，外键连接表与表之间的关系，NOT NULL 和 CHECK 在写入时拦住非法数据。
- 约束不是文档，是数据库执行的门卫，写在表结构里，数据写入时自动生效。
- 表结构会演进，加列用 ALTER TABLE；生产环境中变更由迁移脚本管理版本，而不是手改 DDL。

> 约束长在表结构里，数据才守得住；结构定得稳，数据才放得下。表是墙，约束是门，墙砌歪了，门装再多也挡不住乱。
