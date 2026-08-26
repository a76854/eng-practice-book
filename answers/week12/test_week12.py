"""week12 习题测试（hermetic 纯函数，≥5 例）。"""

from __future__ import annotations

import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "week12_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_api_url = _mod.build_api_url  # type: ignore[attr-defined]
task_status_label = _mod.task_status_label  # type: ignore[attr-defined]
task_status_type = _mod.task_status_type  # type: ignore[attr-defined]
task_icon = _mod.task_icon  # type: ignore[attr-defined]
format_duration = _mod.format_duration  # type: ignore[attr-defined]
filter_tasks = _mod.filter_tasks  # type: ignore[attr-defined]


def test_build_api_url_basic() -> None:
    assert build_api_url("/api", "/tasks") == "/api/tasks"
    assert build_api_url("/api/", "/tasks") == "/api/tasks"
    assert build_api_url("/api", "tasks") == "/api/tasks"
    assert build_api_url("/api/", "tasks") == "/api/tasks"
    assert build_api_url("", "/tasks") == "/api/tasks"
    assert build_api_url("  ", "/tasks") == "/api/tasks"
    assert build_api_url("/api", "") == "/api"
    assert build_api_url("/api/", "") == "/api"


def test_build_api_url_edge() -> None:
    assert build_api_url("/api", "/task/123") == "/api/task/123"
    assert build_api_url("http://localhost:8000/api", "/tasks") == "http://localhost:8000/api/tasks"
    assert build_api_url("/api", "//tasks") == "/api/tasks"
    assert build_api_url("/api", "/tasks/") == "/api/tasks/"


def test_task_status_label() -> None:
    assert task_status_label("pending") == "等待中"
    assert task_status_label("processing") == "转写中"
    assert task_status_label("done") == "已完成"
    assert task_status_label("error") == "失败"
    # 未知返回原值
    assert task_status_label("unknown") == "unknown"
    assert task_status_label("") == ""


def test_task_status_type() -> None:
    assert task_status_type("done") == "success"
    assert task_status_type("processing") == "info"
    assert task_status_type("pending") == "warning"
    assert task_status_type("error") == "error"
    assert task_status_type("unknown") == "default"
    assert task_status_type("") == "default"


def test_task_icon() -> None:
    assert task_icon(True, True) == "📋"
    assert task_icon(True, False) == "📋"
    assert task_icon(False, True) == "📝"
    assert task_icon(False, False) == "🎙️"


def test_format_duration() -> None:
    assert format_duration(None) == ""
    assert format_duration(0) == ""
    assert format_duration(-5) == ""
    assert format_duration(5) == "5s"
    assert format_duration(65) == "1m 5s"
    assert format_duration(60) == "1m"
    assert format_duration(3661) == "1h 1m 1s"
    assert format_duration(3600) == "1h"
    assert format_duration(7320) == "2h 2m"


def test_filter_tasks() -> None:
    tasks = [
        {"id": "1", "filename": "meeting.wav", "name": "周会"},
        {"id": "2", "filename": "interview.mp3", "name": ""},
        {"id": "3", "filename": "demo.wav", "name": "Demo Review"},
    ]
    # 空 keyword 返回全部
    assert len(filter_tasks(tasks, "")) == 3
    assert len(filter_tasks(tasks, "   ")) == 3
    # 按 name 匹配
    assert len(filter_tasks(tasks, "周会")) == 1
    assert filter_tasks(tasks, "周会")[0]["id"] == "1"
    # 按 filename 回退（name 为空时）
    assert len(filter_tasks(tasks, "interview")) == 1
    assert filter_tasks(tasks, "interview")[0]["id"] == "2"
    # 大小写不敏感
    assert len(filter_tasks(tasks, "demo")) == 1
    assert len(filter_tasks(tasks, "DEMO")) == 1
    # 无匹配
    assert filter_tasks(tasks, "notfound") == []
    # 不修改原列表
    assert len(tasks) == 3
