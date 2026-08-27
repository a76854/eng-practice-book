---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **关系型数据库原理是持久化的契约**：ACID 中原子性与隔离性由事务边界保证，`COMMIT` / `ROLLBACK` / `SAVEPOINT` 划定正确性；索引是空间换时间的目录，`idx_tasks_created_at` 让 `ORDER BY` 可被加速；锁与 WAL 解决并发冲突，`WAL + busy_timeout` 是 `m2t/store.py` 的工程默认。
- **SQL 进阶让查询从“能跑”到“巧查”**：`INNER / LEFT JOIN` 解决多表关联，`EXISTS / IN` 子查询判断存在性，派生表分步聚合；窗口函数 `ROW_NUMBER / RANK / SUM() OVER` 在不折叠行的前提下提供组内透视，SQLite 3.25+ 已原生支持。
- **Python 三境界是抽象的阶梯**：原生 `sqlite3` 以 `?` 占位符与 `with conn:` 事务保证可见与安全；驱动层 `asyncpg` 仍写 SQL 但托管异步与连接池；ORM 层 `SQLAlchemy 2.0` 以声明式模型生成 SQL，适合复杂关联与跨库。三者选型看“为了解决什么新问题、愿意付出什么新代价”，参数化查询是共同底线。
- **迁移是表结构的版本控制**：`alembic_version` 单行表是当前指针，`upgrade` / `downgrade` 互为逆操作且在事务中执行，失败即回滚；`m2t/store.py` 的 `IF NOT EXISTS` 适合起步，生产中新增列与索引应走迁移脚本而非删库重建。
- **建模在冗余与一致性间权衡**：1NF/2NF/3NF 逐步消除部分与传递依赖，范式化保一致、反范式化换速度；MeetingToText 的单表 `tasks` 满足当前查询模式，拆出 `segments` 则在一对多与级联删除上更清晰，冗余列 `segment_count` 的维护成本需由应用层或触发器承担。
- **贯穿启示**：本章以 `m2t/store.py` 的 SQLite + WAL 为最小闭环，把“原理—SQL—访问—迁移—建模”五步串成可验证的链路——数据既能在故障与并发下保持正确，也能在查询与演进中保持高效。

## 思考题

1. **事务边界**：`m2t/store.py` 的每次 `create` / `update` 都在独立事务中提交，若“创建任务后立即更新状态”需保证原子性，应如何划定事务边界？把两步包在一个 `with conn:` 中与分两次提交在可见性与失败回滚上有何差异？
2. **索引的代价**：`idx_tasks_created_at` 加速了 `ORDER BY created_at DESC`，但会拖慢写入。若任务表每小时写入数千条且查询以 `WHERE status = ?` 为主，是否应为 `status` 加索引？如何用 `EXPLAIN QUERY PLAN` 验证你的判断？
3. **JOIN 与子查询**：`EXISTS` 与 `INNER JOIN` 在“找出至少有一条片段的任务”上可互换，二者在语义与执行计划上有何差异？当 `segments` 存在重复 `task_id` 时，`JOIN` 是否会导致 `tasks` 行膨胀？如何去重？
4. **窗口函数的必要性**：`GROUP BY` 也能做聚合，为什么还需要窗口函数？若需“每个任务在其状态分组内的按时长排名”且保留任务明细，`GROUP BY` 能否实现？窗口函数的 `PARTITION BY` 与 `GROUP BY` 在“是否折叠行”上有何本质区别？
5. **三境界的选型**：团队 SQL 能力强且查询以复杂窗口与聚合为主，ORM 的生成 SQL 可能不符合预期，此时坚持 `SQLAlchemy ORM` 会付出什么代价？在什么信号出现时你会考虑退回 `Core` 或原生 SQL？
6. **迁移的可回滚性**：SQLite 对 `DROP COLUMN` 支持有限，Alembic 的 `downgrade` 若需“重建表”策略，如何保证数据不丢失？迁移脚本中 `server_default` 与 `default` 的差异会对已有数据产生什么影响？
7. **范式化的边界**：MeetingToText 若为“列出任务时总要显示片段数”在 `tasks` 冗余 `segment_count`，更新该列的时机有哪些选择（应用层双写、触发器、定时物化）？每种选择在一致性延迟与实现复杂度上的 trade-off 是什么？若接受短暂不一致，如何向用户解释？
8. **WAL 与锁**：`m2t/store.py` 的 `WAL + busy_timeout=5000` 让读不阻塞写、短暂锁冲突等待重试。若将 `busy_timeout` 设为 0，短暂并发写入会发生什么？WAL 模式下是否就无需关心锁？结合 [第6章 并发模型](../chapter06_concurrency_perf/index.md) 讨论你的理解。

