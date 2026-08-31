---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据持久化

> **本章学习目标**
> - 能够用 ER 图完成数据建模并映射为关系表结构，用 `sqlite3` 与 `SQLAlchemy` 的 DDL 将 ER 落成 `students / courses / enrollments` 三张可运行库表，并说明主键、外键与索引的声明方式
> - 能够对比原生 `sqlite3`、驱动层 `asyncpg`、ORM 层 `SQLAlchemy 2.0` 三境界的抽象代价与适用场景，并用参数化查询规避注入
> - 能够用版本表思想解释数据库迁移（Alembic）的升级与回滚，并用 SQLite 模拟迁移步骤
> - 能够用范式化与反范式化的 trade-off 做出数据建模决策，并在两张表对比中权衡冗余与一致性
> - 能够用 SQLite 与 SQLAlchemy 完成从 ER 建模到建库的完整链路，并说明约束与索引的维护方式

> **为什么需要掌握本章**
> 后端把“可计算”变成“可记忆”靠的就是持久化：请求结束进程就退出，内存随之清空，只有落盘的数据能在下一次请求、重启、扩容后依然可被读取。示例应用的任务状态、转写文本与配置若只留在内存，服务一重启就丢失，用户看到的就是“任务消失”。本章以 `m2t/store.py` 的 SQLite + WAL 为例，把 ER 建模、建库、Python 三层访问、迁移与建模串成一条可验证的链路——让数据既“存得下”也“改得安全”。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清“为什么需要这个概念”，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 3、4 章相同，所有示例均在书仓根目录的 `.venv` 环境中用标准库 `sqlite3` 本地验证，无需真实的 PostgreSQL、网络调用或外部服务；`asyncpg` 与 `SQLAlchemy` 仅作示意围栏讲解，不参与执行。

章内结构如下：

- [5.1 数据建模](5.1_database_modeling_er.md) —— 实体、属性、关系与 ER 图如何映射为表、主键、外键和约束
- [5.2 构建数据库](5.2_building_database.md) —— 用标准库 `sqlite3` 与 SQLAlchemy 声明式模型表达同一套数据库结构
- [5.3 Python 操作数据库](5.3_python_db_three_levels.md) —— 原生 `sqlite3`、驱动层 `asyncpg` 与 ORM 层 SQLAlchemy 的职责和取舍
- [5.4 数据库迁移](5.4_db_migration_alembic.md) —— 用 revision、升级、降级和版本表管理结构演进
- [5.5 数据建模原则](5.5_data_modeling_principles.md) —— 范式化与反范式化：何时拆表、何时冗余

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及示例的片段复用 `m2t.store.TaskStore`（见 [m2t 源码](../../../m2t/store.py) 的精简实现），无需启动真实的 ASR 或 LLM 服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第4章 HTTP 与 RESTful 架构](../chapter04_http_restful/index.md)。

示例（验证本章环境与 `m2t.store.TaskStore` 可用）：

```{code-cell} ipython3
import gc, sys, pathlib, sqlite3

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
del store
gc.collect()  # Windows 上先回收尚未显式关闭的 SQLite 连接，再删除临时文件
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
