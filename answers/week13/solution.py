"""week13 习题参考答案（hermetic，mock LLM）。

对应 m2t.llm 的 OpenAI 兼容客户端（timeout/max_retries/脱敏映射）、
templates/presets 的模板选择与 prompts 的装配、以及流式概念镜像。

所有测试均为 hermetic：通过注入 fake OpenAI 客户端与 fake openai 模块
绕过网络，不依赖真实 Key/网络/文件系统。
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from unittest.mock import MagicMock

# ------------------------------------------------------------------
# 0. 确保 openai 模块可被 patch（教学环境默认未装 openai）
# ------------------------------------------------------------------
# m2t.llm 在函数内 `from openai import ...`，若环境未装 openai，
# map_llm_error 会走兜底分支，无法区分四类异常。
# 这里注入一个最小 fake openai 模块，使 isinstance 检查可区分，
# 且 patch("openai.OpenAI") 可用。
try:
    import openai  # type: ignore  # noqa: F401

    _FAKE_OPENAI_INJECTED = False
except ImportError:
    _fake = types.ModuleType("openai")

    class APITimeoutError(Exception):
        def __init__(self, request=None, *args, **kwargs):
            super().__init__(*args)
            self.request = request

    class APIConnectionError(Exception):
        def __init__(self, request=None, message=None, *args, **kwargs):
            super().__init__(message or "connection error")
            self.request = request

    class AuthenticationError(Exception):
        def __init__(self, message=None, response=None, body=None, *args, **kwargs):
            super().__init__(message or "auth error")
            self.response = response
            self.body = body

    class RateLimitError(Exception):
        def __init__(self, message=None, response=None, body=None, *args, **kwargs):
            super().__init__(message or "rate limit")
            self.response = response
            self.body = body

    class OpenAI:  # type: ignore[no-redef]
        def __init__(self, base_url=None, api_key=None, timeout=None, max_retries=None):
            self.base_url = base_url
            self.api_key = api_key
            self.timeout = timeout
            self.max_retries = max_retries
            self.chat = MagicMock()

    _fake.APITimeoutError = APITimeoutError  # type: ignore[attr-defined]
    _fake.APIConnectionError = APIConnectionError  # type: ignore[attr-defined]
    _fake.AuthenticationError = AuthenticationError  # type: ignore[attr-defined]
    _fake.RateLimitError = RateLimitError  # type: ignore[attr-defined]
    _fake.OpenAI = OpenAI  # type: ignore[attr-defined]
    sys.modules["openai"] = _fake
    _FAKE_OPENAI_INJECTED = True

# 现在可安全导入 m2t.llm
from m2t.llm import LLMClient, map_llm_error  # noqa: E402

# ------------------------------------------------------------------
# 1. 模板库（与 MeetingToText backend/app/templates/presets.py 同形）
# ------------------------------------------------------------------
TEMPLATES: dict[str, dict] = {
    "meeting_minutes": {
        "id": "meeting_minutes",
        "name": "标准会议纪要",
        "description": "包含会议主题、参会人员、讨论内容、决定事项和行动项",
        "system_prompt": "你是一位专业的会议记录秘书，擅长从会议转录文字中提取关键信息并整理成结构化的会议纪要。",
        "output_format": "# 会议纪要\n\n## 一、会议基本信息\n- **主题**：{摘要}\n",
    },
    "action_items": {
        "id": "action_items",
        "name": "行动计划",
        "description": "提取会议中的待办事项，含负责人和截止日期",
        "system_prompt": "你是一位高效的项目管理员，负责从会议转录文字中提取所有行动项 (Action Items)。",
        "output_format": "| 优先级 | 行动项 | 负责人 | 截止日期 |",
    },
    "quick_summary": {
        "id": "quick_summary",
        "name": "简要纪要",
        "description": "200字以内的简短摘要，适合快速同步",
        "system_prompt": "请将以下会议转录内容精炼为一段不超过200字的中文摘要。",
        "output_format": "{一行摘要}",
    },
}


def get_template(template_id: str) -> dict | None:
    """按 id 取模板，未知返回 None（与 presets.py 一致）。"""
    return TEMPLATES.get(template_id)


def get_templates() -> list[dict]:
    """返回全部模板列表（id/name/description/system_prompt/output_format）。"""
    return list(TEMPLATES.values())


# ------------------------------------------------------------------
# 2. 提示词装配（与 backend/app/templates/prompts.py 同形）
# ------------------------------------------------------------------
_OUTPUT_FORMAT_SUFFIX = "\n\n请按照以下格式输出：\n{output_format}"
_TRANSCRIPT_SCAFFOLD = "请根据以下会议转录内容生成会议纪要：\n\n=== 会议转录开始 ===\n{transcript}\n=== 会议转录结束 ==="
_CUSTOM_INSTRUCTIONS_SUFFIX = "\n\n额外要求：{custom_instructions}"


def build_minutes_messages(
    template_prompt: str,
    transcript_text: str,
    custom_instructions: str | None,
    output_format_hint: str = "",
) -> list[dict]:
    """装配 chat messages：system 含格式约束，user 含转录与额外要求。"""
    system_prompt = template_prompt
    if output_format_hint:
        system_prompt += _OUTPUT_FORMAT_SUFFIX.format(output_format=output_format_hint)
    user_message = _TRANSCRIPT_SCAFFOLD.format(transcript=transcript_text)
    if custom_instructions:
        user_message += _CUSTOM_INSTRUCTIONS_SUFFIX.format(custom_instructions=custom_instructions)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]


# ------------------------------------------------------------------
# 3. 客户端构造 helpers（供习题 1 使用）
# ------------------------------------------------------------------
def make_client(timeout: float = 60, max_retries: int = 2) -> LLMClient:
    """构造 LLMClient，参数直接透传给 OpenAI。"""
    return LLMClient(
        base_url="https://api.example.com",
        api_key="{API_KEY}",
        model="mock-model",
        timeout=timeout,
        max_retries=max_retries,
    )


def sanitize_error(exc: Exception) -> str:
    """封装 map_llm_error，便于测试脱敏文案与不泄漏。"""
    return map_llm_error(exc)


# ------------------------------------------------------------------
# 4. 流式概念镜像（习题附加）
# ------------------------------------------------------------------
def fake_stream_generate(text: str, chunk_size: int = 5) -> Iterator[str]:
    """将完整文本按 chunk_size 切块 yield，模拟流式分片。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正整数")
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


def collect_stream(chunks: Iterator[str]) -> str:
    """聚合流式分片为完整文本（概念镜像的逆操作）。"""
    return "".join(chunks)
