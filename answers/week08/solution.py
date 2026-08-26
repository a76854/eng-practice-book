"""week08 习题参考答案（hermetic sqlite :memory:/tmp_path 真读写）。

所有函数均为纯函数，不依赖网络或外部服务，sqlite 操作在传入的
Connection 或临时文件中完成，便于测试 hermetic。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    full_text TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """建表与索引（幂等）。"""
    conn.executescript(SCHEMA)
    conn.commit()


def open_db(path: str | Path) -> sqlite3.Connection:
    """按 m2t.store 生产默认打开数据库：WAL + busy_timeout=5000 + 初始化。

    Args:
        path: 数据库文件路径，":memory:" 亦可。
    Returns:
        已初始化的 sqlite3.Connection（row_factory=Row）。
    """
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    # 必须在建表前/后均可执行，教学与生产一致
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    # 幂等建表
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def create_task(
    conn: sqlite3.Connection,
    task_id: str,
    filename: str,
    status: str = "pending",
    full_text: str = "",
    created_at: str = "2026-08-26T10:00:00+00:00",
) -> None:
    """插入一条任务。"""
    conn.execute(
        "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
        (task_id, filename, status, created_at, full_text),
    )
    conn.commit()


def get_task(conn: sqlite3.Connection, task_id: str) -> dict | None:
    """按 id 查询，返回字典或 None。"""
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return dict(row)


def update_task(
    conn: sqlite3.Connection,
    task_id: str,
    status: str | None = None,
    full_text: str | None = None,
    filename: str | None = None,
) -> None:
    """仅更新非 None 的字段。"""
    fields: list[str] = []
    values: list[str] = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if full_text is not None:
        fields.append("full_text = ?")
        values.append(full_text)
    if filename is not None:
        fields.append("filename = ?")
        values.append(filename)
    if not fields:
        return
    values.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", tuple(values))
    conn.commit()


def delete_task(conn: sqlite3.Connection, task_id: str) -> None:
    """删除任务。"""
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()


def list_tasks(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """按 created_at 倒序列出任务。"""
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def insert_two_atomic(conn: sqlite3.Connection, a_id: str, b_id: str) -> None:
    """在同一事务中插入两行；若 b_id == 'boom' 则中途抛异常触发回滚。

    调用方应捕获异常并检查落盘行数为 0。
    """
    with conn:
        conn.execute(
            "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
            (a_id, "a.wav", "pending", "2026-08-26T10:00:00+00:00", ""),
        )
        if b_id == "boom":
            raise RuntimeError("boom")
        conn.execute(
            "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
            (b_id, "b.wav", "pending", "2026-08-26T10:00:01+00:00", ""),
        )
