---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 日志与可观测

学完本节，你能回答：

- "能打印"和"可观测"差在哪里
- 一条日志最少要带哪些字段，级别该怎么分
- 采样必然丢信息，怎么做到丢得可控
- 日志怎么从"事后能查"走到"出事前能告警"

> 无从追溯的事，等于没有发生。

前三节都在处理故障，接住异常、判断重试、准备回退，可这些动作如果没有留下痕迹，出事之后只能靠猜。本节是横跨全章的追溯层：无论故障发生在身份、数据还是依赖上，最后都要能在日志里找到它。这也是它放在章末的原因，前几节埋下的降级与错误码，到这里才汇成一条可检索的线索。

## 从打印到结构化

用 `print` 记事的做法在开发阶段够用，到了线上会同时暴露四个问题：没有级别，分不清是日常信息还是故障；没有时间，无法算清两个事件隔了多久；没有上下文，看不出这条日志属于哪次请求；格式自由，机器没法按字段检索与聚合。可观测的第一个门槛，就是让日志从"能读"变成"能算"。

结构化的做法是让每条日志成为一个带固定字段的 JSON 对象。

| 字段 | 作用 |
| --- | --- |
| `timestamp` | 事件发生的时间，统一用 UTC |
| `level` | 级别，用于过滤与告警 |
| `logger` | 来源模块，定位代码位置 |
| `msg` | 人读的一句话 |
| `request_id` | 串起同一次请求的所有日志 |
| `doc_id` | 业务对象标识，按对象复盘 |
| `duration_ms` | 耗时，用于性能分析 |
| `error_code` | 稳定的错误标识，用于统计与告警 |

字段不必求多，够用即可；多出来的上下文用扁平键追加，避免嵌套过深导致检索语句复杂。下面这段代码实现一个 JSON 格式化器，并打印三条不同级别的日志：

```{code-cell} ipython3
import io
import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "doc_id", "duration_ms", "error_code"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


buf = io.StringIO()
handler = logging.StreamHandler(buf)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("doc_search.search")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.propagate = False

logger.info("搜索完成", extra={"request_id": "req-42", "doc_id": "d1", "duration_ms": 128})
logger.warning("搜索降级", extra={"request_id": "req-42", "error_code": "SEARCH_TIMEOUT"})
try:
    raise RuntimeError("database is locked")
except RuntimeError:
    logger.error("写入收藏失败", exc_info=True, extra={"request_id": "req-42", "error_code": "DB_LOCKED"})

lines = [json.loads(line) for line in buf.getvalue().strip().splitlines()]
for line in lines:
    print(line["level"], line["msg"], line.get("error_code", "-"))
print("首条字段齐全:", {"timestamp", "level", "logger", "msg"} <= set(lines[0]))
```

三条日志的 `request_id` 相同，一次请求的三个阶段就此串成一条链，检索时按这个字段取回全部相关记录即可。异常堆栈被塞进 `exc` 字段而不是直接拼接在消息里，既保留了排查信息，又不破坏结构。

## 分级与采样

级别的用途不只是分类，它同时是默认的过滤开关与告警的触发条件。选错级别，日志要么淹掉重要信息，要么在出事时一言不发。

| 级别 | 含义 | 是否告警 |
| --- | --- | --- |
| `DEBUG` | 开发排查用的细节，生产默认关闭 | 否 |
| `INFO` | 关键路径的里程碑，如搜索完成 | 否 |
| `WARNING` | 可恢复的异常，如降级、重试 | 否，但要看趋势 |
| `ERROR` | 需要人工介入的失败 | 是 |
| `CRITICAL` | 进程级不可用 | 是，通常还触发重启 |

`WARNING` 这一级最容易被当成"不重要"而忽略。上一节的降级事件正好属于它：单次降级不影响使用，但如果一天之内降级比例从百分之一涨到百分之三十，说明上游已经在恶化，趋势本身就是信号。

量一大就有成本问题。全量 `INFO` 在高并发下会迅速吃掉存储与费用，于是需要采样：按比例丢弃一部分低级别的日志。难处在于不能随便丢，同一次请求的日志如果只留下后半段，线索就断了。

