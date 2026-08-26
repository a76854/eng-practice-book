---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 第8章 数据持久化与 SQL

> 上一章你把「转写」封装成了 HTTP 接口，但重启服务后任务就丢了——因为 `FAKE_DB = {}` 只活在内存里。真实的 MeetingToText 需要把会议、转写结果、用户设置落盘，即使进程重启也能找回。本章把「内存字典」换成 SQLite（SQLite）：用 `sqlite3` 标准库建表、做 CRUD、用事务（transaction）保证原子性、用 WAL（Write-Ahead Logging，预写日志）与 `busy_timeout` 解决并发写入冲突。学完本章，你能为 `m2t.store` 写出带事务与 WAL 的持久层，并解释为什么「显示名可改而文件名不可改」只需改一列。

## 学习目标

完成本章后，你将能够：

1. 能用 `sqlite3` 写 `CREATE TABLE` 建表语句，解释主键、非空约束与索引的作用，并用 `sqlite3.Row` 按列名访问结果。
2. 能编写 CRUD（Create/Read/Update/Delete，增查改删）四类 SQL，并在 Python 中用参数化占位符 `?` 避免注入。
3. 能用 `with conn:` 事务块保证多语句原子性，解释去掉事务后一致性如何被破坏。
4. 能解释 WAL 模式与 `busy_timeout` 对并发读写的意义，并通过 `PRAGMA journal_mode` 验证。

## 先修要求

- 完成 [第1章 环境与项目骨架](chapter01_环境与项目骨架.md)与 [第7章 HTTP 与 REST API](chapter07_HTTP与REST_API.md)（会用 `pytest` 与 `TestClient`）。
- 会 `import m2t.store` 并阅读其 `TaskStore` 轮廓（本章只读参考，不改其源码）。
- 无需 SQL 基础，本章从 `CREATE TABLE` 讲起。

## 正文

### 8.1 为什么需要持久化：从内存字典到 SQLite

内存字典的问题：进程结束，数据消失；多进程各自一份，互不可见。持久化（persistence）指把数据写入磁盘上的数据库文件，进程重启后仍可读取。SQLite 是单文件嵌入式数据库，无需独立服务进程，Python 标准库 `sqlite3` 即开即用，非常适合 MeetingToText 这类单机应用的任务与设置存储。

选择 SQLite 的理由：零运维、单文件易备份、WAL 模式下读写可并发、事务保证原子性。代价是「单写者多读者」的并发模型对高并发写入不如服务端数据库，但对本项目的任务量已足够。

### 8.2 表设计与 CREATE TABLE

MeetingToText 的生产表结构以 `backend/app/services/store.py` 的 `SCHEMA` 为准（只读参考，记录于此）：

```python
# 生产 SCHEMA（简化展示，字段以 HEAD 为准）
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    name TEXT DEFAULT '',
    audio_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    duration REAL DEFAULT 0,
    segments TEXT DEFAULT '[]',
    full_text TEXT DEFAULT '',
    minutes TEXT DEFAULT '',
    error TEXT DEFAULT '',
    progress TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
"""
```

教学版 `m2t.store` 为便于演示精简为 `id/filename/status/created_at/full_text` 四核心列，生产版在此基础上增加了 `name`（显示名）、`audio_path`、`duration`、`segments`、`minutes`、`error`、`progress` 等列，并对 `created_at` 建了降序索引 `idx_tasks_created_at` 以加速 `ORDER BY created_at DESC` 的列表查询。`IF NOT EXISTS` 保证重复执行不报错。

主键（PRIMARY KEY）保证 `id` 唯一；`NOT NULL` 约束拒绝缺失字段；`DEFAULT` 提供缺省值。`app_settings` 用 `key` 作主键存键值对（如 LLM 密钥、模型名）。

可运行示例：用 `:memory:` 内存库建教学表并插入一条记录：

```{code-cell} ipython3
import sqlite3

SCHEMA_MINI = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    full_text TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
"""

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript(SCHEMA_MINI)
# 演示 PRAGMA：WAL 与 busy_timeout 是 m2t.store 的生产默认
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
print("journal_mode:", conn.execute("PRAGMA journal_mode").fetchone()[0])
print("busy_timeout:", conn.execute("PRAGMA busy_timeout").fetchone()[0])

conn.execute(
    "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
    ("t1", "meeting.wav", "done", "2026-08-26T10:00:00+00:00", "大家好"),
)
conn.commit()
row = conn.execute("SELECT * FROM tasks WHERE id = ?", ("t1",)).fetchone()
print(dict(row))
# 索引存在性
idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tasks_created_at'").fetchone()
print("index exists:", idx is not None)
conn.close()
```

