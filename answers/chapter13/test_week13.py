"""week13 习题测试（hermetic，mock LLM）。

覆盖：超时/重试参数透传、脱敏四类中文文案不泄漏、
模板选择、提示词装配、mock 生成成功、mock 超时→脱敏链路、
流式概念镜像。
"""

from __future__ import annotations

import contextlib
import importlib.util
import pathlib
from unittest.mock import MagicMock, patch

# 确保 fake openai 已注入（solution 会注入，这里再兜底）
with contextlib.suppress(ImportError):
    import openai  # type: ignore  # noqa: F401

_spec = importlib.util.spec_from_file_location(
    "week13_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# 导出被测函数
make_client = _mod.make_client  # type: ignore[attr-defined]
sanitize_error = _mod.sanitize_error  # type: ignore[attr-defined]
get_template = _mod.get_template  # type: ignore[attr-defined]
get_templates = _mod.get_templates  # type: ignore[attr-defined]
build_minutes_messages = _mod.build_minutes_messages  # type: ignore[attr-defined]
fake_stream_generate = _mod.fake_stream_generate  # type: ignore[attr-defined]
collect_stream = _mod.collect_stream  # type: ignore[attr-defined]
LLMClient = _mod.LLMClient  # type: ignore[attr-defined]

# 取 fake openai 异常类（无论真实/假）
import openai as _openai  # type: ignore  # noqa: E402

APITimeoutError = _openai.APITimeoutError  # type: ignore[attr-defined]
APIConnectionError = _openai.APIConnectionError  # type: ignore[attr-defined]
AuthenticationError = _openai.AuthenticationError  # type: ignore[attr-defined]
RateLimitError = _openai.RateLimitError  # type: ignore[attr-defined]


def _fake_request():
    try:
        import httpx

        return httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    except Exception:
        return MagicMock()


def test_client_default_params() -> None:
    c = make_client(timeout=60, max_retries=2)
    assert c.timeout == 60
    assert c.max_retries == 2
    c2 = make_client(timeout=5, max_retries=0)
    assert c2.timeout == 5
    assert c2.max_retries == 0


def test_client_passes_timeout_retry_to_openai() -> None:
    with patch("openai.OpenAI") as MockOpenAI:
        llm = make_client(timeout=60, max_retries=2)
        _ = llm.client
        kwargs = MockOpenAI.call_args.kwargs
        assert kwargs["timeout"] == 60
        assert kwargs["max_retries"] == 2

        MockOpenAI.reset_mock()
        llm2 = make_client(timeout=5, max_retries=0)
        _ = llm2.client
        kwargs2 = MockOpenAI.call_args.kwargs
        assert kwargs2["timeout"] == 5
        assert kwargs2["max_retries"] == 0


def test_sanitize_four_categories_and_no_leak() -> None:
    req = _fake_request()
    # 构造各异常（兼容 fake openai 的签名）
    try:
        import httpx

        resp401 = httpx.Response(401, request=req)
        resp429 = httpx.Response(429, request=req)
    except Exception:
        resp401 = MagicMock()
        resp401.status_code = 401
        resp429 = MagicMock()
        resp429.status_code = 429

    # 超时
    _has_req = "request" in APITimeoutError.__init__.__code__.co_varnames
    e1 = APITimeoutError(req) if _has_req else APITimeoutError("timeout")
    msg1 = sanitize_error(e1)
    assert msg1 == "连接 LLM 服务失败，请检查网络或稍后重试"
    # 连接失败
    try:
        e2 = APIConnectionError(request=req)
    except TypeError:
        e2 = APIConnectionError("conn")
    msg2 = sanitize_error(e2)
    assert msg2 == "连接 LLM 服务失败，请检查网络或稍后重试"
    # 鉴权
    try:
        e3 = AuthenticationError("auth failed", response=resp401, body=None)
    except TypeError:
        e3 = AuthenticationError("auth failed")
    msg3 = sanitize_error(e3)
    assert msg3 == "LLM API Key 无效或未授权，请在设置中检查"
    # 限流
    try:
        e4 = RateLimitError("rate", response=resp429, body=None)
    except TypeError:
        e4 = RateLimitError("rate")
    msg4 = sanitize_error(e4)
    assert msg4 == "LLM 服务请求过于频繁，请稍后重试"
    # 兜底且不泄漏：ValueError 含 Key/URL
    dangerous = ValueError("sk-live-abc123 https://api.example.com/v1 堆栈")
    msg5 = sanitize_error(dangerous)
    assert msg5 == "LLM 调用失败，请检查服务可用性或联系管理员"
    for m in (msg1, msg2, msg3, msg4, msg5):
        assert "sk-live" not in m
        assert "https://api.example.com" not in m
        assert "abc123" not in m


def test_template_selection() -> None:
    t = get_template("meeting_minutes")
    assert t is not None
    assert "system_prompt" in t
    assert t["id"] == "meeting_minutes"
    assert get_template("action_items") is not None
    assert get_template("quick_summary") is not None
    assert get_template("unknown") is None
    assert get_template("") is None
    all_templates = get_templates()
    assert len(all_templates) == 3
    ids = {x["id"] for x in all_templates}
    assert ids == {"meeting_minutes", "action_items", "quick_summary"}


def test_build_minutes_messages() -> None:
    # 有 output_format 时 system 追加
    msgs = build_minutes_messages("persona", "转录内容", None, "格式A")
    assert msgs[0]["role"] == "system"
    assert "请按照以下格式输出" in msgs[0]["content"]
    assert "格式A" in msgs[0]["content"]
    assert "=== 会议转录开始 ===" in msgs[1]["content"]
    assert "转录内容" in msgs[1]["content"]
    assert "额外要求" not in msgs[1]["content"]

    # 无 output_format 时不追加
    msgs2 = build_minutes_messages("persona", "转录内容", None, "")
    assert "请按照以下格式输出" not in msgs2[0]["content"]

    # 有 custom_instructions 时 user 追加，None/"" 不追加空段
    msgs3 = build_minutes_messages("persona", "转录", "请用中文", "")
    assert "额外要求" in msgs3[1]["content"]
    assert "请用中文" in msgs3[1]["content"]
    msgs4 = build_minutes_messages("persona", "转录", None, "")
    assert "额外要求" not in msgs4[1]["content"]
    msgs5 = build_minutes_messages("persona", "转录", "", "")
    assert "额外要求" not in msgs5[1]["content"]


def test_mock_generate_success() -> None:
    llm = make_client(timeout=60, max_retries=2)
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="mock 纪要结果"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp
    llm._client = fake_client

    result = llm.generate(
        system_prompt="系统提示",
        user_message="用户转录",
        temperature=0.3,
        max_tokens=100,
    )
    assert result == "mock 纪要结果"
    kwargs = fake_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "mock-model"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][0]["content"] == "系统提示"
    assert kwargs["messages"][1]["role"] == "user"
    assert kwargs["messages"][1]["content"] == "用户转录"
    assert kwargs["temperature"] == 0.3
    assert kwargs["max_tokens"] == 100


