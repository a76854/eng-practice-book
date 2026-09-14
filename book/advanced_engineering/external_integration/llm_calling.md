---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 大模型调用方法

学完本节，你能回答：

- 一次大模型调用要经过哪几步，key 为什么只能放服务端
- 流式响应解决什么问题，增量解析要注意什么
- 结构化输出与函数调用分别解决什么问题
- 调得起和丢不起，分别指哪两笔账

> 答案越易得，问题越珍贵。

前面三节的对象存储、缓存、队列，都是后端自己的手艺，可以先把基础设施搭好、跑通，再上生产。本节的新同事不一样：大模型的能力不在自家服务器上，只能通过网络，一次次地向服务方借；一次调用可能花上十几秒，按字数计费，答案还要经过处理才能被程序使用。

本节从最小的一次调用讲起，把大模型的四种用法依次铺开：怎么把问题送出去、怎么让答案边生成边回来、怎么让结果能被程序校验、怎么让它查到它不知道的东西；最后收在两笔账上，成本与安全。

## 普通调用

从最小的一次调用开始。

调用大模型就是往它的接口发一条 HTTP 请求，把问题装进去，把回答取出来。本节用 DeepSeek 的接口做示例（模型 `deepseek-flash`，即 DeepSeek-V4.1-Flash）：它兼容 OpenAI 协议，同类厂商与本地部署方案大多遵循同一协议，换一家只改地址与模型名。第一个要定的是钥匙放哪：API key 只放服务端。前端直接带 key 的后果是爬虫抄走随便刷，账单全算你头上；正确结构是前端调自家后端，自家后端带 key 出网。

```{code-cell} ipython3
# 普通调用：有 key 实跑 DeepSeek，无 key 降级跳过
import os
import httpx

api_key = os.environ.get("LLM_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
model = os.environ.get("LLM_MODEL", "deepseek-flash")

if not api_key:
    print("未配置 LLM_API_KEY，跳过真实调用")
else:
    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": [
            {"role": "user", "content": "用一句话介绍 pydantic"},
        ]},
        timeout=30.0,
    )
    resp.raise_for_status()
    print(resp.json()["choices"][0]["message"]["content"])
```

观测小结：有 key 时真正调用 DeepSeek 并打印回答，无 key 时只打印跳过信息，两种路径都不报错。`LLM_BASE_URL` 与 `LLM_MODEL` 可配，换厂商、切本地部署都只改环境变量，不改代码。

## 流式响应

调用能通了，体感问题随之而来：一次生成短则几秒，长则几十秒，等全量返回再渲染，用户对着空白页面干等。

流式的思路是边算边回：模型每生成一小段就把这一小段推给客户端，界面渐渐长出来，首字时延从秒级降到百毫秒级。协议上通常用 SSE（Server-Sent Events）：服务器持续输出若干行文本，每行以 `data:` 开头携带一段增量，最后用 `[DONE]` 收尾。

```{code-cell} ipython3
# 流式调用：逐段接收增量，拼出完整回答
import json
import os
import httpx

api_key = os.environ.get("LLM_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
model = os.environ.get("LLM_MODEL", "deepseek-flash")

if not api_key:
    print("未配置 LLM_API_KEY，跳过真实调用")
else:
    parts = []
    with httpx.stream(
        "POST",
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "stream": True, "messages": [
            {"role": "user", "content": "用三句话介绍 pydantic"},
        ]},
        timeout=60.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            chunk = json.loads(payload)
            if not chunk["choices"]:
                continue
            delta = chunk["choices"][0]["delta"] or {}
            parts.append(delta.get("content") or "")
    print(f"收到 {len(parts)} 个增量，拼出 {sum(len(p) for p in parts)} 字")
```

观测小结：增量逐段到来，不能等 `[DONE]` 才动手，拼完再整体处理。前端用 `fetch` 读流逐块渲染的姿势，与前后端联调一章的[异步状态](../communication_debugging/async_state.md)一节是同一套；后端负责吐流，前端负责接流，两头在这里接上。

## 结构化输出

响应快慢解决了，下一个问题：结果能不能被程序用。

自由文本适合人读，不适合机器读。文档摘要要入库、要渲染字段，模型直接吐一段自然语言，下游没法校验。让模型吐 JSON 也不够，还得约束字段与类型：接口支持声明 `response_format`，要求输出合法 JSON，这叫 JSON 模式；进一步可以用 JSON Schema 约定字段、类型与必填，缺字段、类型错在服务端就被拒绝。

```python
# 结构化：声明 response_format，再拿 Pydantic 校验（展示代码）
resp = httpx.post(
    f"{base_url}/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": "把下面这段介绍抽成 JSON，字段为 title 与 points 数组"}],
    },
    timeout=30.0,
)
summary = DocSummary.model_validate_json(resp.json()["choices"][0]["message"]["content"])
```

收到后先解析再校验，失败视为生成失败，走重试或降级。结构化越强，可靠性越高，创造力越低。摘要这类半结构化输出，常用结构化外壳加自由文本内核：外壳锁住 title、points 这些字段，内核留一段自由文字。

## 函数调用

结构化解决了结果可用，还有一个更根本的问题：模型不知道的东西，它会编。

文档问答里，用户问"这篇文档的作者是谁"，模型手里只有摘要，正确答案在数据库里。与其让它猜，不如给它工具去查。函数调用（function calling）就是干这个的：请求里附带一份工具清单，说明每个工具的名字、参数和用途；模型判断需要时，不直接回答，而是返回"我要调用 get_author，参数是……"；后端执行真正的查询，把结果塞回对话，再请模型组织语言回答。

```python
# 函数调用：模型开口要调，后端动手去查，结果塞回再答（展示代码）
tools = [{"type": "function", "function": {
    "name": "get_author",
    "parameters": {"type": "object", "properties": {"doc_id": {"type": "string"}}},
}}]
resp = httpx.post(
    f"{base_url}/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": model, "tools": tools, "messages": messages},
    timeout=30.0,
)
call = resp.json()["choices"][0]["message"]["tool_calls"][0]
result = get_author(**json.loads(call["function"]["arguments"]))
```

整套流程三步：模型开口要调，后端动手去查，结果塞回再答。有一个纪律要守住：模型给的参数也要校验，不对就拒绝并让它重给。工具是模型的眼睛和手，它能查到什么，决定它答得多准。

## key 与账单

能力讲完了，最后收两笔账。

一笔是成本账。token 按量计费，长文档先截断再送，流式边收边算，每次调用的耗时与用量都记进日志，[日志设计](../robustness_security/logging_design.md)一节有展开。

一笔是安全账。key 只放服务端环境变量，进仓库、进前端、进日志都是事故；真出了泄露，换 key 要快，所以 key 的读取只收敛在一处。

## 本节小结

- key 只放服务端，前端调自家后端，自家后端带 key 出网，读取收敛在一处。
- 流式让答案边生成边回来，增量逐段解析；结构化输出让结果能被程序校验和使用。
- 模型不知道的别让它编，函数调用三步走，要调、去查、塞回再答，参数不对就拒。
- token 按量计费，长文先截断，用量记日志；key 泄露是安全事故，收口与轮换都要准备好。
