---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 周13 外部服务集成：ASR与LLM

> 前几章你已能在本地用 `m2t.store` 持久化任务、用 `FastAPI` 暴露接口、用 `ThreadPoolExecutor` 跑后台转写——但 MeetingToText 的“纪要生成”并不在本地算完：它把 `task.result.full_text` 与模板提示词一起发给外部 LLM（OpenAI 兼容 API，如 DeepSeek / OpenAI / Ollama），再把返回的 Markdown 存回数据库。外部服务（external service）意味着三件本地函数没有的事：密钥（Key）不能硬编码、网络会超时（timeout）与限流（rate limit）、失败信息必须脱敏（sanitize）后才展示。本章以 `m2t.llm` 的 `LLMClient(timeout=60, max_retries=2)` 与 `map_llm_error` 为锚，配合 `backend/app/templates/presets.py` 的模板选择与 `routers/generate.py` 的装配链路，用 mock（模拟）方式在教学环境中完整演示“超时→重试→脱敏中文错误”的闭环——全程不跑真 LLM。

## 学习目标

完成本章后，你将能够：

1. 能解释 LLM API Key 为何不能提交到仓库、对比“环境变量/设置页/SQLite `app_settings`”三种存放方式，并用 `LLMClient(base_url, api_key, model, timeout, max_retries)` 正确构造 OpenAI 兼容客户端。
2. 能说明 `timeout=60` 与 `max_retries=2` 的工程含义，预测超时（`APITimeoutError`）与连接失败（`APIConnectionError`）时的重试（retry）行为，并用 mock 客户端断言超时与重试参数被正确传递。
3. 能编写 `map_llm_error` 的四类脱敏映射（超时/连接失败、鉴权失败、限流、其他），并解释为何必须返回固定中文文案而非 `str(exc)`（防止 Key/URL/堆栈泄漏）。
4. 能根据 `template_id` 调用 `get_template` / `get_templates` 选择纪要模板（`meeting_minutes` / `action_items` / `quick_summary`），并用 `build_minutes_messages` 将模板 `system_prompt` + `output_format` 装配为 `messages` 列表，解释 system 与 user 的职责分离。

## 先修要求

- 完成 [周7 HTTP 与 REST API](week07_HTTP与REST_API.md)与 [周8 数据持久化与 SQL](week08_数据持久化与SQL.md)（会用 `FastAPI`、`TestClient` 与 `sqlite3`；理解 `store.save_minutes`）。
- 会 `import m2t.llm` 并阅读 `m2t/llm.py` 的 `LLMClient` 与 `map_llm_error`（只读参考，不需安装 `openai` 即可跑 mock 示例）。
- 无需真实 LLM Key；本章所有网络调用均为 mock（模拟），教学环境不跑真 LLM（真 Key 手动可选，仅在个人机器上按需开启）。

## 正文

### 13.1 Key 管理：为什么 Key 不能进仓库

LLM 的 `api_key` 是“能花钱的密码”——一旦提交到 Git，就会被爬虫扫到并盗用。MeetingToText 因此采用“代码不存 Key、运行时注入”：

| 存放方式 | 位置 | 适用场景 | 风险 |
|---|---|---|---|
| 环境变量（`OPENAI_API_KEY` / `MTT_LLM_KEY`） | 容器/CI 的 secrets | 部署期注入 | 进程环境可见，但不在仓库 |
| 设置页 → SQLite `app_settings` | `data/meetingtotext.db` 的 `app_settings(key, value)` | 用户在前端「设置」页填入，持久化后 `get_llm()` 读取 | 需保证 `data/` 在 `.gitignore` |
| 代码硬编码 | `llm.py` 源码 | 禁止 | 仓库即泄漏 |

