"""week08 习题测试（hermetic sqlite 真读写 :memory:/tmp_path）。"""

from __future__ import annotations

import importlib.util
import pathlib
import sqlite3

_spec = importlib.util.spec_from_file_location(
    "week08_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

init_db = _mod.init_db  # type: ignore[attr-defined]
open_db = _mod.open_db  # type: ignore[attr-defined]
create_task = _mod.create_task  # type: ignore[attr-defined]
get_task = _mod.get_task  # type: ignore[attr-defined]
update_task = _mod.update_task  # type: ignore[attr-defined]
delete_task = _mod.delete_task  # type: ignore[attr-defined]
list_tasks = _mod.list_tasks  # type: ignore[attr-defined]
insert_two_atomic = _mod.insert_two_atomic  # type: ignore[attr-defined]
SCHEMA = _mod.SCHEMA  # type: ignore[attr-defined]


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def test_create_table_and_index() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    # 表存在
    tbl = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
    ).fetchone()
    assert tbl is not None
    # 列名齐全
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    assert {"id", "filename", "status", "created_at", "full_text"} <= cols
    # 索引存在
    idx = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tasks_created_at'"
    ).fetchone()
    assert idx is not None
    conn.close()


def test_insert_and_get() -> None:
    conn = _mem_conn()
    create_task(conn, "t1", "meeting.wav", status="done", full_text="hello")
    row = get_task(conn, "t1")
    assert row is not None
    assert row["id"] == "t1"
    assert row["filename"] == "meeting.wav"
    assert row["status"] == "done"
    assert row["full_text"] == "hello"
    # 不存在返回 None
    assert get_task(conn, "nope") is None
    conn.close()


def test_update_keeps_other_fields() -> None:
    conn = _mem_conn()
    create_task(conn, "u1", "a.wav", status="pending", full_text="old")
    update_task(conn, "u1", status="done")
    row = get_task(conn, "u1")
    assert row is not None
    assert row["status"] == "done"
    assert row["full_text"] == "old"  # 未传字段保持
    update_task(conn, "u1", full_text="new")
    row2 = get_task(conn, "u1")
    assert row2 is not None
    assert row2["full_text"] == "new"
    assert row2["status"] == "done"
    conn.close()


def test_delete_and_list() -> None:
    conn = _mem_conn()
    create_task(conn, "d1", "x.wav", created_at="2026-08-26T10:00:00+00:00")
    create_task(conn, "d2", "y.wav", created_at="2026-08-26T10:01:00+00:00")
    assert len(list_tasks(conn)) == 2
    # 倒序：d2 在前
    assert list_tasks(conn)[0]["id"] == "d2"
    delete_task(conn, "d1")
    assert get_task(conn, "d1") is None
    assert len(list_tasks(conn)) == 1
    conn.close()


def test_transaction_rollback() -> None:
    conn = _mem_conn()
    # 正常：两行均落盘
    insert_two_atomic(conn, "a1", "a2")
    assert conn.execute("SELECT count(*) FROM tasks").fetchone()[0] == 2
    # 清空
    conn.execute("DELETE FROM tasks")
    conn.commit()
    # 异常：两行均回滚
    try:
        insert_two_atomic(conn, "b1", "boom")
    except RuntimeError:
        pass
    else:
        assert False, "should have raised"
    assert conn.execute("SELECT count(*) FROM tasks").fetchone()[0] == 0
    conn.close()


def test_wal_and_busy_timeout(tmp_path: pathlib.Path) -> None:
    db_path = tmp_path / "test_wal.db"
    conn = open_db(str(db_path))
    # WAL
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    # busy_timeout
    tout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert tout == 5000
    # 读写可用
    conn.execute(
        "INSERT INTO tasks (id, filename, status, created_at, full_text) VALUES (?, ?, ?, ?, ?)",
        ("w1", "w.wav", "pending", "2026-08-26T10:00:00+00:00", "hi"),
    )
    conn.commit()
    assert get_task(conn, "w1") is not None
    conn.close()


def test_list_order_and_limit() -> None:
    conn = _mem_conn()
    for i in range(5):
        create_task(conn, f"o{i}", f"{i}.wav", created_at=f"2026-08-26T10:0{i}:00+00:00")
    all_rows = list_tasks(conn, limit=50)
    assert len(all_rows) == 5
    # 倒序
    assert all_rows[0]["id"] == "o4"
    assert all_rows[-1]["id"] == "o0"
    # limit 生效
    assert len(list_tasks(conn, limit=2)) == 2
    conn.close()
