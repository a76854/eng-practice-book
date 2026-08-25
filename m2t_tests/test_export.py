"""export 模块 hermetic 测试（伪造 TaskInfo，无需真实 DB）。"""

from __future__ import annotations

import types

from m2t.export import export


def _make_task(**kwargs):  # type: ignore[no-untyped-def]
    # 用 SimpleNamespace 模拟 TaskInfo
    seg1 = types.SimpleNamespace(speaker="说话人1", text="你好", start=0.0, end=1.5)
    seg2 = types.SimpleNamespace(speaker="", text="世界", start=1.5, end=3.0)
    result = types.SimpleNamespace(segments=[seg1, seg2], duration=3.0, full_text="你好 世界")
    task = types.SimpleNamespace(
        id="abc123",
        filename="meeting.wav",
        result=result,
        minutes="",
        **kwargs,
    )
    return task


def test_export_txt_includes_speaker():  # type: ignore[no-untyped-def]
    task = _make_task()
    out = export(task, "txt")
    assert "[说话人1] 你好" in out
    assert "世界" in out


def test_export_srt_format():  # type: ignore[no-untyped-def]
    task = _make_task()
    out = export(task, "srt")
    assert "00:00:00,000 --> 00:00:01,500" in out
    assert "[说话人1] 你好" in out
    assert "1\n" in out


def test_export_md_includes_header_and_minutes():  # type: ignore[no-untyped-def]
    task = _make_task()
    task.minutes = "纪要正文"
    out = export(task, "md")
    assert "# 会议转录" in out
    assert "meeting.wav" in out
    assert "纪要正文" in out
    assert "说话人1" in out


def test_export_dispatcher_case_insensitive():  # type: ignore[no-untyped-def]
    task = _make_task()
    assert export(task, "TXT") == export(task, "txt")
    assert export(task, ".srt") == export(task, "srt")


def test_export_unknown_format_raises():  # type: ignore[no-untyped-def]
    task = _make_task()
    try:
        export(task, "docx")
        assert False, "should raise"
    except ValueError as exc:
        assert "不支持" in str(exc)


def test_export_empty_task():  # type: ignore[no-untyped-def]
    task = types.SimpleNamespace(id="x", filename="empty.wav", result=None, minutes="")
    assert export(task, "txt") == ""
    assert export(task, "srt") == ""
    md = export(task, "md")
    assert "empty.wav" in md
