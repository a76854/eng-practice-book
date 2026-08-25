"""OpenAI 兼容客户端与脱敏错误映射。

为什么：MeetingToText 的纪要生成依赖外部 LLM，网络/鉴权/限流等失败必
须以固定中文文案呈现给用户，且绝不能把原始异常（含 key、URL、堆栈）
透传到前端。本模块把「客户端构造」与「错误映射」收敛在一处，并在
导入期对 openai 做懒加载，保证 ``import m2t.llm`` 不强依赖 openai。
"""

from __future__ import annotations

from typing import Any


class LLMClient:
    """OpenAI 兼容客户端。

    为什么参数固定为 base_url/key/model/timeout/max_retries：与
    MeetingToText 的真实配置对齐，教学中可直接对照 ``settings`` 的
    取值；timeout=60 与 max_retries=2 是生产默认值，避免每章重复
    解释。
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "",
        timeout: float = 60,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        """懒创建 ``OpenAI`` 客户端。

        为什么懒创建：避免在模块导入期就要求 openai 已安装；同时让
        测试可通过传入 fake client 完全绕过网络。
        """
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai 未安装，请先安装 openai 依赖"
                ) from exc
            self._client = OpenAI(
                base_url=self.base_url or None,
                api_key=self.api_key or "sk-fake",
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        model: str = "",
    ) -> str:
        """调用 chat.completions 生成文本。"""
        chosen = model or self.model
        resp = self.client.chat.completions.create(
            model=chosen,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        return content or ""


def map_llm_error(exc: Exception) -> str:
    """将异常映射为脱敏中文文案（绝不含原始异常文本）。

    为什么脱敏：原始异常常含 API key、URL、堆栈；前端展示必须用固定
    文案，原始信息仅由服务端日志记录。本函数不拼接任何异常原文。

    映射：

    - 超时/连接失败 → 连接失败文案
    - 鉴权失败 → Key 无效文案
    - 限流 → 稍后重试文案
    - 其他 → 通用失败文案
    """
    try:
        from openai import (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            RateLimitError,
        )
    except ImportError:
        return "LLM 调用失败，请检查服务可用性或联系管理员"

    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return "连接 LLM 服务失败，请检查网络或稍后重试"
    if isinstance(exc, AuthenticationError):
        return "LLM API Key 无效或未授权，请在设置中检查"
    if isinstance(exc, RateLimitError):
        return "LLM 服务请求过于频繁，请稍后重试"
    return "LLM 调用失败，请检查服务可用性或联系管理员"
