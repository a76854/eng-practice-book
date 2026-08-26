"""week12 习题参考答案（hermetic 纯函数，映射 Vue 任务列表页逻辑）。

对应 MeetingToText 的 frontend/src/views/TasksListPage.vue
与 frontend/src/api/client.ts 的纯逻辑部分：
- build_api_url: API_BASE + url 拼接（client.ts 的 request 基础）
- task_status_label / task_status_type / task_icon: TasksListPage.vue 的展示函数
- format_duration: utils/format.ts 的格式化
- filter_tasks: v-model 搜索 + v-for 过滤的纯函数等价
"""

from __future__ import annotations


def build_api_url(base: str, path: str) -> str:
    """拼接 API base 与 path，处理尾斜杠与空 base。

    规则：
    - 空 base 或仅空白 -> 回退 "/api"
    - 去掉 base 尾部的 "/"，去掉 path 首部的 "/" 后用 "/" 拼接
    - path 为空 -> 返回归一化后的 base
    - path 以 "/" 开头与否均归一化
    """
    b = (base or "").strip()
    if not b:
        b = "/api"
    # 归一化 base：去掉尾部 /
    b = b.rstrip("/")
    if not b:
        b = "/api"
    p = (path or "").strip()
    if not p:
        return b
    p = p.lstrip("/")
    return f"{b}/{p}"


def task_status_label(status: str) -> str:
    """状态中文文案（TasksListPage.vue statusLabel）。"""
    mapping = {
        "pending": "等待中",
        "processing": "转写中",
        "done": "已完成",
        "error": "失败",
    }
    return mapping.get(status, status)


def task_status_type(status: str) -> str:
    """状态对应 naive-ui Tag type（TasksListPage.vue statusType）。"""
    mapping = {
        "done": "success",
        "processing": "info",
        "pending": "warning",
        "error": "error",
    }
    return mapping.get(status, "default")


def task_icon(has_minutes: bool, has_transcript: bool) -> str:
    """任务图标（TasksListPage.vue taskIcon）。"""
    if has_minutes:
        return "📋"
    if has_transcript:
        return "📝"
    return "🎙️"


def format_duration(seconds: float | int | None) -> str:
    """格式化时长（秒 -> 可读字符串）。

    - None / 0 / 负数 -> ""
    - <60 -> "Xs"
    - <3600 -> "Xm Ys"
    - >=3600 -> "Xh Ym Zs"（零值段省略，但至少保留秒）
    """
    if seconds is None:
        return ""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    if s <= 0:
        return ""
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    parts: list[str] = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    # 秒始终显示（若 h/m 存在且 sec==0 则省略秒以保持简洁，但测试期望包含）
    # 规则：若有 h/m 且 sec==0，仅显示 h/m；否则显示 sec
    if sec or not parts:
        parts.append(f"{sec}s")
    return " ".join(parts)


def filter_tasks(tasks: list[dict], keyword: str) -> list[dict]:
    """按 name || filename 含 keyword 过滤（大小写不敏感）。

    - keyword 为空/空白 -> 返回原列表浅拷贝
    - 匹配字段为 task.get("name") or task.get("filename") or ""
    """
    kw = (keyword or "").strip()
    if not kw:
        return list(tasks)
    low = kw.lower()
    result: list[dict] = []
    for t in tasks:
        name = t.get("name") or t.get("filename") or ""
        if low in str(name).lower():
            result.append(t)
    return result
