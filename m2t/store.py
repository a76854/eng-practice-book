"""极简 SQLite 任务存储。

为什么：MeetingToText 用 SQLite 持久化任务与设置，教学中只需最小子集
（id/filename/status/created_at/full_text）即可演示「建表/CRUD/WAL」。
本模块保持单文件、无 ORM，让读者直观看到 SQL 与事务边界。
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
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


class TaskStore:
    """最小任务存储。

    为什么用 WAL + busy_timeout：WAL 允许读写并发，busy_timeout 避免
    多进程/多线程短暂锁冲突直接抛错，二者是 MeetingToText 的生产
    默认，教学中保留可让读者观察到「并发写入不丢数据」的效果。
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def create(
        self,
        task_id: str,
        filename: str,
        status: str = "pending",
        full_text: str = "",
    ) -> None:
        """创建任务。"""
        created_at = datetime.now(UTC).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO tasks (id, filename, status, created_at, full_text)"
                " VALUES (?, ?, ?, ?, ?)",
                (task_id, filename, status, created_at, full_text),
            )
            conn.commit()

    def get(self, task_id: str) -> dict[str, str] | None:
        """按 id 查询，返回字典或 ``None``。"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_tasks(self, limit: int = 50) -> list[dict[str, str]]:
        """按创建时间倒序列出任务。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update(
        self,
        task_id: str,
        *,
        status: str | None = None,
        full_text: str | None = None,
        filename: str | None = None,
    ) -> None:
        """更新指定字段，未传的字段保持不变。"""
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
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )
            conn.commit()

    def delete(self, task_id: str) -> None:
        """删除任务。"""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
