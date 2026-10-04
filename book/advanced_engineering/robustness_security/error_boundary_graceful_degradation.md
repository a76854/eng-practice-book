---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 错误边界与优雅降级

前两节守的是进来的东西：身份要认准，数据要干净。这一节守的是出去的路上会遇到的麻烦。文档查询真正自己说了不算的部分在外部：搜索靠 WebSearch 接口，摘要靠大模型，缓存靠 Redis。这些依赖随时会超时、限流或连接中断，故障消灭不掉，只能约束在某个范围内。本节按一次故障的处理顺序走：先在哪里接住它，再判断值不值得重试，然后准备一条次优的出路。

## 故障是常态

把外部依赖和它们常见的失败形态列出来，比想象"系统不会坏"要实在得多。

| 依赖 | 常见故障 | 在接口上的表现 |
| --- | --- | --- |
| WebSearch 接口 | 超时、限流 | 搜索迟迟不返回，或返回 429 |
| 大模型 | 超时、限流、输出不合格式 | 摘要失败或结果无法解析 |
| SQLite | 写锁冲突、磁盘忙 | 写入报错，读不受影响 |
| Redis | 连接中断 | 缓存不可用，回源变慢 |

追求"永不失败"既不现实也不经济。更可行的目标是三条：把故障隔离在边界之内，不让它蔓延到无关的功能；给用户一个可预期的响应，而不是一堆堆栈；给运维留下可定位的信号。错误边界负责第一条与第三条，优雅降级负责第二条。

## 错误边界

边界的含义是"在哪里接住异常"。接住的地方应该在系统与外部打交道的那一层，也就是各个仓库和客户端的内部，而不是散落在每个业务分支里写 `try`。收藏的 Service 不应该关心 WebSearch 抛的是超时还是限流，它只应该知道"这次搜索没有成功"。

接住之后要做的第一件事是分类，因为不同类的错误出路完全不同。

| 类别 | 例子 | 处理方式 |
| --- | --- | --- |
| 可重试 | 超时、限流、写锁冲突 | 有界退避后重试，失败再向上抛 |
| 不可重试 | 参数非法、格式不支持、资源不存在 | 直接失败，转成用户看得懂的文案 |
| 未预料 | 类型错误、空指针、逻辑漏洞 | 记 `ERROR` 并告警，对外只暴露通用文案 |

分类之后还有一步容易漏掉：脱敏。原始异常里可能带着连接字符串、服务器地址甚至密钥，这些信息只能进内部日志，不能出现在给用户的响应里。对外的错误体沿用前面讲统一响应时的信封（[统一响应与契约](../../backend_development/http_restful/error_and_contract.md)），`code` 用稳定的 `error_code`，`msg` 用人能读懂的话。

下面这段代码把"分类加重试加脱敏"收成一个装饰器，凡是跨出系统边界的调用都可以套上它：

```{code-cell} ipython3
import random
import time

RETRYABLE = {"TimeoutError", "RateLimitError", "DatabaseLocked"}


def is_retryable(exc: Exception) -> bool:
    return type(exc).__name__ in RETRYABLE


def with_boundary(max_retries: int = 2, base_delay: float = 0.01):
    def deco(fn):
        def wrapper(*args, **kwargs):
            last: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last = exc
                    if not is_retryable(exc):
                        raise RuntimeError("请求无法完成，请检查输入后重试") from exc
                    if attempt == max_retries:
                        break
                    time.sleep(base_delay * 2 ** attempt + random.uniform(0, 0.005))
            raise RuntimeError("依赖暂不可用，请稍后再试") from last

        return wrapper

    return deco


calls = {"n": 0}


@with_boundary(max_retries=3, base_delay=0.001)
def flaky_search(query: str) -> list[str]:
    calls["n"] += 1
    if calls["n"] < 3:
        raise TimeoutError("search timeout")
    return [f"result-for-{query}"]


print("结果:", flaky_search("pydantic"), "尝试次数:", calls["n"])


@with_boundary(max_retries=3)
def search_with_bad_sort(field: str) -> list[str]:
    raise ValueError(f"unsupported sort field: {field}")


try:
    search_with_bad_sort("drop table")
except RuntimeError as exc:
    print("不可重试:", exc)
```

