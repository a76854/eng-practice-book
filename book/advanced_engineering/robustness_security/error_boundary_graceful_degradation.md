---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 错误边界与优雅降级

> 学完本节，你能回答：错误边界要“隔离什么、暴露什么”？何时重试、何时回退、何时直接失败？优雅降级的 fallback 如何保证“可用但可感知”？

## 故障是常态：从“永不失败”到“可预期地失败”

MeetingToText 调用 ASR、LLM、SQLite 时，超时、限流、磁盘忙、格式异常都会发生。追求“永不失败”既不现实也不经济；更可行的目标是**把故障隔离在边界内，给用户可预期的响应，给运维可定位的信号**。

错误边界（error boundary）与优雅降级（graceful degradation）即是这套思想的落地：前者负责“兜住”异常、记录上下文并决定是否重试；后者负责在主路径不可用时，用缓存、默认值或简化流程继续提供“可用但受限”的服务。

## 错误边界：try/except 的工程化用法

边界的核心是三件事：

1. **分层捕获**：在“外部调用边界”（如 `m2t.asr`、`m2t.llm`、`m2t.store`）统一捕获，而非在每个业务分支散落 `try`。
2. **区分可重试与不可重试**：网络超时、5xx、锁冲突可重试；参数校验失败、`FileNotFound`、签名错误应直接失败。
3. **保留上下文**：记录 `task_id` / `request_id` / `error_code`，并对原始异常做脱敏映射（见 `m2t.llm.map_llm_error`）。

重试必须有界（次数与总时长）且带退避，避免把瞬态故障放大为雪崩；同时对用户侧给出明确的错误码与可操作文案，而非堆栈。

示例：错误边界：

```{code-cell} ipython3
import time, random, logging, io, json

# 简化的可重试判断与边界装饰器
RETRYABLE = {"TimeoutError", "BusyError", "RateLimitError"}

def is_retryable(exc: Exception) -> bool:
    return exc.__class__.__name__ in RETRYABLE or "timeout" in str(exc).lower()

def with_boundary(max_retries: int = 2, base_delay: float = 0.01):
    def deco(fn):
        def wrapper(*args, **kwargs):
            last: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last = e
                    # 不可重试：直接对外抛出脱敏错误
                    if not is_retryable(e):
                        raise RuntimeError(f"操作失败（{e.__class__.__name__}），请检查输入或联系管理员") from e
                    if attempt == max_retries:
                        break
                    # 指数退避（带抖动，避免惊群）
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.005)
                    time.sleep(delay)
            raise RuntimeError(f"重试 {max_retries} 次后仍失败: {last}") from last
        return wrapper
    return deco

# 模拟：前两次超时，第三次成功
calls = {"n": 0}
@with_boundary(max_retries=3, base_delay=0.001)
def flaky_asr(task_id: str) -> str:
    calls["n"] += 1
    if calls["n"] < 3:
        raise TimeoutError("ASR timeout")
    return f"transcript:{task_id}"

# 模拟：参数错误（不可重试，应直接失败）
@with_boundary(max_retries=3)
def bad_input(path: str) -> str:
    raise ValueError("unsupported audio format")

print("flaky result:", flaky_asr("t10"))
print("attempts:", calls["n"])
try:
    bad_input("bad.xyz")
except RuntimeError as e:
    print("bad_input blocked:", e)
    assert "ValueError" in str(e) or "操作失败" in str(e)
assert flaky_asr("t10")  # 幂等：已成功后不再抛错（演示用，实际应带缓存）
# 预期输出:
# flaky result: transcript:t10
# attempts: 3
# bad_input blocked: 操作失败（ValueError），请检查输入或联系管理员
```

## 优雅降级：主路径不可用时的 Plan B

降级的本质是**在可用性与完整性之间做取舍**，常见模式：

- **缓存回退**：摘要服务超时时，返回上次成功的摘要或基于规则的摘要（标题 + 关键词），并标注“降级结果”。
- **功能降级**：转写失败时仍允许用户查看已上传的文件与基础元信息，而非整页报错。
- **默认值与空态**：任务列表查询失败时返回空列表 + 明确的 `error_code`，前端据此展示“重试”按钮而非空白。

降级必须“可感知”——在响应中带上 `degraded: true` 与原因，避免让用户误以为是完整结果；同时在日志中以 `WARNING` 记录降级事件，便于后续恢复。

示例：优雅降级：

```{code-cell} ipython3
import time, json

# 模拟外部依赖：LLM 摘要（偶发超时）
def llm_summarize(text: str) -> str:
    if "timeout" in text:
        raise TimeoutError("LLM timeout")
    return f"摘要：{text[:12]}…"

# 缓存（简化：内存 dict；生产可用 Redis 或 SQLite）
_cache: dict[str, str] = {"t10": "缓存的旧摘要（2026-08-20）"}

def summarize_with_fallback(task_id: str, transcript: str) -> dict:
    try:
        result = llm_summarize(transcript)
        _cache[task_id] = result
        return {"minutes": result, "degraded": False}
    except Exception as e:
        # 降级：优先用缓存，其次用规则摘要
        fallback = _cache.get(task_id)
        if fallback is not None:
            return {"minutes": fallback + " [降级：来自缓存]", "degraded": True, "reason": str(e)}
        rule_based = f"关键词：{transcript[:20]} [降级：规则生成]"
        return {"minutes": rule_based, "degraded": True, "reason": str(e)}

# 1) 正常路径
print(summarize_with_fallback("t11", "与外部世界的集成是现代后端的必修课"))
# 2) 触发超时，回退到缓存
print(summarize_with_fallback("t10", "timeout trigger"))
# 3) 无缓存时的规则降级
print(summarize_with_fallback("t12", "timeout 无缓存场景"))
# 断言：降级结果带 degraded 标记
r2 = summarize_with_fallback("t10", "timeout again")
assert r2["degraded"] is True and "降级" in r2["minutes"]
r3 = summarize_with_fallback("t99", "hello world")
# t99 无 timeout，不降级
assert r3["degraded"] is False
# 预期输出:
# {'minutes': '摘要：与外部世界的集成是…', 'degraded': False}
# {'minutes': '缓存的旧摘要（2026-08-20） [降级：来自缓存]', 'degraded': True, ...}
# {'minutes': '关键词：timeout 无缓存场景 [降级：规则生成]', 'degraded': True, ...}
```

```bash
# 前端感知降级的响应示意
curl http://localhost:8000/api/tasks/t10 | jq .
# 正常: {"minutes":"...","degraded":false}
# 降级: {"minutes":"... [降级：来自缓存]","degraded":true,"reason":"LLM timeout"}
```

> **环境约定**：本书面向 Linux，重试中的 `time.sleep` 在 Linux 上行为一致，单位均为秒；涉及超时配置时，建议用浮点秒（如 `0.5`、`60`）而非毫秒，避免“毫秒/秒”混淆。路径与日志见 [第10章 索引](index.md) 的环境约定。

> **工程启示**：错误边界决定“故障止于何处”，优雅降级决定“故障时用户看到什么”。二者配合，才能让 MeetingToText 在 ASR 抖动或 LLM 限流时，依然给出“可解释、可重试、可审计”的响应，而非把原始异常抛给前端。