生产 `backend/app/services/llm.py` 的 `get_llm()` 从 `settings`（即 `app_settings` 落库的内存镜像）读取 `llm_base_url / llm_api_key / llm_model`，并用 `threading.Lock` 保证单例；教学 `m2t.llm.LLMClient` 把构造参数显式化为 `LLMClient(base_url, api_key, model, timeout, max_retries)`，便于在习题中直接断言。

> 规则：仓库中只出现 `{API_KEY}` 占位符（见 `STYLE.md`），绝不出现真实 Key；`.gitignore` 必须包含 `data/` 与 `.env`。

### 13.2 超时与重试：`timeout=60` 与 `max_retries=2`

外部调用的两个不可控因素是“慢”与“偶发失败”。`OpenAI(timeout=60, max_retries=2)` 的含义：

- **`timeout=60`（超时，单位秒）**：单次 HTTP 请求最多等 60 秒，超时抛 `APITimeoutError`。MeetingToText 选 60 而非 5，是因为纪要生成常为数千 token 的长输出，短超时会把正常慢响应误判为失败。
- **`max_retries=2`（重试）**：对可重试错误（超时、连接失败、429 限流等）最多重试 2 次（即最多 3 次尝试），由 `openai` SDK 内部按指数退避执行；鉴权失败（401）不重试。

教学演示时，用 mock 不真等 60 秒——断言“构造参数被正确传给 `OpenAI`”即等价验证。

```{code-cell} ipython3
# 13.2 超时与重试参数：mock 验证 OpenAI 构造收到的 timeout / max_retries
from unittest.mock import MagicMock, patch
from m2t.llm import LLMClient

with patch("openai.OpenAI") as MockOpenAI:
    # 构造时传入自定义超时与重试
    llm = LLMClient(base_url="https://api.example.com", api_key="{API_KEY}", model="mock-model", timeout=60, max_retries=2)
    _ = llm.client  # 触发懒创建
    kwargs = MockOpenAI.call_args.kwargs
    print("timeout:", kwargs["timeout"], "max_retries:", kwargs["max_retries"])
    assert kwargs["timeout"] == 60
    assert kwargs["max_retries"] == 2
    # 改小超时：习题会断言不同取值
    llm2 = LLMClient(base_url="https://api.example.com", api_key="{API_KEY}", model="mock-model", timeout=5, max_retries=0)
    MockOpenAI.reset_mock()
    _ = llm2.client
    kwargs2 = MockOpenAI.call_args.kwargs
    print("timeout2:", kwargs2["timeout"], "max_retries2:", kwargs2["max_retries"])
    assert kwargs2["timeout"] == 5
    assert kwargs2["max_retries"] == 0
    print("—— 超时与重试参数已正确透传给 OpenAI 客户端 ——")
```

> 本节关键词：超时（timeout）与重试（retry）均为 `openai.OpenAI` 的构造期参数，非 `generate` 期参数；`m2t.llm.LLMClient` 将其收敛在 `__init__` 以便与生产对齐。

### 13.3 错误脱敏：`map_llm_error` 的四类中文文案

原始异常常含 `api_key`、`base_url`、堆栈；若直接 `raise HTTPException(detail=str(e))`，前端即可看到 Key。`map_llm_error` 的契约是“绝不拼接 `str(exc)`，只返回固定中文文案”：

| 异常类型 | 映射文案 | 触发场景 |
|---|---|---|
| `APITimeoutError` / `APIConnectionError` | `连接 LLM 服务失败，请检查网络或稍后重试` | 超时（timeout）/ 断网 |
| `AuthenticationError` | `LLM API Key 无效或未授权，请在设置中检查` | Key 错/过期 |
| `RateLimitError` | `LLM 服务请求过于频繁，请稍后重试` | 429 限流 |
| 其他 `Exception` | `LLM 调用失败，请检查服务可用性或联系管理员` | 兜底 |

生产 `routers/generate.py` 的 `except Exception as e: logger.exception(...); raise HTTPException(status_code=500, detail=map_llm_error(e))` 即此模式——日志用 `logger.exception` 保留完整堆栈（服务端可见），客户端只见脱敏文案。

