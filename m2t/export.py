"""转录结果导出（txt / srt / md）。

为什么：MeetingToText 的导出是纯函数（同一任务输入必得同一字符串），
与 HTTP 层无关；抽到本模块后，单测可直接对字符串做快照断言，无需
启动 FastAPI。三种格式覆盖「纯文本 / 字幕 / Markdown」三类常见消费
场景。
"""

from __future__ import annotations

from typing import Any


def _get_segments(task: Any) -> list[Any]:
    if isinstance(task, dict):
        # dict 形态：兼容 store 返回的扁平结构与测试中的手工 dict
        result = task.get("result") or task.get("segments") or []
        if isinstance(result, dict) and "segments" in result:
            segs = result["segments"]
            if isinstance(segs, list):
                return segs
            return []
        if isinstance(result, list):
            return result
        # full_text 兜底不产生段
        return []
    # 对象形态：优先 result.segments，其次 segments 属性
    result = getattr(task, "result", None)
    if result is not None:
        segs = getattr(result, "segments", None)
        if isinstance(segs, list):
            return segs
    segs2 = getattr(task, "segments", None)
    if isinstance(segs2, list):
        return segs2
    return []


def _get_filename(task: Any) -> str:
    if isinstance(task, dict):
        return str(task.get("filename") or task.get("name") or "meeting")
    return str(getattr(task, "filename", None) or getattr(task, "name", None) or "meeting")


def _get_minutes(task: Any) -> str:
    if isinstance(task, dict):
        return str(task.get("minutes") or "")
    return str(getattr(task, "minutes", None) or "")


def _get_task_id(task: Any) -> str:
    if isinstance(task, dict):
        return str(task.get("id") or "")
    return str(getattr(task, "id", None) or "")


def _get_duration(task: Any) -> float:
    if isinstance(task, dict):
        result = task.get("result")
        if isinstance(result, dict):
            try:
                return float(result.get("duration") or 0)
            except (TypeError, ValueError):
                return 0.0
        return 0.0
    result = getattr(task, "result", None)
    if result is not None:
        try:
            return float(getattr(result, "duration", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _format_timestamp_srt(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _seg_text(seg: Any) -> str:
    if isinstance(seg, dict):
        return str(seg.get("text") or "")
    return str(getattr(seg, "text", None) or "")


def _seg_speaker(seg: Any) -> str:
    if isinstance(seg, dict):
        return str(seg.get("speaker") or "")
    return str(getattr(seg, "speaker", None) or "")


def _seg_start(seg: Any) -> float:
    if isinstance(seg, dict):
        try:
            return float(seg.get("start") or 0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(getattr(seg, "start", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _seg_end(seg: Any) -> float:
    if isinstance(seg, dict):
        try:
            return float(seg.get("end") or 0)
        except (TypeError, ValueError):
            return 0.0
    try:
        return float(getattr(seg, "end", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _export_txt(task: Any) -> str:
    segments = _get_segments(task)
    if not segments:
        # 若无段但有 full_text，回退到直接输出
        if isinstance(task, dict):
            return str(task.get("full_text") or "")
        result = getattr(task, "result", None)
        if result is not None:
            ft = getattr(result, "full_text", None)
            if ft:
                return str(ft)
        return str(getattr(task, "full_text", None) or "")
    lines: list[str] = []
    for seg in segments:
        speaker = _seg_speaker(seg)
        text = _seg_text(seg)
        if speaker:
            lines.append(f"[{speaker}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _export_srt(task: Any) -> str:
    segments = _get_segments(task)
    if not segments:
        return ""
    blocks: list[str] = []
    for idx, seg in enumerate(segments, 1):
        blocks.append(str(idx))
        blocks.append(
            f"{_format_timestamp_srt(_seg_start(seg))} --> {_format_timestamp_srt(_seg_end(seg))}"
        )
        speaker = _seg_speaker(seg)
        text = _seg_text(seg)
        if speaker:
            blocks.append(f"[{speaker}] {text}")
        else:
            blocks.append(text)
        blocks.append("")
    return "\n".join(blocks)


def _export_md(task: Any) -> str:
    filename = _get_filename(task)
    task_id = _get_task_id(task)
    duration = _get_duration(task)
    segments = _get_segments(task)
    minutes = _get_minutes(task)

    lines: list[str] = [f"# 会议转录 — {filename}", ""]
    if duration:
        total = int(duration)
        h, total = divmod(total, 3600)
        m, s = divmod(total, 60)
        if h:
            lines.append(f"> 时长: {h}h{m}m{s}s  |  任务ID: `{task_id}`")
        else:
            lines.append(f"> 时长: {m}m{s}s  |  任务ID: `{task_id}`")
        lines.append("")
    if segments:
        for idx, seg in enumerate(segments, 1):
            start_s = int(_seg_start(seg))
            end_s = int(_seg_end(seg))
            sh, sm = divmod(start_s, 3600)
            sm, ss = divmod(sm, 60)
            eh, em = divmod(end_s, 3600)
            em, es = divmod(em, 60)
            start = f"{sh}:{sm:02d}:{ss:02d}" if sh else f"{sm}:{ss:02d}"
            end = f"{eh}:{em:02d}:{es:02d}" if eh else f"{em}:{es:02d}"
            speaker = _seg_speaker(seg) or "未知"
            lines.append(f"## {idx}. [{start}–{end}] {speaker}")
            lines.append("")
            lines.append(_seg_text(seg))
            lines.append("")
    if minutes:
        lines.append("---")
        lines.append("")
        lines.append("# 会议纪要")
        lines.append("")
        lines.append(minutes)
    return "\n".join(lines)


_EXPORTERS: dict[str, Any] = {
    "txt": _export_txt,
    "srt": _export_srt,
    "md": _export_md,
}


def export(task: Any, fmt: str) -> str:
    """按 ``fmt`` 导出任务为字符串。

    为什么提供统一分发：调用方只需 ``export(task, fmt)``，无需记住
    三个函数名；同时便于在未知格式时抛明确异常，而非静默返回空。

    参数:
        task: 任务对象（支持 dict 或带 ``result.segments`` 的对象）
        fmt: ``"txt"`` / ``"srt"`` / ``"md"`` 之一

    返回:
        对应格式的字符串内容。
    """

    key = fmt.lower().strip().lstrip(".")
    fn = _EXPORTERS.get(key)
    if fn is None:
        raise ValueError(f"不支持的导出格式: {fmt}，可选: {', '.join(sorted(_EXPORTERS))}")
    return fn(task)