要点：`sqlite3.Row` 让 `row["id"]` 按列名访问；所有 SQL 值用 `?` 占位符传入元组，防止拼接注入；`executescript` 可一次执行多条 `CREATE`。

### 8.3 CRUD：增查改删

CRUD 对应四类 SQL：

| 操作 | SQL | Python 方法 |
|---|---|---|
| Create | `INSERT INTO tasks (...) VALUES (?, ...)` | `conn.execute("INSERT ...", (...))` |
| Read | `SELECT * FROM tasks WHERE id = ?` | `conn.execute("SELECT ...", (...)).fetchone()` |
| Update | `UPDATE tasks SET status = ? WHERE id = ?` | `conn.execute("UPDATE ...", (...))` |
| Delete | `DELETE FROM tasks WHERE id = ?` | `conn.execute("DELETE ...", (...))` |

参数化是铁律：`WHERE id = ?` + `(task_id,)` 而非 `f"WHERE id = '{task_id}'"`，后者可被 `"' OR '1'='1"` 注入绕过。

可运行示例：CRUD 完整链路：

```{code-cell} ipython3
import sqlite3

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript(SCHEMA_MINI)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")

# Create
conn.execute(
    "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
    ("t2", "demo.wav", "pending", "2026-08-26T10:01:00+00:00", ""),
)
conn.commit()
print("after insert:", dict(conn.execute("SELECT * FROM tasks WHERE id='t2'").fetchone()))

# Update
conn.execute("UPDATE tasks SET status = ?, full_text = ? WHERE id = ?", ("done", "转写完成", "t2"))
conn.commit()
print("after update:", dict(conn.execute("SELECT * FROM tasks WHERE id='t2'").fetchone()))

# Read list
conn.execute(
    "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
    ("t3", "other.wav", "pending", "2026-08-26T10:02:00+00:00", ""),
)
conn.commit()
rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (10,)).fetchall()
print("list count:", len(rows), "first id:", rows[0]["id"])

# Delete
conn.execute("DELETE FROM tasks WHERE id = ?", ("t2",))
conn.commit()
print("after delete t2:", conn.execute("SELECT * FROM tasks WHERE id='t2'").fetchone())
conn.close()
```

生产中 `m2t.store.TaskStore` 的 `create/get/list_tasks/update/delete` 即对此的封装，区别在于：生产取连接时自动执行 `PRAGMA journal_mode=WAL` 与 `PRAGMA busy_timeout=5000`，并用 `threading.Lock` 串行化写操作。

### 8.4 事务（transaction）：`with conn:` 保证原子性

事务指「多条 SQL 要么全成功，要么全失败」。`sqlite3` 的 `Connection` 对象本身是上下文管理器：`with conn:` 进入时开启事务，块内所有 `execute` 在同一事务中；正常退出自动 `COMMIT`，抛异常则自动 `ROLLBACK`。若不使用事务，每条 `execute` 后立即生效，中途失败会留下半完成状态。

可运行示例：对比有事务与无事务的一致性：

```{code-cell} ipython3
import sqlite3

def demo_with_transaction():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_MINI)
    try:
        with conn:  # 事务块
            conn.execute(
                "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
                ("a1", "a.wav", "pending", "2026-08-26T10:00:00+00:00", ""),
            )
            conn.execute(
                "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
                ("a2", "b.wav", "pending", "2026-08-26T10:00:00+00:00", ""),
            )
            # 模拟中途失败
            raise RuntimeError("中途失败")
    except RuntimeError:
        pass
    rows = conn.execute("SELECT count(*) as c FROM tasks").fetchone()
    print("with 事务, 失败后 count:", rows["c"], "（期望 0，全部回滚）")
    conn.close()

def demo_without_transaction():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_MINI)
    conn.isolation_level = None  # 自动提交，每条语句独立事务
    try:
        conn.execute(
            "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
            ("b1", "a.wav", "pending", "2026-08-26T10:00:00+00:00", ""),
        )
        conn.execute(
            "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
            ("b2", "b.wav", "pending", "2026-08-26T10:00:00+00:00", ""),
        )
        raise RuntimeError("中途失败")
    except RuntimeError:
        pass
    rows = conn.execute("SELECT count(*) as c FROM tasks").fetchone()
    print("无事务, 失败后 count:", rows["c"], "（期望 2，已落盘无法回滚）")
    conn.close()

demo_with_transaction()
demo_without_transaction()
```

生产中 `TaskStore._init_db` 的建表与懒迁移（`ALTER TABLE ADD COLUMN`）也在 `with self._get_conn() as conn:` 块内，最后 `conn.commit()`，保证多语句迁移要么全成要么全回滚。

### 8.5 WAL 与 busy_timeout：并发读写的性能与正确性

