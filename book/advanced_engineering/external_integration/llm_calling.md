---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 大模型调用方法

学完本节，你能回答：

- 调外部服务的超时、重试、熔断，分别防什么
- key 为什么只能放服务端，不能进前端
- 流式响应解决什么问题，增量解析要注意什么
- 结构化输出解决什么问题，收到后还要做什么
- 调得起和丢不起，分别指哪两笔账

> 请专车要说清目的地，司机边开边报位置，到付打表，用平台账号叫车，别把银行卡给司机。大模型调用也一样，说清要什么，分段回，即时算价，钥匙放自己手里。

前三节是三个老帮手，本节是新同事，管答得聪明。本节在整章的位置是收束，调用外部服务的通用姿势加一个大模型的特殊处。目的是调得通、回得快、结果可用、账单不炸。本节代码真实调用兼容 OpenAI 的接口，有 key 实跑，无 key 降级，key 放环境变量。

## 调用外部服务的通用姿势

调谁都要先立三条规矩。超时防"永远等"，任何请求都要有 deadline，大模型 30 秒起步。重试防"抖一下"，网络闪断、429 限流可重试，4xx 传错了不重试。熔断防"雪崩"，下游持续失败就停一会，直接降级，不让请求堆积压垮自己。

Webhook 是反向调用，对方调你。支付成功、文档解析完成这类不知道什么时候好的通知，都走 Webhook。验签、幂等、尽快返回，三件事和调别人时一样，只不过角色反了过来。服务端代调外部 URL 时要校验目标，第 11 章数据校验节有呼应，SSRF 的口子不能开。

## 普通调用

key 放服务端，前端只调自家后端，自家后端带 key 调大模型。key 进前端等于把银行卡给司机，爬虫拿走随便刷，账单算你的。

```{code-cell} ipython3
import os
import httpx

api_key = os.environ.get("LLM_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

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

观测小结：有 key 时打出模型的一句话介绍，无 key 时只打印跳过信息，两种路径都不报错。`LLM_BASE_URL` 与 `LLM_MODEL` 可配，换兼容接口只改环境变量，不改代码。

## 流式响应

一次调用短则几秒，长则几十秒，等全量回来再渲染，用户体感是卡住。流式让模型边生成边吐增量，前端逐块渲染，首字时延从秒级降到百毫秒级。wire 格式极简，每行一个 `data:`，最后跟 `[DONE]`。

```{code-cell} ipython3
import json
import os
import httpx

api_key = os.environ.get("LLM_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

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
            delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
            parts.append(delta)
    print(f"收到 {len(parts)} 个增量，拼出 {sum(len(p) for p in parts)} 字")
```

观测小结：增量逐个到来，不能等 `[DONE]` 才解析，拼完再整体处理。前端用 `fetch` 读流逐块渲染，姿势与联调章的异步状态节是同一套，后端 SSE 与前端流式渲染前后呼应。

## 结构化输出

自由文本适合人读，不适合机器读。文档摘要要入库、要渲染字段，模型直接吐自然段，下游没法校验。结构化输出用 JSON Schema 约束模型只吐合法 JSON：

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

收到后先解析再校验，失败视为生成失败，走重试或降级。结构化越强，可靠性越高，创造力越低，摘要这类半结构化输出，常用结构化外壳加自由文本内核。

## 函数调用

模型不知道的别让它编，给它工具查。文档问答里，用户问"这篇文档的作者是谁"，模型手里只有摘要，正确答案在库里。函数调用让模型先说"我要调 get_author"，后端查库把结果塞回去，模型再组织语言：

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

三步走，模型开口要调，后端动手去查，结果塞回再答。函数返回也要做校验，模型给的参数不对，后端拒掉并告诉它重给。工具是模型的眼睛和手，眼睛看到的决定了它能答多准。

## key 与账单

调得起是成本账，token 按量计费，长文档先截断再送，流式边收边算，日志记下每次调用的耗时与用量，第 11 章日志节有呼应。丢不起是安全账，key 只放服务端环境变量，进仓库、进前端、进日志都是事故。出事换 key 要快，所以 key 的读取只收敛在一处。

## 本节小结

- 调外部服务先立规矩，超时防永远等，可重试的才重试，下游持续失败就熔断降级。
- key 只放服务端，前端调自家后端，自家后端带 key 出门，读取收敛在一处。
- 流式降首字时延，增量解析拼完再处理；结构化输出先解析再校验，失败走重试或降级。
- 模型不知道的别让它编，函数调用三步走，要调、去查、塞回再答，参数不对拒掉重给。
- token 按量计费，长文先截断，用量记日志，key 泄露等于丢钱包。