```{code-cell} ipython3
# 13.3 脱敏映射：mock 演示超时→脱敏中文错误（全程不跑真 LLM）
from unittest.mock import MagicMock
from m2t.llm import LLMClient, map_llm_error

# 构造一个携带假 Key 的“危险”异常文本，验证映射后不泄漏
dangerous_text = "sk-live-{API_KEY} https://api.example.com/v1/chat/completions"

# 用 openai 的真实异常类构造（若未装 openai，map_llm_error 会走兜底分支，仍不泄漏）
try:
    from openai import APITimeoutError, APIConnectionError, AuthenticationError, RateLimitError
    # APITimeoutError 需要 request 参数
    import httpx
    fake_request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")

    cases = [
        (APITimeoutError(fake_request), "连接 LLM 服务失败，请检查网络或稍后重试"),
        (APIConnectionError(request=fake_request), "连接 LLM 服务失败，请检查网络或稍后重试"),
        (AuthenticationError("auth failed", response=httpx.Response(401, request=fake_request), body=None), "LLM API Key 无效或未授权，请在设置中检查"),
        (RateLimitError("rate limited", response=httpx.Response(429, request=fake_request), body=None), "LLM 服务请求过于频繁，请稍后重试"),
        (ValueError(dangerous_text), "LLM 调用失败，请检查服务可用性或联系管理员"),
    ]
    for exc, expected in cases:
        msg = map_llm_error(exc)
        print(f"{exc.__class__.__name__} -> {msg}")
        assert msg == expected, f"期望 {expected}, 实际 {msg}"
        assert "{API_KEY}" not in msg and "sk-live" not in msg, "脱敏失败：泄漏了原始异常文本"
    print("—— 四类脱敏映射均通过，且无 Key/URL 泄漏 ——")
except ImportError:
    # 未装 openai 时走兜底：任意异常均映射为通用文案
    msg = map_llm_error(ValueError(dangerous_text))
    print("openai 未安装，兜底文案:", msg)
    assert "{API_KEY}" not in msg

# 进阶：mock LLM 客户端让 generate 抛超时，验证路由层的 try/except + 映射链路
def demo_generate_timeout_to_sanitized():
    llm = LLMClient(base_url="https://api.example.com", api_key="{API_KEY}", model="mock-model", timeout=1, max_retries=0)
    # 注入 fake client：chat.completions.create 直接抛超时
    fake_create = MagicMock(side_effect=APITimeoutError(fake_request) if 'APITimeoutError' in dir() else ValueError("timeout"))
    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create
    llm._client = fake_client
    try:
        llm.generate(system_prompt="你是会议秘书", user_message="转录：大家好", temperature=0.3, max_tokens=100)
    except Exception as e:
        sanitized = map_llm_error(e)
        print("generate 超时后脱敏文案:", sanitized)
        assert sanitized == "连接 LLM 服务失败，请检查网络或稍后重试"
        assert "{API_KEY}" not in sanitized
        return sanitized
    raise AssertionError("应抛超时异常")

try:
    demo_generate_timeout_to_sanitized()
    print("—— mock 超时→脱敏链路验证通过 ——")
except NameError:
    print("跳过 generate mock（openai 未安装时 APITimeoutError 不可用），但脱敏契约已验证")
```

要点：`map_llm_error` 不做 `return f"失败: {exc}"`，只做 `isinstance` 分支返回固定串；测试必须断言“返回值不含 `str(exc)` 的子串”以证明脱敏。

### 13.4 模板选择与提示词装配

MeetingToText 的纪要不是“一句话 prompt”，而是“模板库 + 装配器”：

