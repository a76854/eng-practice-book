---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据库访问的工程化

学完本节，你能回答：

- 前几节用的手写 SQL 属于哪种访问方式，真实项目里它差在哪？
- 连接池解决什么问题，为什么教学用的 SQLite 不需要它？
- ORM 如何把表和对象对应起来，SQLAlchemy 的 Core 与 ORM 有何区别？
- 表结构演进为什么需要迁移脚本，SQL 与 ORM 何时选哪个？

> 手写 SQL 像自己开车，换挡与路线一概由你掌控，但每次都得亲力亲为；ORM 像请了司机，你只说目的地，它替你开，省力却少了那份精确的控制。

前几节从连接、建表到查询，用的都是同一种方式：`sqlite3` 连上数据库，把 SQL 文本直接交给 `execute`。这是访问数据库最直接的方式，也是本书到目前为止的教学方式。可真实项目里，这条路还有三件事没有交代：连接怎么复用，重复劳动怎么省，表结构变了怎么改。这一节把它们一一补上，引出连接池、ORM 与迁移。

## 直接访问

回到 5.3 的查询，程序是这样和数据库对话的：

```python
import sqlite3

conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("SELECT * FROM student WHERE dept = ?", ("计算机",))
rows = cur.fetchall()
```

程序直接拿着 SQL 文本和数据库对话，这种方式叫直接访问。直接方式透明、零依赖，这正是前几节一直用它、也要求你先把它学扎实的原因。但它把两件事留给了程序员自己：连接的复用，和表结构的演进。真实项目里，这两件事都有专门的工具。

## 手写 SQL 的痛点

把分数大于 80 的学生与课程查出来，手写是这样：

```python
rows = conn.execute(
    "SELECT s.name, c.title, e.score FROM enrollment e "
    "JOIN student s ON e.student_id = s.id "
    "JOIN course c ON e.course_id = c.id "
    "WHERE e.score > ?", (80,)
).fetchall()
```

这段字符串里有三处隐患：表名与字段名是硬编码的字符串，拼错一个字母要到运行时才暴露；JOIN 的关联条件要手写；多几处查询，这些片段就散落各处难以统一修改。

## 连接池

真实项目里，数据库通常是独立运行的服务（PostgreSQL、MySQL 之类），程序每发一条命令都要先建立连接。建连接不是免费的：要握手、鉴权、分配资源。请求一多，反复建连既拖慢程序，也压垮数据库。

连接池的做法是：程序启动时预先建好一批连接，用时借、用完还，连接反复复用。SQLite 之所以前面一直直接 `connect`，是因为它根本不需要这套：

| 数据库 | 形态 | 建连成本 | 适用场景 |
|---|---|---|---|
| SQLite | 文件库，跑在程序进程内 | 几乎为零 | 教学、本地工具、小流量 |
| 服务器数据库 | 独立服务进程 | 握手鉴权分配资源，成本高 | 生产、多程序共享 |

SQLite 的"连接"就是打开一个文件，成本几乎为零；生产库则必须配连接池。ORM 框架（SQLAlchemy）自带连接池，配置一次就不用再管，这是直接方式在真实项目里的第一件工程化装备。

## ORM

ORM 全称对象关系映射（Object Relational Mapping，简称 ORM），做的事就是把数据库映射成程序中的对象。先看"对象"是什么：对象是程序里的概念，前面各章一直在用，类的实例、字典、列表，都是有属性、有方法、能装数据的东西，是程序处理数据最自然的样子。"关系"指关系型数据库，就是 5.1 以来一直在讲的"表"的世界。ORM 把这两个世界连起来：一张表对应成一个类，一行记录对应成一个对象，一条 SQL 对应成一次方法调用。程序只跟对象打交道，创建对象就是插入一行，改属性就是更新，遍历对象就是查询；翻译成 SQL、发给数据库的事，由 ORM 在背后完成。表结构不再写进 SQL 字符串，而是定义在模型类里。下面是 SQLAlchemy 的声明式模型，对应 5.1 拆出的学生、课程与选课三张表：

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey

class Base(DeclarativeBase):
    pass

class Student(Base):
    __tablename__ = "student"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    dept: Mapped[str] = mapped_column(String, nullable=False)

class Course(Base):
    __tablename__ = "course"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    credits: Mapped[int] = mapped_column(nullable=False)

class Enrollment(Base):
    __tablename__ = "enrollment"
    student_id: Mapped[str] = mapped_column(ForeignKey("student.id"), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"), primary_key=True)
    score: Mapped[int | None] = mapped_column(nullable=True)
```

模型定义一次，字段名就有了 Python 层面的类型与属性，编辑器能提示、拼错能告警。同样的查询，ORM 写法变成：

```python
rows = (
    session.query(Enrollment)
    .filter(Enrollment.score > 80)
    .all()
)
# 再通过 relationship 拿到 student.name 与 course.title
```

不用手写 JOIN 与字符串，字段都成了对象属性。这就是 ORM 换来的省力。直接访问和映射方式的差别：

| 方面 | 直接方式（sqlite3 加手写 SQL） | 映射方式（ORM） |
|---|---|---|
| 写什么 | SQL 字符串 | Python 对象与方法 |
| 透明性 | 高| 依赖框架生成，复杂查询可能不如预期 |
| 重复度 | 高，字段名四处硬编码 | 低，模型定义一次处处复用 |
| 依赖 | Python 标准库自带 | 需要额外框架 |

## SQLAlchemy 的两层：Core 与 ORM

写 SQL 文本、写代码构建 SQL、操作对象，其实是三个层次：

| 层次 | 写什么 | 例子 |
|---|---|---|
| 手写 SQL | SQL 字符串 | conn.execute("SELECT ... WHERE ...") |
| 查询构建器（Core） | Python 表达式，逐步拼出查询 | select(student).where(student.dept == "计算机") |
| ORM | 直接操作对象与关系 | session.add(student) |

SQLAlchemy 恰好把后两层都提供了：Core 是底座，负责把 Python 表达式翻译成 SQL；ORM 建在 Core 之上，再往前一步，把表映射成对象。所以复杂查询在 ORM 层写不顺时，可以退回 Core 层，用表达式精确控制，这正是后面对比表里"复杂聚合用 Core 层"的含义。

## 同一查询，SQL 版与 ORM 版

用 5.1 的例子数据，把"分数大于 80 的学生与课程"跑两遍：一遍手写 SQL，一遍 ORM。先跑 SQL 版：

```{code-cell} python
import sqlite3

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript("""
CREATE TABLE student (id TEXT PRIMARY KEY, name TEXT NOT NULL, dept TEXT NOT NULL);
CREATE TABLE course (id TEXT PRIMARY KEY, title TEXT NOT NULL, credits INTEGER NOT NULL);
CREATE TABLE enrollment (
    student_id TEXT NOT NULL REFERENCES student(id),
    course_id TEXT NOT NULL REFERENCES course(id),
    score INTEGER,
    PRIMARY KEY (student_id, course_id)
);
INSERT INTO student VALUES ('20240101', '张三', '计算机'), ('20240102', '李四', '软件');
INSERT INTO course VALUES ('C101', '数据库原理', 3);
INSERT INTO enrollment VALUES ('20240101', 'C101', 85), ('20240102', 'C101', 92);
""")
conn.commit()

rows = conn.execute("""
SELECT s.name, c.title, e.score
FROM enrollment e
JOIN student s ON e.student_id = s.id
JOIN course c ON e.course_id = c.id
WHERE e.score > 80
""").fetchall()
print("SQL 版:", [dict(r) for r in rows])
assert len(rows) == 2
```

SQL 版把表名、字段名、JOIN 条件全部写进字符串，查询怎么执行一目了然。下面用 ORM 定义同样的表结构并灌入同样的数据：

```{code-cell} python
from sqlalchemy import create_engine, String, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

class Base(DeclarativeBase):
    pass

class Student(Base):
    __tablename__ = "student"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    dept: Mapped[str] = mapped_column(String)

class Course(Base):
    __tablename__ = "course"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    credits: Mapped[int] = mapped_column()

class Enrollment(Base):
    __tablename__ = "enrollment"
    student_id: Mapped[str] = mapped_column(ForeignKey("student.id"), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("course.id"), primary_key=True)
    score: Mapped[int | None] = mapped_column()

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)