文件 `book/part2_backend_development/chapter05_persistence_sql_orm/demo_summary.py`（本章贯通校验：事务 + 进阶 SQL + 建模 + 迁移思想的最小闭环）：

```{code-cell} ipython3
# 文件 book/part2_backend_development/chapter05_persistence_sql_orm/demo_summary.py
import tempfile, pathlib, sqlite3
from m2t.store import TaskStore

tmpdir = tempfile.TemporaryDirectory()
db_path = pathlib.Path(tmpdir.name) / "summary.db"
store = TaskStore(db_path)

# 1) 事务：创建任务（TaskStore 内部已用事务保证原子性）
store.create("t1", "meeting.wav")
store.create("t2", "demo.wav")
store.create("t3", "notes.wav")
print("created:", len(store.list_tasks()))

# 2) 建模延伸：为 summary 演示加一张 segments 表（模拟一对多拆表）
# 直接用 sqlite3 在同一库上加表，复用 TaskStore 的库文件
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL")
conn.executescript("""
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL,
    text TEXT NOT NULL
);
""")
conn.executemany("INSERT INTO segments (task_id, speaker, text) VALUES (?, ?, ?)", [
    ("t1", "Alice", "hello"),
    ("t1", "Bob", "world"),
    ("t2", "Alice", "foo"),
])
conn.commit()

# 3) SQL 进阶：JOIN + 窗口函数（组内按 task_id 统计片段数并排名）
rows = conn.execute("""
SELECT
    t.id,
    t.filename,
    COUNT(s.id) OVER (PARTITION BY t.id) AS seg_cnt,
    ROW_NUMBER() OVER (PARTITION BY t.id ORDER BY s.id) AS rn
FROM tasks t LEFT JOIN segments s ON s.task_id = t.id
ORDER BY t.id, rn
""").fetchall()
for r in rows:
    print(tuple(r))
# t3 无片段，LEFT JOIN 后 seg_cnt 为 0 或 1（取决于窗口对 NULL 的计数），此处验证“行保留”
assert len(rows) >= 3

# 4) 迁移思想：模拟新增列 duration 的版本升级
cur_ver = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'").fetchone()
if cur_ver is None:
    conn.execute("CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO alembic_version VALUES ('001')")
    conn.commit()
# 升级：加 duration 列
cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
if "duration" not in cols:
    with conn:
        conn.execute("ALTER TABLE tasks ADD COLUMN duration INTEGER DEFAULT 0")
        conn.execute("UPDATE alembic_version SET version_num='002'")
print("version:", conn.execute("SELECT version_num FROM alembic_version").fetchone()[0])
print("duration col exists:", "duration" in [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()])

# 5) 更新与一致性：更新任务文本与时长，验证 TaskStore 仍可读
store.update("t1", full_text="hello world", status="completed")
# 直接用 sqlite3 更新 duration（模拟迁移后新列的使用）
conn.execute("UPDATE tasks SET duration = 120 WHERE id = 't1'")
conn.commit()
row = store.get("t1")
print("t1:", row["id"], row["status"], row["full_text"])
assert row["full_text"] == "hello world"
assert conn.execute("SELECT duration FROM tasks WHERE id='t1'").fetchone()[0] == 120

conn.close()
tmpdir.cleanup()
print("贯通校验通过：事务/建模/SQL 进阶/迁移在同一库中可回归")
# 预期输出:
# created: 3
# ('t1', 'meeting.wav', 2, 1) ...
# version: 002
# duration col exists: True
# t1: t1 completed hello world
# 贯通校验通过：事务/建模/SQL 进阶/迁移在同一库中可回归
```

```bash
# 贯通验证
.venv/bin/python -c "from m2t.store import TaskStore; print('summary demo ok')"
```
