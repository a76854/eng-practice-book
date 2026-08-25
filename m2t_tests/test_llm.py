"""llm 模块 hermetic 测试（fake SDK，无网络，无 str(e) 泄漏）。"""

from __future__ import annotations

import sys
import types


def _make_fake_openai_module():  # type: ignore[no-untyped-def]
    mod = types.ModuleType("openai")

    class APIConnectionError(Exception):
        pass

    class APITimeoutError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class FakeMessage:
        def __init__(self, content):  # type: ignore[no-untyped-def]
            self.content = content

    class FakeChoice:
        def __init__(self, content):  # type: ignore[no-untyped-def]
            self.message = FakeMessage(content)

    class FakeResponse:
        def __init__(self, content):  # type: ignore[no-untyped-def]
            self.choices = [FakeChoice(content)]

    class FakeCompletions:
        def __init__(self, content="ok"):  # type: ignore[no-untyped-def]
            self._content = content
            self.last_kwargs = None

        def create(self, **kwargs):  # type: ignore[no-untyped-def]
            self.last_kwargs = kwargs
            return FakeResponse(self._content)

    class FakeChat:
        def __init__(self, content="ok"):  # type: ignore[no-untyped-def]
            self.completions = FakeCompletions(content)

    class FakeClient:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.chat = FakeChat("fake-reply")
            self.args = args
            self.kwargs = kwargs

    mod.APIConnectionError = APIConnectionError  # type: ignore[attr-defined]
    mod.APITimeoutError = APITimeoutError  # type: ignore[attr-defined]
    mod.AuthenticationError = AuthenticationError  # type: ignore[attr-defined]
    mod.RateLimitError = RateLimitError  # type: ignore[attr-defined]
    mod.OpenAI = FakeClient  # type: ignore[attr-defined]
    return mod


def test_llm_generate_with_fake_client():  # type: ignore[no-untyped-def]
    from m2t.llm import LLMClient

    client = LLMClient(base_url="http://fake", api_key="sk-test", model="fake-model")

    # 注入 fake SDK 客户端，避免 import openai
    class FakeCompletions:
        def create(self, **kwargs):  # type: ignore[no-untyped-def]
            assert kwargs["model"] == "fake-model"
            assert kwargs["temperature"] == 0.3

            class Msg:
                content = "hello-llm"

            class Choice:
                message = Msg()

            class Resp:
                choices = [Choice()]

            return Resp()

    class FakeChat:
        completions = FakeCompletions()

    class FakeSDK:
        chat = FakeChat()

    client._client = FakeSDK()  # type: ignore[attr-defined]
    out = client.generate("sys", "user")
    assert out == "hello-llm"


def test_llm_timeout_param_defaults():  # type: ignore[no-untyped-def]
    from m2t.llm import LLMClient

    c = LLMClient()
    assert c.timeout == 60
    assert c.max_retries == 2


def test_map_llm_error_sanitized_no_leak():  # type: ignore[no-untyped-def]
    fake_mod = _make_fake_openai_module()
    sys.modules["openai"] = fake_mod
    try:
        from m2t.llm import map_llm_error

        # 每种异常都应映射到固定中文，且不包含原始文本 "SECRET_KEY_123"
        cases = [
            (fake_mod.APITimeoutError("SECRET_KEY_123 timeout"), "连接 LLM 服务失败"),
            (fake_mod.APIConnectionError("SECRET_KEY_123 conn"), "连接 LLM 服务失败"),
            (fake_mod.AuthenticationError("SECRET_KEY_123 auth"), "LLM API Key 无效"),
            (fake_mod.RateLimitError("SECRET_KEY_123 rate"), "请求过于频繁"),
            (ValueError("SECRET_KEY_123 other"), "LLM 调用失败"),
        ]
        for exc, expect_sub in cases:
            msg = map_llm_error(exc)
            assert expect_sub in msg
            assert "SECRET_KEY_123" not in msg
    finally:
        # 清理，避免影响其他测试对 openai 的懒导入
        sys.modules.pop("openai", None)
        # 重新确保下一次 import 能被捕获（若需要）
        import importlib

        import m2t.llm

        importlib.reload(m2t.llm)


def test_llm_module_import_does_not_require_openai():  # type: ignore[no-untyped-def]
    # 确保在没有 openai 的环境下 import m2t.llm 仍成功
    sys.modules.pop("openai", None)
    import importlib

    import m2t.llm

    importlib.reload(m2t.llm)
    assert hasattr(m2t.llm, "LLMClient")
    assert hasattr(m2t.llm, "map_llm_error")