SQLite 默认 `journal_mode=DELETE`（回滚日志），写时会锁整个库，读被阻塞。WAL（Write-Ahead Logging，预写日志）把写入追加到 `-wal` 文件，读可并发进行，极大提升「多读少写」场景的吞吐。`PRAGMA journal_mode=WAL` 开启；`PRAGMA busy_timeout=5000` 表示遇到锁时等待最多 5000 毫秒而非立即抛 `database is locked`。

生产 `store.py` 的 `_get_conn()` 每次建连接即执行这两条 PRAGMA，且用 `threading.Lock`（`self._lock`）在进程内串行化写操作：WAL 解决「读写并发」，锁解决「多线程同时写」的竞态，二者互补。

可运行示例：验证 WAL 生效与锁超时：

```{code-cell} ipython3
import sqlite3
import tempfile
import pathlib

# 需落盘文件才能观察 WAL（:memory: 的 WAL 无意义）
with tempfile.TemporaryDirectory() as tmp:
    db_path = str(pathlib.Path(tmp) / "demo.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_MINI)
    # 开启 WAL
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    print("设置后 journal_mode:", row[0])
    # 设 busy_timeout
    conn.execute("PRAGMA busy_timeout=5000")
    print("busy_timeout:", conn.execute("PRAGMA busy_timeout").fetchone()[0])
    # 验证索引加速：查询计划应命中索引
    conn.execute(
        "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
        ("w1", "x.wav", "pending", "2026-08-26T10:00:00+00:00", ""),
    )
    conn.commit()
    plan = conn.execute("EXPLAIN QUERY PLAN SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10").fetchall()
    print("query plan:", [dict(r) for r in plan])
    conn.close()
    # 关闭后 WAL 文件存在性（演示，不强求）
    wal_exists = pathlib.Path(db_path + "-wal").exists()
    print("wal file exists after close:", wal_exists)
```

### 8.6 对照：`m2t.store` 与生产 `store.py` 的设计取舍

`m2t.store.TaskStore`（教学版）与 `backend/app/services/store.py`（生产版）共享同一设计骨架，差异是生产版更完整：

- **表**：教学 `tasks(id, filename, status, created_at, full_text) + idx_tasks_created_at`；生产 `tasks` 额外有 `name/audio_path/duration/segments/minutes/error/progress`，`app_settings(key, value, updated_at)` 存设置，二者均为 `CREATE TABLE IF NOT EXISTS`。
- **连接**：二者 `_get_conn()` 均设 `row_factory = sqlite3.Row`、`PRAGMA journal_mode=WAL`、`PRAGMA busy_timeout=5000`。
- **锁**：生产对所有写方法加 `with self._lock`，教学版可按需加锁（单线程演示可省略，多线程必须）。
- **懒迁移**：生产 `_init_db()` 中 `PRAGMA table_info(tasks)` 查现有列，缺 `name` 或 `progress` 时 `ALTER TABLE ADD COLUMN` 补齐，保证旧库升级不丢数据；教学版建表即完整，无需迁移。
- **设置**：生产的 `get_setting/set_setting/delete_setting` 对 `app_settings` 做 `INSERT ... ON CONFLICT(key) DO UPDATE`，教学聚焦 `tasks`。

延伸参考：同伴特性：任务显示名可改、文件名不可改——生产 `rename(task_id, name)` 只改 `tasks.name` 列，不动 `tasks.filename` 与磁盘文件，这一约束由「显示名可改、文件名不可改」的交互语义决定，存储层仅需 `UPDATE tasks SET name = ? WHERE id = ?`。

### 改动并预测

以下实验均可在本章 `{code-cell}` 或本地 `sqlite3` 中复现。按「改什么 → 预测 → 解释」三段式书写。

#### 改动并预测 实验 1：去掉 `with conn:` 事务块 → 预测一致性破坏

- **改什么**：把 8.4 节 `with conn:` 包裹的两条 `INSERT` 改为裸的两次 `conn.execute(...)` + `conn.commit()`（或设 `isolation_level=None`），并在第二条后抛异常。
- **预测**：`SELECT count(*)` 返回 2 而非 0；第一条已落盘，异常只阻止后续语句，已写入的脏数据残留。若后续查询依赖「两条要么全有要么全无」，会读到半完成状态。
- **解释**：`with conn:` 把多语句包进同一事务，异常触发 `ROLLBACK` 保证原子性；去掉后每条语句独立提交，失败无法回滚。生产 `store.py` 的迁移与批量更新均依赖此机制保证一致性。

#### 改动并预测 实验 2：关掉 WAL（改回 DELETE 模式）→ 预测并发行为差异

