---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第9章 与外部世界的集成

> **本章学习目标**
> - 能够区分 SDK 与裸 HTTP 客户端的适用边界，并用超时、重试与熔断解释第三方服务的容错策略
> - 能够说清语音识别（ASR）接入中的签名鉴权、音频格式归一与结果多形状问题，并用教学包完成一次无真实模型的转写闭环
> - 能够设计大模型（LLM）的结构化输出与流式响应（SSE）接口，并用本地仿真生成器演示首字时延与增量解析
> - 能够用任务队列的 broker / worker / result 三件套解释长时任务的异步化，并在不依赖 Celery 的前提下实现最小可运行的队列抽象
> - 能够把上述能力串联为 MeetingToText 的“上传 → 转写 → 摘要 → 导出”外部集成链路，并说清每一跳的失败域与观测点

> **为什么需要掌握本章**
> 现代后端极少“闭门造车”——转写要调 FunASR 或云端 ASR、摘要要调 OpenAI 兼容的 LLM、长耗时要丢进队列、文件要落盘或上云。外部服务带来能力的“杠杆”，也带来网络抖动、鉴权过期、限流、格式不一致与长时阻塞等真实风险。本章以 MeetingToText 为贯穿案例，把“如何安全地与外部世界对话”收敛为可复用的集成模式，让系统既能借力外部能力，也能在外部不可用时可观测、可重试、可降级。

> **预计理论学时**：3学时

本章是第四篇的起点，也是全书从“单体内的正确性”走向“分布式协作的健壮性”的转折。我们延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清工程痛点，再给出最小可用抽象，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 1 至 8 章相同，所有示例均在书仓根目录的 `.venv` 环境中用 `m2t` 教学包本地验证，无需真实的网络、云端密钥或外部服务。

章内结构如下：

- [9.1 第三方服务集成模式](9.1_third_party_service_integration.md) —— SDK vs HTTP 客户端：何时包一层、何时直接调；超时、重试、熔断与错误脱敏
- [9.2 语音识别接入](9.2_asr_integration.md) —— 云端签名的本质、音频格式归一（声道/采样率/编码）与多形状结果归一
- [9.3 大模型接口设计](9.3_llm_api_design.md) —— 结构化输出（JSON 模式）、流式 SSE 的增量解析与首字时延
- [9.4 异步任务队列 Celery](9.4_async_task_queue_celery.md) —— 为何长时任务要异步化；broker / worker / result 的最小队列抽象（不依赖 Celery）

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t` 教学包（见 [m2t 源码](../../../m2t/llm.py) 与 [m2t ASR 源码](../../../m2t/asr.py) 的精简实现），无需启动真实的 ASR 模型或 LLM 服务。

> **跨平台约定**：本章所有涉及路径与环境激活的命令均标注 Windows / macOS / Linux 差异，详见各小节对照表；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第6章 并发模型与性能工程](../../part2_backend_development/chapter06_concurrency_perf/index.md)。

文件 `book/part4_advanced_engineering/chapter09_external_integration/demo_index.py`（验证本章环境与 m2t 教学包可用）：

```{code-cell} ipython3
# 文件 book/part4_advanced_engineering/chapter09_external_integration/demo_index.py
import sys, pathlib

import m2t
from m2t.llm import LLMClient, map_llm_error
from m2t.asr import normalize_result
from m2t.audio import load_audio, resample_audio

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("LLMClient:", LLMClient.__name__, "| timeout default:", LLMClient().timeout)
print("normalize_result:", normalize_result.__name__)
print("load_audio:", load_audio.__name__, "resample_audio:", resample_audio.__name__)
# 脱敏演示：原始异常含 key 也不应透传
try:
    raise RuntimeError("sk-abc123 connection timeout https://api.example.com")
except Exception as e:
    safe = map_llm_error(e)
    print("safe message:", safe)
    assert "sk-abc123" not in safe
print("prefix:", pathlib.Path(sys.prefix).name)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# LLMClient: LLMClient | timeout default: 60
# normalize_result: normalize_result
# load_audio: load_audio resample_audio: resample_audio
# safe message: LLM 调用失败，请检查服务可用性或联系管理员
# prefix: .venv 或系统前缀
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行（macOS / Linux）
.venv/bin/python -c "import m2t; print(m2t.__version__)"
# Windows 需用
.venv\Scripts\python.exe -c "import m2t; print(m2t.__version__)"
```