- **模板库** `backend/app/templates/presets.py`：`TEMPLATES = {"meeting_minutes": {...}, "action_items": {...}, "quick_summary": {...}}`，每模板含 `id / name / description / system_prompt / output_format`；`get_templates()` 列全部，`get_template(id)` 按 id 取单条，`None` 表示未知模板。
- **装配器** `backend/app/templates/prompts.py` 的 `build_minutes_messages(template_prompt, transcript_text, custom_instructions, output_format_hint)`：返回 `[{"role": "system", ...}, {"role": "user", ...}]`，`system` 承载 persona + 格式约束，`user` 承载转录文本 + 额外要求。

`routers/generate.py` 的链路（只读对照）：

```python
template = get_template(req.template_id)
if template is None:
    raise HTTPException(status_code=400, detail=f"Unknown template: {req.template_id}")
messages = build_minutes_messages(template["system_prompt"], task.result.full_text, req.custom_instructions, template.get("output_format",""))
minutes = await asyncio.to_thread(llm.generate, system_prompt=messages[0]["content"], user_message=messages[1]["content"], ...)
```

```{code-cell} ipython3
# 13.4 模板选择与装配：mock 演示 get_template + build_minutes_messages + LLMClient.generate
from unittest.mock import MagicMock
from m2t.llm import LLMClient

# ---- 最小模板库（与 presets.py 同形，教学精简）----
TEMPLATES = {
    "meeting_minutes": {
        "id": "meeting_minutes",
        "name": "标准会议纪要",
        "description": "含主题/参会/讨论/决定/行动项",
        "system_prompt": "你是专业的会议记录秘书，客观提取信息，不要编造。",
        "output_format": "# 会议纪要\n## 一、主题\n{摘要}\n## 二、讨论\n{讨论}\n",
    },
    "action_items": {
        "id": "action_items",
        "name": "行动计划",
        "description": "提取待办与负责人",
        "system_prompt": "你是高效的项目管理员，提取所有 Action Items。",
        "output_format": "| 优先级 | 行动项 | 负责人 | 截止日期 |\n",
    },
    "quick_summary": {
        "id": "quick_summary",
        "name": "简要纪要",
        "description": "200字内摘要",
        "system_prompt": "请将转录精炼为200字内中文摘要。",
        "output_format": "{一行摘要}",
    },
}

def get_template(tid: str):
    return TEMPLATES.get(tid)

def get_templates():
    return list(TEMPLATES.values())

def build_minutes_messages(template_prompt: str, transcript_text: str, custom_instructions: str | None, output_format_hint: str = "") -> list[dict]:
    _OUTPUT_SUFFIX = "\n\n请按照以下格式输出：\n{output_format}"
    _SCAFFOLD = "请根据以下会议转录内容生成会议纪要：\n\n=== 会议转录开始 ===\n{transcript}\n=== 会议转录结束 ==="
    _CUSTOM_SUFFIX = "\n\n额外要求：{custom_instructions}"
    system_prompt = template_prompt
    if output_format_hint:
        system_prompt += _OUTPUT_SUFFIX.format(output_format=output_format_hint)
    user_message = _SCAFFOLD.format(transcript=transcript_text)
    if custom_instructions:
        user_message += _CUSTOM_SUFFIX.format(custom_instructions=custom_instructions)
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]

# ---- 演示：选择模板并 mock 调用 LLM ----
transcript = "说话人1：我们周三上线。\n说话人2：我负责前端联调。"
template = get_template("meeting_minutes")
assert template is not None
messages = build_minutes_messages(template["system_prompt"], transcript, custom_instructions="请用中文", output_format_hint=template["output_format"])
print("system 含格式约束:", "请按照以下格式输出" in messages[0]["content"])
print("user 含转录:", "=== 会议转录开始 ===" in messages[1]["content"])
print("user 含额外要求:", "额外要求" in messages[1]["content"])

# mock LLM：不跑网络，直接返回固定纪要
llm = LLMClient(base_url="https://api.example.com", api_key="{API_KEY}", model="mock-model")
fake_resp = MagicMock()
fake_resp.choices = [MagicMock(message=MagicMock(content="# 会议纪要\n## 一、主题\n周三上线\n"))]
fake_client = MagicMock()
fake_client.chat.completions.create.return_value = fake_resp
llm._client = fake_client

result = llm.generate(system_prompt=messages[0]["content"], user_message=messages[1]["content"], temperature=0.3, max_tokens=4096)
print("mock 纪要首行:", result.splitlines()[0])
# 断言 mock 收到正确的 model 与 messages
call_kwargs = fake_client.chat.completions.create.call_args.kwargs
assert call_kwargs["model"] == "mock-model"
assert call_kwargs["messages"][0]["role"] == "system"
assert call_kwargs["messages"][1]["role"] == "user"
assert "周三上线" in call_kwargs["messages"][1]["content"]
print("—— 模板选择与装配+mock 调用均通过 ——")

# 未知模板分支
assert get_template("unknown") is None
print("未知模板返回 None（路由层应转 400）")
```