- **改什么**：把 `_get_conn()` 中的 `PRAGMA journal_mode=WAL` 改为 `PRAGMA journal_mode=DELETE`（或直接删掉该行），然后用两连接并发：一连接长事务 `BEGIN; INSERT ...` 不提交，另一连接执行 `SELECT * FROM tasks`。
- **预测**：`DELETE` 模式下读会被写阻塞（或立即报 `database is locked`，若 `busy_timeout=0`），`WAL` 模式下读可并发返回旧快照；`PRAGMA journal_mode` 查询返回 `delete` 而非 `wal`。
- **解释**：WAL 把写追加到 `-wal` 文件，读不抢锁；`DELETE` 模式写时持独占锁。`m2t.store` 默认 WAL 正是为了让「前端轮询列表」不被「后台转写更新」阻塞，`busy_timeout=5000` 则让短暂锁冲突等待而非直接失败。

#### 改动并预测 实验 3：删掉 `idx_tasks_created_at` 索引 → 预测查询变化

- **改什么**：把 `SCHEMA` 中的 `CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC)` 删除，重建空库后插入 1000 条任务，分别 `EXPLAIN QUERY PLAN SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10` 并计时。
- **预测**：`EXPLAIN QUERY PLAN` 从 `USING INDEX idx_tasks_created_at` 变为 `USING TEMP B-TREE FOR ORDER BY`（需排序），`LIMIT 10` 仍正确但需全表扫描+排序，耗时随数据量线性增长；结果正确性不变，性能退化。
- **解释**：索引是「按 `created_at` 排好序的副本」，`ORDER BY created_at DESC LIMIT 10` 可直接取索引前 10 行，无需排序。删索引不影响语义，但把「索引扫描」退化为「全表扫描+排序」，生产 `store.py` 对列表查询建此索引正是为此。

#### 改动并预测 实验 4：把 `?` 占位符改成字符串拼接 → 预测注入风险

- **改什么**：把 `conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))` 改为 `conn.execute(f"SELECT * FROM tasks WHERE id = '{task_id}'")`，然后传入 `task_id = "' OR '1'='1"`。
- **预测**：拼接版返回全表（`WHERE id = '' OR '1'='1'` 恒真），参数化版返回 0 行（把恶意串当普通值匹配）；拼接版还可能被 `'; DROP TABLE tasks; --` 破坏结构。
- **解释**：`?` 占位符让驱动把值当「数据」而非「SQL 片段」转义，拼接则把输入混入语法树。`m2t.store` 与生产 `store.py` 全程用 `?`，正是为了在「文件名来自用户上传」的场景下免疫注入。

## 习题

> 参考答案与测试在 `answers/chapter08/`，运行 `.venv/bin/pytest answers/chapter08/ -q` 验证。题目均为 hermetic 纯函数，不依赖网络或外部服务，所有 sqlite 操作均在 `:memory:` 或 `tmp_path` 临时库中完成。

1. **建表**：实现 `init_db(conn: sqlite3.Connection) -> None`，执行 `CREATE TABLE IF NOT EXISTS tasks ...` 与索引，测试断言 `sqlite_master` 中表与索引存在。
2. **插入与查询**：实现 `create_task(conn, task_id, filename, status, full_text)` 与 `get_task(conn, task_id)`，测试断言插入后按 `id` 可查回且字段一致，不存在返回 `None`。
3. **更新**：实现 `update_task(conn, task_id, status=None, full_text=None)`，仅更新非 `None` 字段，测试断言更新后新值生效、未传字段保持不变。
4. **事务回滚**：实现 `insert_two_atomic(conn, a_id, b_id)`，在同一 `with conn:` 中插入两行，中间若 `b_id == "boom"` 则抛异常，测试断言抛异常后两行均未落盘（`count==0`），正常时两行均落盘。
5. **WAL 与 busy_timeout**：实现 `open_db(path: str) -> sqlite3.Connection`，要求返回的连接 `PRAGMA journal_mode` 为 `wal` 且 `PRAGMA busy_timeout` 为 `5000`，测试用 `tmp_path` 落盘库验证。
6. *（附加）* **列表与索引**：实现 `list_tasks(conn, limit=50)` 按 `created_at DESC` 返回，测试断言索引 `idx_tasks_created_at` 存在且列表顺序正确。

## 延伸挑战

1. 给 `tasks` 增加 `name TEXT DEFAULT ''` 列并实现 `rename_task(conn, task_id, name)`，验证 `UPDATE tasks SET name = ? WHERE id = ?` 且 `filename` 不变；思考为什么生产要区分「显示名」与「文件名」。
2. 为 `app_settings` 建表并实现 `get_setting/set_setting`（`INSERT ... ON CONFLICT DO UPDATE`），用 `tmp_path` 验证重启后设置仍可读。
3. 用 `threading.Thread` 各持独立连接并发 `INSERT` 100 条，观察 `WAL + busy_timeout=5000 + threading.Lock` 与「去掉锁且 `busy_timeout=0`」的失败率差异。