def test_mock_generate_timeout_to_sanitized() -> None:
    llm = make_client(timeout=1, max_retries=0)
    req = _fake_request()
    try:
        err = APITimeoutError(req)
    except TypeError:
        err = APITimeoutError("timeout")
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = err
    llm._client = fake_client

    try:
        llm.generate(system_prompt="sys", user_message="user", temperature=0.3, max_tokens=10)
        raise AssertionError("应抛超时异常")
    except Exception as e:
        msg = sanitize_error(e)
        assert msg == "连接 LLM 服务失败，请检查网络或稍后重试"
        assert "sk-live" not in msg


def test_streaming_mirror() -> None:
    text = "hello world 流式测试"
    chunks = list(fake_stream_generate(text, chunk_size=3))
    assert len(chunks) == (len(text) + 3 - 1) // 3
    assert collect_stream(iter(chunks)) == text
    # 空文本
    assert list(fake_stream_generate("", chunk_size=5)) == []
    assert collect_stream(iter([])) == ""
    # chunk_size 大于文本
    assert list(fake_stream_generate("abc", chunk_size=10)) == ["abc"]
    # 流式中任一 chunk 抛超时，脱敏同样适用
    def gen_with_error():
        yield "part1"
        _has_req2 = "request" in APITimeoutError.__init__.__code__.co_varnames
        if _has_req2:
            raise APITimeoutError(_fake_request())
        raise APITimeoutError("timeout")

    try:
        for _ in gen_with_error():
            pass
        raise AssertionError()
    except Exception as e:
        assert sanitize_error(e) == "连接 LLM 服务失败，请检查网络或稍后重试"
