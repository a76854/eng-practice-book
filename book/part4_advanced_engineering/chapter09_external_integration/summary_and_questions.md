---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **第三方集成的边界收敛**：SDK 与裸 HTTP 客户端无绝对优劣，选型依据是“是否需处理流式、分页、错误码映射”与“是否需统一自家观测层”；无论哪种，都应在边界模块统一超时、重试、鉴权与脱敏，`m2t.llm.LLMClient`（`timeout=60`、`max_retries=2`）即是该收敛的最小示例。
- **超时、重试与熔断是组合拳**：超时防“无限等待”，重试治“瞬态抖动”，熔断治“持续故障”；重试仅对可重试错误（网络、限流、5xx）做有界指数退避，失败时用 `map_llm_error` 脱敏，绝不把 `sk-xxx` 或堆栈透传给前端。
- **语音识别的本质是两段归一**：音频归一（`m2t.audio.load_audio` 立体声压单声道、`resample_audio` 按需重采样至 16k）与结果归一（`m2t.asr.normalize_result` 把 `sentence_info` / `raw_text+timestamp` / 空结果收敛为统一段结构）让上层 pipeline 只面对 `[{speaker, text, start, end}]`。
- **大模型接口要兼顾确定性与时延**：结构化输出用 JSON Schema 约束可编程性，收到后先 `json.loads` 再校验，失败即重试或降级；流式 SSE 用 `data: {...}` 增量拼出全量，首字即渲染以降低体感时延，截断时等待更多 delta 而非入库脏数据。
- **长时任务必须异步化**：HTTP 只做“入队 + 返回 ID”，broker / worker / result 三件套把 30 秒以上的转写与摘要隔离在后台，`m2t.store.TaskStore` 的 SQLite + WAL 是最小可用的 result backend；幂等键防重、重试有界、状态可查询，是队列可观测的三要素。
- **贯穿启示**：本章把 MeetingToText 的“上传 → 转写 → 摘要 → 导出”外部链路拆为可独立测试的边界模块——`m2t.llm` 管调用与脱敏、`m2t.asr`/`m2t.audio` 管输入归一、`m2t.export` 管输出、`m2t.store` 管状态；每一跳都有明确的失败域与观测点，符合“可重试、可降级、可审计”的工程底线。

## 思考题

1. **SDK 选型**：在什么情况下你会放弃官方 SDK、改用自家薄封装的 HTTP 客户端？若对方既提供 SDK 又提供 OpenAPI 契约，你会如何设计“可替换的调用层”以便未来切换？
2. **重试边界**：哪些错误适合重试、哪些必须快速失败？结合 `map_llm_error` 的脱敏文案，讨论“重试”与“熔断”应如何配合告警与日志，避免把瞬态故障放大为雪崩。
3. **签名与时钟**：云端 ASR 的 HMAC 签名为何要校验时间戳窗口？若客户端与服务端时钟偏差 5 分钟，除了放宽窗口，还有哪些更可靠的修复路径？
4. **音频归一的代价**：把 48k 立体声重采样至 16k 单声道会丢失信息，什么场景下这种丢失不可接受？你会如何在“模型要求”与“保真需求”之间做 trade-off？
5. **多形状结果**：`normalize_result` 的三种形状（`sentence_info` / `timestamp` / 空）在什么参数或模型下触发？若上游新增第四种形状，你会如何扩展归一函数而不让下游感知？
6. **结构化 vs 自由文本**：对会议纪要，哪些字段适合强约束（枚举、必填），哪些适合自由文本？当模型持续产出校验失败的 JSON 时，你会如何设计“结构化优先、自由文本兜底”的降级策略？
7. **流式的中断**：SSE 流在中途断连时，已收到的增量应如何处理——丢弃、续传还是入库部分结果？结合首字时延与一致性，讨论前端应何时渲染、何时等待。
8. **队列的持久化**：内存队列在进程重启后会丢任务，`m2t.store.TaskStore` 的 SQLite 如何弥补？若要支持多 worker 并发消费，你会如何用 WAL 与 `busy_timeout` 避免锁冲突？
9. **幂等与重试**：同一音频被用户重复提交时，幂等键应基于什么生成（文件哈希、业务 ID 还是随机 ID）？幂等去重表应放在 broker、worker 还是 result backend？
10. **端到端观测**：为“上传 → 转写 → 摘要 → 导出”四段链路设计最小可用的观测指标（时延、成功率、重试次数），并说明每一跳的告警阈值应如何设定才能既灵敏又不噪声。

文件 `book/part4_advanced_engineering/chapter09_external_integration/demo_summary.py`（本章贯通校验：用教学包串联“归一 → 存储 → 导出”最小闭环）：

```{code-cell} ipython3
import tempfile, pathlib, json
from m2t.store import TaskStore
from m2t.asr import normalize_result
from m2t.export import export
from m2t.llm import LLMClient, map_llm_error

with tempfile.TemporaryDirectory() as td:
    db = pathlib.Path(td) / "ch09_summary.db"
    store = TaskStore(db)

    # 1) 模拟 ASR 归一（无真实模型）
    raw = [{"sentence_info": [
        {"text": "与外部世界的集成", "start": 0, "end": 1000, "spk": 0},
        {"text": "是现代后端的必修课", "start": 1000, "end": 2200, "spk": 1},
    ]}]
    segments = normalize_result(raw)
    assert len(segments) == 2
    print("segments:", segments[0]["text"], "|", segments[1]["text"])

    # 2) 模拟 LLM 结构化生成（无网络）
    transcript = " ".join(s["text"] for s in segments)
    structured = json.dumps({
        "title": "集成纪要",
        "summary": transcript[:12] + "…",
        "action_items": [{"owner": "Alice", "task": "实现队列"}],
    }, ensure_ascii=False)
    obj = json.loads(structured)
    print("structured title:", obj["title"])

    # 3) 存储：复用 TaskStore（与真实 MeetingToText 一致的 SQLite 抽象）
    store.create("ch09", "meeting.wav", full_text=transcript)
    row = store.get("ch09")
    print("stored:", row["filename"], row["status"])

    # 4) 导出：复用 m2t.export 的纯函数能力
    fake_task = {
        "id": row["id"],
        "filename": row["filename"],
        "result": {"duration": 2, "segments": segments},
        "minutes": obj["summary"],
    }
    md = export(fake_task, "md")
    print(md.splitlines()[0])
    assert "meeting.wav" in md

    # 5) 脱敏：验证错误不泄漏
    safe = map_llm_error(RuntimeError("sk-xxx leaked"))
    assert "sk-xxx" not in safe
    print("safe:", safe)

    # 6) 客户端契约：展示 LLMClient 配置即文档
    client = LLMClient(timeout=60, max_retries=2)
    print("client:", client.timeout, client.max_retries)
    print("闭环校验通过：归一 -> 结构化 -> 存储 -> 导出 -> 脱敏")
# 预期输出:
# segments: 与外部世界的集成 | 是现代后端的必修课
# structured title: 集成纪要
# stored: meeting.wav pending
# # 会议转录 — meeting.wav
# safe: LLM 调用失败，请检查服务可用性或联系管理员
# client: 60 2
# 闭环校验通过：归一 -> 结构化 -> 存储 -> 导出 -> 脱敏
```