> 以上 `get_template` / `build_minutes_messages` 的 shape 与生产 `presets.py` / `prompts.py` 一致，可直接对照 `backend/app/templates/presets.py:76` 的 `return TEMPLATES.get(template_id)` 与 `prompts.py:73-87` 的 `system_prompt += _OUTPUT_FORMAT_SUFFIX`。

### 13.5 Mock 测试：教学环境不跑真 LLM

教学环境不跑真 LLM（真 Key 手动可选）——所有单测均为 hermetic（不依赖网络/真实 Key），通过“注入 fake client”实现：

```python
# 模式：给 LLMClient 注入 _client，再让 chat.completions.create 按需返回或抛异常
llm = LLMClient(base_url="https://...", api_key="{API_KEY}", model="mock-model", timeout=60, max_retries=2)
fake_client = MagicMock()
fake_client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content="..."))])
# 或 fake_client.chat.completions.create.side_effect = APITimeoutError(...)
llm._client = fake_client
assert llm.generate(...) == "..."
```

这样测到的正是“参数是否正确传递、提示词是否正确装配、脱敏是否不泄漏”，而非“LLM 智力”。

### 13.6 流式（streaming）的概念镜像

真实纪要生成常为“流式（streaming）”：`stream=True` 时服务端以 SSE/ chunk 增量推送，前端逐字渲染；但本章教学环境不引入 SSE/WS 真链路。为验证“流式概念”而不跑网络，习题采用“概念镜像（conceptual mirror）”：

- `fake_stream_generate(full_text, chunk_size=5) -> Iterator[str]`：把完整文本按 `chunk_size` 切块 `yield`，模拟流式分片。
- `collect_stream(chunks) -> str`：`"".join(chunks)` 聚合，断言 `collect_stream(fake_stream_generate(text)) == text`。

镜像的意义：分片→聚合恒等，验证“流式只是传输形态，不改变内容契约”；超时/脱敏对流式同样适用（任一 chunk 抛 `APITimeoutError` 即映射为同一中文文案）。

### 改动并预测

以下实验均可在本章 `{code-cell}` 或本地 `.venv` 中复现，按“改什么 → 预测 → 解释”三段式。

#### 改动并预测 实验 1：把 `timeout=60` 改为 `0.001` → 预测 mock 超时映射

- **改什么**：把 `LLMClient(..., timeout=60, max_retries=2)` 改为 `LLMClient(..., timeout=0.001, max_retries=0)`，并让 `fake_client.chat.completions.create.side_effect = APITimeoutError(fake_request)`。
- **预测**：`llm.generate(...)` 抛 `APITimeoutError`，`map_llm_error(e)` 返回 `连接 LLM 服务失败，请检查网络或稍后重试`，且文案中不含 `{API_KEY}` 或 `sk-`；`MockOpenAI` 的 `timeout` 入参变为 `0.001`。
- **解释**：`timeout` 是 `OpenAI` 构造期参数，极小值模拟“网络慢于阈值”；`max_retries=0` 时不重试，超时直接暴露给 `map_llm_error` 做脱敏。验证了“超时阈值→触发→脱敏”的链路。