with Session(engine) as session:
    session.add_all([
        Student(id="20240101", name="张三", dept="计算机"),
        Student(id="20240102", name="李四", dept="软件"),
        Course(id="C101", title="数据库原理", credits=3),
        Enrollment(student_id="20240101", course_id="C101", score=85),
        Enrollment(student_id="20240102", course_id="C101", score=92),
    ])
    session.commit()
print("tables:", sorted(Base.metadata.tables))
```

表结构定义在模型类里，灌数据变成了创建 Python 对象，表名、字段名只出现一次。最后用 ORM 跑同一个查询：

```{code-cell} python
with Session(engine) as session:
    rows = session.execute(
        select(Student.name, Course.title, Enrollment.score)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .join(Course, Enrollment.course_id == Course.id)
        .where(Enrollment.score > 80)
        .order_by(Enrollment.score.desc())
    ).all()
print("ORM 版:", rows)
assert len(rows) == 2
```

查询用 Python 表达式拼出来，表名变成类名、列名变成属性，JOIN 条件也是表达式。终点和 SQL 版一致，写法却和写普通代码是一回事。

## 迁移：表结构演进的版本管理

5.2 说过，生产环境改表结构不能直接改 DDL 删库重建，要写带版本号的迁移脚本。为什么？表里有真实数据，直接改 DDL 会破坏数据；多人协作时，谁改了表、改到哪一版，需要能查、能回放。迁移脚本把"改表结构"变成一条条可执行的版本记录：

```python
# 迁移脚本：给 course 表加一列 capacity（容量）
def upgrade():
    op.add_column("course", sa.Column("capacity", sa.Integer(), nullable=True))

def downgrade():
    op.drop_column("course", "capacity")
```

`upgrade` 是升级到新版本要执行的变更，`downgrade` 是回滚。数据库记录当前版本号，按顺序重放或回滚迁移。ORM 模型改了，通常配一套迁移工具（SQLAlchemy 生态里是 Alembic）自动生成这类脚本，实验四会实操到。

## 择优录用

| 场景 | 选择 | 理由 |
|---|---|---|
| 教学、小工具、本地脚本 | 手写 SQL | 依赖为零，SQL 可见 |
| 表多关系多、需迁移、团队协作 | ORM | 模型复用，配合 Alembic |
| 复杂聚合、窗口函数、精细调优 | 手写 SQL，或 ORM 的 Core 层 | 生成 SQL 难控，退回 SQL 更直接 |

ORM 只是翻译器，底层跑的仍是 SQL，翻出来的东西是否高效，取决于你对 SQL 的理解。所以学习顺序应是先吃透 SQL，再上车 ORM，而不是反过来。生产项目里，连接池、ORM、迁移通常成套出现：SQLAlchemy 自带连接池，配 Alembic 管迁移，这正是实验四要组装起来的形态。

## 本节小结

- 前几节用的是直接方式：sqlite3 加手写 SQL，透明、零依赖，适合教学；真实项目还要补上连接复用、重复劳动、结构演进三件事。
- 连接池复用连接，服务器数据库建连成本高必须用；SQLite 是文件库，建连几乎零成本，所以前面直连没有问题。
- ORM 把表映射成类、行映射成对象，SQLAlchemy 分 Core 与 ORM 两层，复杂查询可退回 Core 层。
- 迁移脚本把改表结构变成带版本号的增量变更，可重放可回滚，模型与迁移配套管理。
- 选型看场景：教学与小工具用手写 SQL，复杂项目用 ORM 配迁移，前提都是先懂 SQL。

> ORM 是翻译，不是魔法；懂 SQL，才握得住 ORM 翻出来的东西。