超时的搜索第三次才成功，尝试次数是 3；参数错误一次就被拒绝，重试三次纯属浪费。判断可重试不能靠字符串模糊匹配，最稳的做法是让每个外部客户端把厂商的异常翻译成自己的异常类型，边界只认自己这套类型。

## 有界重试与退避

重试有两层约束，缺一不可：次数有上限，总时长也有上限。没有上限的重试等于把一个已经变慢的服务拖垮，雪崩往往就是这么来的。退避则是让每次重试之间隔得更久，第一次等十毫秒，第二次二十毫秒，成倍增长；再加上一点随机抖动，避免大量请求在同一刻齐刷刷重试。

比退避更根本的前提是幂等。重试意味着同一次操作可能执行两次，这要求操作做一次和做两次结果相同。

上一章讲消息队列时，用去重表让同一条消息重复投递也不出错（[消息队列与 Kafka](../external_integration/kafka_queue.md)），思路在这里完全一样。搜索是只读操作，重试天然安全；写操作要重试，先要保证它幂等。文档查询的收藏接口把 `doc_id` 设成主键（[综合实战](../../backend_development/backend_synthesis/index.md)），重复收藏被数据库拒绝，这才让它成为一个可以放心重试的写操作。

判断该走哪条路，可以按下面的顺序问自己：

| 策略 | 什么时候用 | 要接受的代价 |
| --- | --- | --- |
| 重试 | 瞬态故障，且操作幂等 | 响应变慢，故障期间压力更大 |
| 回退 | 主路径不可用，但有次优结果 | 结果可能过期或不完整 |
| 直接失败 | 输入或权限问题，重试无意义 | 用户被打断，但诚实且省资源 |

## 优雅降级与诚实标记

降级是在可用性与完整性之间做取舍：主路径给不出最好的结果，就先给一个能用的。

三种落法在文档查询里都能对上。缓存回退：搜索超时时，返回上一次的结果，并在响应里说明它来自缓存。功能降级：摘要服务不可用时，仍允许用户查看搜索结果与原文，只是收藏夹里的摘要暂时为空。空态与默认值：依赖彻底不可用时返回空列表加明确的错误码，前端据此显示重试按钮，而不是留一片空白。

降级必须让用户察觉得到。用旧结果冒充最新结果，比直接报错更糟，用户会基于过期的信息做判断。所以响应里要带标记，前端可以据此加一行提示。下面这段代码把一次搜索的超时处理成三种结局：

```{code-cell} ipython3
def search_documents(query: str, fetch, cache: dict[str, list[str]]) -> dict:
    try:
        results = fetch(query)
        cache[query] = results
        return {"results": results, "degraded": False}
    except TimeoutError as exc:
        if query in cache:
            return {"results": cache[query], "degraded": True, "reason": str(exc), "source": "cache"}
        return {"results": [], "degraded": True, "reason": str(exc), "source": "empty"}


def healthy_search(query: str) -> list[str]:
    return [f"fresh-{query}"]


def broken_search(query: str) -> list[str]:
    raise TimeoutError("search timeout")


cache: dict[str, list[str]] = {}
print("正常:", search_documents("pydantic", healthy_search, cache))
print("降级走缓存:", search_documents("pydantic", broken_search, cache)["source"])
print("降级走空态:", search_documents("never-seen", broken_search, cache)["source"])
```

三次调用分别是正常、回退到缓存、回退到空态，`degraded` 与 `source` 两个字段把这次响应的成色说清楚了。降级事件同时应该写一条 `WARNING` 日志，这正好接上下一节的内容：故障被接住之后，得有痕迹留下来，否则它只是被藏起来了。

```bash
curl -s "http://localhost:8000/api/search?q=pydantic" | jq .
# 正常: {"results":[...],"degraded":false}
# 降级: {"results":[...],"degraded":true,"reason":"search timeout","source":"cache"}
```

## 本节小结

- 故障是常态，目标不是永不失败，而是隔离在边界内、响应可预期、信号可定位。
- 边界的职责是捕获、分类、脱敏；可重试的上抛重试，不可重试的转成用户文案，未预料的记 ERROR 并告警。
- 重试要有界并带退避与抖动，前提是操作幂等，写操作先靠主键或去重表把重复变成无害。
- 降级是在可用性与完整性之间的取舍，缓存回退、功能降级、空态默认三种落法按场景选。
- 降级必须诚实，用 degraded 标记与来源说明当前结果的成色，并留下 WARNING 日志。