#### 改动并预测 实验 2：把 `max_retries=2` 改为 `0` → 预测重试消失

- **改什么**：保持 `timeout=60`，把 `max_retries=2` 改为 `0`，用 `patch("openai.OpenAI")` 观察 `OpenAI(..., max_retries=?)` 的入参；同时用计数型 `fake_create` 记录被调次数。
- **预测**：`MockOpenAI.call_args.kwargs["max_retries"] == 0`；若 `fake_create` 首调抛 `APIConnectionError`，`max_retries=0` 时只调 1 次即抛，`max_retries=2` 时（真实 SDK）会重试至多 3 次——mock 中通过 `side_effect=[APIConnectionError, success]` 可观测到 `max_retries=0` 时直接失败、`max_retries=2` 时第二次成功。
- **解释**：`max_retries` 由 SDK 在底层重试，对调用方透明；教学中通过 mock 构造参数断言其值，而非真等重试退避。`generate` 的幂等性（同一 `system_prompt/user_message` 重试结果一致）是重试安全的前提。

#### 改动并预测 实验 3：把 `map_llm_error` 改成 `return str(exc)` → 预测 Key 泄漏

- **改什么**：把 `map_llm_error` 的 `return "连接 LLM 服务失败..."` 改为 `return str(exc)`（或 `return f"LLM 失败: {exc}"`），传入 `ValueError("sk-live-abc https://api.example.com")`。
- **预测**：返回值含 `sk-live-abc` 与 URL，明文泄漏；`pytest` 中 `assert "sk-live" not in msg` 失败；若该文案经 `HTTPException(detail=msg)` 返回前端，浏览器即可看到 Key。
- **解释**：`map_llm_error` 的核心契约是“绝不拼接原始异常”；固定文案 + `logger.exception` 分流（日志存原文、前端只见脱敏）是生产 `routers/generate.py:59` 的模式。改回固定文案后，`assert` 重新通过。

#### 改动并预测 实验 4：把 `get_template("meeting_minutes")` 改为 `get_template("unknown")` → 预测 400 分支

- **改什么**：把 `get_template("meeting_minutes")` 的实参改为 `"unknown"` 或 `""`，保持后续 `if template is None: raise HTTPException(400, detail="Unknown template: ...")` 不变。
- **预测**：`get_template` 返回 `None`，路由层抛 `400` 且 `detail` 含 `Unknown template: unknown`；若删掉该 `if` 检查而直接 `template["system_prompt"]`，则抛 `TypeError: 'NoneType' object is not subscriptable` 导致 500，掩盖了“模板不存在”的业务语义。
- **解释**：`presets.py` 的 `TEMPLATES.get` 对未知 id 返回 `None` 是刻意设计，路由层必须显式处理并映射为 400，让客户端知道“换个模板 id 重试”而非“服务端崩溃”。习题 `test_template_selection` 即断言此分支。

#### 改动并预测 实验 5：去掉 `build_minutes_messages` 的 `output_format` 追加 → 预测 system 长度变化

- **改什么**：把 `if output_format_hint: system_prompt += _OUTPUT_FORMAT_SUFFIX.format(...)` 删掉，始终 `system_prompt = template_prompt`。
- **预测**：`messages[0]["content"]` 长度变短，不再含 `请按照以下格式输出` 与 Markdown 骨架；`quick_summary` 等依赖格式约束的模板，mock 生成的“格式”将不再可断言（如 `assert "# "` 不再稳定）。
- **解释**：`output_format` 追加到 `system` 是“输出形状约束”，追加到 `user` 则会被转录文本稀释；`prompts.py:74-75` 仅在 `output_format_hint` 非空时追加，避免无格式模板产生空 `请按照以下格式输出：` 段。`custom_instructions` 追加到 `user` 且在 `None/""` 时不追加空段，同理。

