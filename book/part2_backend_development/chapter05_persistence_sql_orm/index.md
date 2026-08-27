---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第5章 数据持久化：从 SQL 到 ORM

> **本章学习目标**
> - 能够用 ACID 四要素解释事务的原子性与隔离性，并在 SQLite 中演示提交与回滚的边界
> - 能够编写 JOIN、子查询与窗口函数三类进阶 SQL，并在 `sqlite3` 中验证其执行结果
> - 能够对比原生 `sqlite3`、驱动层 `asyncpg`、ORM 层 `SQLAlchemy 2.0` 三境界的抽象代价与适用场景，并用参数化查询规避注入
> - 能够用版本表思想解释数据库迁移（Alembic）的升级与回滚，并用 SQLite 模拟迁移步骤
> - 能够用范式化与反范式化的 trade-off 做出数据建模决策，并在两张表对比中权衡冗余与一致性

> **为什么需要掌握本章**
> 后端把“可计算”变成“可记忆”靠的就是持久化：请求结束进程就退出，内存随之清空，只有落盘的数据能在下一次请求、重启、扩容后依然可被读取。MeetingToText 的任务状态、转写文本与配置若只留在内存，服务一重启就丢失，用户看到的就是“任务消失”。本章以 `m2t/store.py` 的 SQLite + WAL 为贯穿示例，把关系型数据库原理、SQL 进阶、Python 三层访问、迁移与建模串成一条可验证的链路——让数据既“存得下”也“改得安全”。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清“为什么需要这个概念”，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 3、4 章相同，所有示例均在书仓根目录的 `.venv` 环境中用标准库 `sqlite3` 本地验证，无需真实的 PostgreSQL、网络调用或外部服务；`asyncpg` 与 `SQLAlchemy` 仅作示意围栏讲解，不参与执行。

章内结构如下：

- [5.1 关系型数据库原理](5.1_relational_db_principles.md) —— 事务 ACID、隔离级别、索引与锁概览：数据为什么需要“契约”
- [5.2 SQL 进阶](5.2_sql_advanced.md) —— JOIN、子查询、窗口函数：从“查得到”到“查得巧”
- [5.3 Python 操作数据库三境界](5.3_python_db_three_levels.md) —— 原生 `sqlite3` / 驱动层 `asyncpg` / ORM 层 `SQLAlchemy 2.0` 的分层与选型
- [5.4 数据库迁移 Alembic](5.4_db_migration_alembic.md) —— 版本控制与回滚思想：用 SQLite 模拟 Alembic 的迁移步骤
- [5.5 数据建模原则](5.5_data_modeling_principles.md) —— 范式化与反范式化：何时拆表、何时冗余

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t.store.TaskStore`（见 [m2t 源码](../../../m2t/store.py) 的精简实现），无需启动真实的 ASR 或 LLM 服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第4章 HTTP 与 RESTful 架构](../chapter04_http_restful/index.md)。

文件 `book/part2_backend_development/chapter05_persistence_sql_orm/demo_index.py`（验证本章环境与 `m2t.store.TaskStore` 可用）：

```{code-cell} ipython3
import sys, pathlib, sqlite3

import m2t
from m2t.store import TaskStore
import tempfile

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("sqlite3:", sqlite3.sqlite_version)
print("TaskStore:", TaskStore.__name__)
# 最小可用性校验：用 :memory: 建库并走一次 TaskStore 写入
tmpdir = tempfile.TemporaryDirectory()
store = TaskStore(pathlib.Path(tmpdir.name) / "index_check.db")
store.create("demo-index", "demo.wav")
row = store.get("demo-index")
print("store get:", row["id"], row["filename"], row["status"])
tmpdir.cleanup()
print("prefix:", pathlib.Path(sys.prefix).name)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# sqlite3: 3.4x.x
# TaskStore: TaskStore
# store get: demo-index demo.wav pending
# prefix: .venv 或系统前缀
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import sqlite3; print(sqlite3.sqlite_version)"
```
