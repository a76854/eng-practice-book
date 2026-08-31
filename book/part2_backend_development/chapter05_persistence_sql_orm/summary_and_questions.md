---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **数据建模先回答事实归属**：实体决定哪些对象拥有独立身份，属性描述对象，关系连接对象；主键、外键和约束再把 ER 图变成数据库能够执行的规则。
- **建库不止是创建文件**：DDL 或 SQLAlchemy 模型必须完整表达身份、关系、合法性和访问方式，并通过非法写入与元数据查询验证。SQLite 外键检查应在每个连接上显式启用。
- **访问层级按问题规模选择**：`sqlite3` 保留直接 SQL，`asyncpg` 增加 PostgreSQL 异步协议与连接池，SQLAlchemy 进一步提供表达式和对象映射。参数化查询、明确事务与连接生命周期是共同底线。
- **迁移提供可计算的演进路径**：Alembic revision 记录前后依赖，`upgrade()` 与 `downgrade()` 描述方向，版本表记录当前位置；autogenerate 只生成候选脚本，执行前仍需人工审查和数据恢复方案。
- **范式化与反范式化都要记账**：范式化减少同一事实的重复存储；反范式化为已证实的读取热点复制数据或预计算结果，同时引入同步、补偿和一致性监控成本。
- **贯穿启示**：本章把“识别事实—声明结构—访问数据—演进结构—权衡冗余”连成一条链。持久化的目标不是把数据写进文件，而是让数据在修改、关联和版本变化后仍能被正确解释。

## 思考题

1. **实体边界**：学生手机号、患者手机号或任务文件名是否适合作为主键？业务属性发生变化时，自然键与代理键分别会带来什么影响？
2. **删除语义**：选课记录适合 `ON DELETE CASCADE`，挂号记录为什么可能更适合 `RESTRICT`？如果业务要求保留审计记录，还能直接物理删除父实体吗？
3. **索引取舍**：唯一约束已经为 `students.email` 提供唯一索引，为什么不应再建一个相同普通索引？你会如何用真实查询和执行计划决定新索引？
4. **访问层选型**：只有五张表和少量固定 SQL 的服务，是否值得引入 ORM？当关联、会话生命周期或跨库需求增加到什么程度时，答案会改变？
5. **迁移审查**：若把列重命名，autogenerate 生成“删旧列、加新列”，直接执行可能造成什么后果？应如何把它改成保留数据的迁移？
6. **冗余一致性**：若在 `tasks` 冗余 `segment_count`，应用层事务、触发器和异步汇总三种方案分别由谁维护一致性，失败后如何补偿？

示例（本章贯通校验：事务 + 进阶 SQL + 建模 + 迁移思想的最小闭环）：

```{code-cell} ipython3
import gc, tempfile, pathlib, sqlite3
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
conn.execute("PRAGMA foreign_keys=ON")
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
# t3 无片段，LEFT JOIN 仍保留任务行；COUNT(s.id) 忽略 NULL，因此 seg_cnt 为 0
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
del store
gc.collect()  # Windows 上先回收尚未显式关闭的 SQLite 连接，再删除临时文件
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