## 习题

> 参考答案与测试在 `answers/week13/`，运行 `.venv/bin/pytest answers/week13/ -q` 验证。题目均为 hermetic（不依赖网络/真实 Key/文件系统），通过 mock LLM 客户端与内存模板库完成。

1. **构造参数透传**：实现 `make_client(timeout, max_retries) -> LLMClient`，并用 `patch("openai.OpenAI")` 断言 `OpenAI(..., timeout=..., max_retries=...)` 收到相同值（覆盖 `60/2` 与自定义 `5/0` 两组）。
2. **脱敏四类映射**：实现 `sanitize_error(exc) -> str`（封装 `map_llm_error`），对 `APITimeoutError / APIConnectionError / AuthenticationError / RateLimitError / ValueError("sk-...")` 五类输入，断言返回四类固定中文文案，且均不含 `sk-` 或 URL。
3. **模板选择**：实现 `get_template(tid) / get_templates()`（或复用 `presets.py` shape），断言 `get_template("meeting_minutes")` 非空且含 `system_prompt`，`get_template("unknown") is None`，`len(get_templates()) == 3`。
4. **提示词装配**：实现 `build_minutes_messages(template_prompt, transcript, custom_instructions, output_format_hint)`，断言 `system` 仅在 `output_format_hint` 非空时追加 `请按照以下格式输出`，`user` 含 `=== 会议转录开始 ===` 且仅在 `custom_instructions` 非空时追加 `额外要求`。
5. **mock 生成成功**：给 `LLMClient` 注入 `fake_client`（`chat.completions.create.return_value = ...`），断言 `generate(system_prompt, user_message)` 返回 `content`，且 `create` 收到的 `model / messages / temperature / max_tokens` 与传入一致。
6. **mock 超时→脱敏链路**：给 `LLMClient` 注入抛 `APITimeoutError` 的 `fake_client`，断言 `generate` 抛异常且 `map_llm_error(e)` 为超时文案，且脱敏不含原始文本。
7. *（附加）* **流式概念镜像**：实现 `fake_stream_generate(text, chunk_size) -> Iterator[str]` 与 `collect_stream(chunks) -> str`，断言 `collect_stream(fake_stream_generate("hello world", 3)) == "hello world"`，且 chunk 数 `== ceil(len(text)/chunk_size)`；并演示任一 chunk 抛 `APITimeoutError` 时同样映射为超时文案。

## 延伸挑战

1. **重试的指数退避**：用计数型 `side_effect = [APIConnectionError, APIConnectionError, success]` 模拟 SDK 重试，记录 `max_retries=2` 时第几次成功、`max_retries=0` 时是否直接失败，思考幂等性对重试的必要性。
2. **Key 的多源注入**：分别从环境变量、SQLite `app_settings`、函数参数三处构造 `LLMClient`，对比“谁覆盖谁”的优先级，并用 `tmp_path` 的临时库验证 `set_setting("llm_api_key", "{API_KEY}")` 后 `get_llm()` 能读到。
3. **流式真链路**：在本地用 `httpx` MockTransport 模拟 `stream=True` 的 chunked 响应，将 `fake_stream_generate` 换成对 `client.chat.completions.create(stream=True)` 的迭代，验证聚合结果一致且首 chunk 超时即全链脱敏。

> 本章内容原创，客户端构造与错误脱敏对应 MeetingToText 的 `backend/app/services/llm.py`（`timeout=60` / `max_retries=2` / `map_llm_error` 四类中文映射），模板与装配对应 `backend/app/templates/presets.py` 与 `backend/app/templates/prompts.py` 的 `get_template / get_templates / build_minutes_messages`，路由链路对应 `backend/app/routers/generate.py` 的 `get_template → build_minutes_messages → llm.generate → map_llm_error`；示例代码、mock 演示与表述均为原创。