```{code-cell} ipython3
import hashlib
import io
import logging


class SamplingFilter(logging.Filter):
    """ERROR 及以上全量保留，INFO 按 request_id 哈希采样。"""

    def __init__(self, sample_rate: float = 0.5):
        super().__init__()
        self.sample_rate = sample_rate

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        request_id = getattr(record, "request_id", "")
        bucket = int(hashlib.sha256(request_id.encode()).hexdigest(), 16) % 100
        return bucket < int(self.sample_rate * 100)


buf = io.StringIO()
handler = logging.StreamHandler(buf)
handler.setFormatter(logging.Formatter("%(levelname)s %(message)s [%(request_id)s]"))
handler.addFilter(SamplingFilter(sample_rate=0.5))
logger = logging.getLogger("doc_search.sampling")
logger.handlers.clear()
logger.addHandler(handler)
logger.propagate = False
logger.setLevel(logging.INFO)

for i in range(4):
    logger.info("搜索完成", extra={"request_id": f"req-{i}"})
    logger.error("搜索失败", extra={"request_id": f"req-{i}"})

kept = buf.getvalue().strip().splitlines()
print("INFO 保留:", sum(1 for line in kept if line.startswith("INFO")))
print("ERROR 保留:", sum(1 for line in kept if line.startswith("ERROR")))
```

采样用 `request_id` 的哈希而不是随机数，同一请求的判定结果恒定，它的日志要么整体保留、要么整体丢弃，不会只留一半。`WARNING` 与 `ERROR` 直接放行，采样只削减流水账，不削减故障证据。

## 脱敏红线

日志是排查工具，也是泄露面。密钥、令牌原文、完整 Cookie、身份证号这类内容一旦写进日志，等于把它们复制到了另一个更难管控的地方。上一章反复强调 `key` 只放服务端（[大模型调用方法](../external_integration/llm_calling.md)），这条纪律要再加一句：它也不能出现在日志里。

合理的做法是分级脱敏。密钥类字段整体替换成前缀加星号，只保留足够识别是哪一把的信息；手机号、邮箱保留必要的片段用于核对；确需原文的场景走受控访问，凭审批临时开启，而不是让所有人都能在日志里搜到。脱敏发生在写入端最省心，等到落盘后再清理，覆盖面和成本都不可控。

## 从检索到告警

单机日志用 `grep` 就能应付，多实例部署之后，日志散在各台机器上，需要集中起来。常见的方案是采集、存储与索引、呈现三步：

| 环节 | 组件 | 职责 |
| --- | --- | --- |
| 采集 | Beats 或 Logstash | 从各实例收集，解析字段，按规则脱敏 |
| 索引 | Elasticsearch | 按时间与字段建索引，支持精确检索与聚合 |
| 呈现与告警 | Kibana | 仪表盘展示，按条件触发通知 |

```bash
# 按 request_id 取回一次请求的全部日志
grep '"request_id": "req-42"' /var/log/doc-search/app.log | jq .
```

规模不大时不必上完整的一套：把结构化 JSON 写进文件，用 `grep` 或一条 SQL 就能完成检索。等实例多起来、检索变慢，再把它接入集中式方案，字段格式不用改，这正是从头就结构化的好处。

有了可检索的字段，告警条件也从"服务挂了"升级为可量化的规则：`ERROR` 速率在一分钟内超过阈值，或降级事件的比例持续攀升，都可以直接触发通知。`request_id` 把一次请求的日志串成链，`error_code` 把同类故障聚成堆，从告警跳到定位只需要两次检索。到这里，本章的四条边界形成闭环：身份、数据、依赖各自守住分内的事，日志把它们的动作记录下来，交到下一章的部署环节（[部署、容器化与持续集成](../deploy_cicd/index.md)）。

## 本节小结

- `print` 缺时间、级别、上下文与结构，可观测的第一步是让每条日志成为带固定字段的 JSON 对象。
- 级别既是过滤开关也是告警条件，`WARNING` 反映趋势，`ERROR` 与 `CRITICAL` 直接触发人工介入。
- 采样按 `request_id` 哈希决定去留，保证同一请求同进同出，`WARNING` 及以上全量保留。
- 密钥、令牌与完整 Cookie 不进日志，脱敏在写入端完成，确需原文走受控访问。
- 字段结构先立住，规模小时用 `grep` 检索，规模大了再接入采集、索引与呈现的集中式方案。