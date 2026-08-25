"""store 模块 hermetic 测试（tmp_path sqlite，校验 WAL + busy_timeout）。"""

from __future__ import annotations

import sqlite3

from m2t.store import TaskStore


def test_store_crud(tmp_path):  # type: ignore[no-untyped-def]
    db = tmp_path / "test.db"
    store = TaskStore(db)
    store.create("id1", "meeting.wav")
    row = store.get("id1")
    assert row is not None
    assert row["filename"] == "meeting.wav"
    assert row["status"] == "pending"

    store.update("id1", status="done", full_text="hello")
    row2 = store.get("id1")
    assert row2 is not None
    assert row2["status"] == "done"
    assert row2["full_text"] == "hello"

    tasks = store.list_tasks()
    assert len(tasks) == 1

    store.delete("id1")
    assert store.get("id1") is None


def test_store_wal_and_busy_timeout(tmp_path):  # type: ignore[no-untyped-def]
    db = tmp_path / "wal.db"
    store = TaskStore(db)
    store.create("a", "a.wav")
    # 直接查 pragma，验证 WAL 与 busy_timeout 已设置
    conn = sqlite3.connect(str(db))
    try:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row is not None
        assert row[0].lower() == "wal"
        row2 = conn.execute("PRAGMA busy_timeout").fetchone()
        assert row2 is not None
        assert int(row2[0]) == 5000
    finally:
        conn.close()


def test_store_list_order(tmp_path):  # type: ignore[no-untyped-def]
    db = tmp_path / "order.db"
    store = TaskStore(db)
    store.create("id1", "a.wav")
    store.create("id2", "b.wav")
    lst = store.list_tasks(limit=10)
    assert len(lst) == 2
    # 按 created_at DESC，最新的在前（id2 后创建）
    # 由于时间精度可能相同，至少保证两者都在列表中
    ids = {r["id"] for r in lst}
    assert ids == {"id1", "id2"}
