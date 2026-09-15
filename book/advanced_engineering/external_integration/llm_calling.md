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

前面三节讲了对象存储、缓存、队列，是后端为了解决文件存储、快速数据查询和处理访问压力。本节的讲一下调用大模型，大模型调用通常不使用进程间通信，而是通过网络向服务提供商发送 RPC 请求。本节从模型的调用讲起，涉及到收发请求和请求校验

## 普通调用

调用大模型就是往它的接口发一条 HTTP 请求，把数据装进去，把数据取出来。本节用 DeepSeek 的接口做示例（模型 `deepseek-flash`）：它兼容 OpenAI 协议，同类厂商与本地部署方案大多遵循同一协议，换一家只改地址与模型名。这些服务通常都是付费的，因此需要秘钥鉴权，使用秘钥的时候也需要注意保密。秘钥通常可以使用环境变量设定，也可以放在`.env`文件中，然后从文件中读取，注意，任何时候都不要把秘钥直接卸载代码中，更不允许进去前端^[有疑问的同学去看看为什么会有前后端分离]。

```{code-cell} ipython3
import os
import httpx

api_key = os.environ.get("LLM_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
model = os.environ.get("LLM_MODEL", "deepseek-flash")

if not api_key:
    print("未配置 LLM_API_KEY")
else:
    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": [
            {"role": "user", "content": "用一句话介绍 pydantic，不得超过200字"},
        ]},
        timeout=30.0,
    )
    resp.raise_for_status()
    print(resp.json()["choices"][0]["message"]["content"])
```

大模型会返回 `Pydantic` 的用法。

## 流式响应

调用能通了，你现在会发现一个问题，大模型的答案是一个字一个字吐出来的，一次生成短则几秒，长则几十秒，等全量返回再渲染，用户对着空白页面等的也着急，而且不知道是否是服务卡了，需要调试。

流式的思路是边算边回：模型每生成一小段就把这一小段推给客户端，界面渐渐长出来，首字时延从秒级降到百毫秒级。协议上通常用 SSE（Server-Sent Events），服务器持续输出若干行文本，每行以 `data:` 开头携带一段增量，最后用 `[DONE]` 收尾。

```{code-cell} ipython3
# 流式调用
import json
import os
import httpx

api_key = os.environ.get("LLM_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
model = os.environ.get("LLM_MODEL", "deepseek-flash")

if not api_key:
    print("未配置 LLM_API_KEY")
else:
    parts = []
    with httpx.stream(
        "POST",
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "stream": True, "messages": [
            {"role": "user", "content": "用三句话介绍 pydantic，每句不得超过200字"},
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

由于结果是死的，你并不能看到流式输出，读者可以将这段代码复制粘贴真实运行一下。

## 结构化输出

前面的小节，大模型的结果只能给人看，没办法给程序看，程序需要固定结构的输入，而大模型的输出是自然语言，程序不能直接理解。但是我们可以通过规约大模型输出，限制其必须输出结构化字段，让模型吐 JSON 。

接下来一个问题，还得约束字段与类型，接口支持声明 `response_format`，要求输出合法 JSON，这叫 JSON 模式；进一步可以用 JSON Schema 约定字段、类型与必填，缺字段、类型错在服务端就被拒绝。

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

相对于写死的程序，大模型的输出更加自由，如果需要大模型执行一些特定的任务，收到数据后先解析再校验，失败视为生成失败，走重试或降级。结构化越强，可靠性越高，创造力越低。

## 函数调用

结构化解决了结果可用，还有一个问题--模型幻觉--模型不知道的东西，它会编。先想一个问题: **1+2等于几？**，*不就是3吗？* **啊，那3+3**，*6啊*，显然这非常容易，但是对于大模型来说这并不是一个简单的问题，每当有一个新模型发布时，就有好事者用这些简单问题测试。这类测试之所以反复出现，是因为它暴露的不是模型的知识多少，而是它生成答案的方式：它给出的始终是“最可能出现的下一个词”，不是在心里跑一遍加法，位数一多，这种凭印象的错误就越明显。在提示词里写“请仔细计算”能缓解，治不了根。

换个角度就清楚了：加法这件事，与其让模型硬算，不如交给一个真的会算的东西。给它一个 `calculator` 工具，由模型判断“这个问题需要算”，真正的计算由后端执行，约束了准确性。

这就是函数调用（function calling）：请求里附带一份工具清单，说明每个工具叫什么、参数是什么、什么时候用；模型判断需要时，不直接给答案，而是返回“我要调用 `calculator`，参数是 `...`”；后端执行查询，把结果塞回对话，模型再拿着结果组织语言。一次问答因此变成两次往返，消息列表多了一进一出。

| 角色 | 谁写的 | 作用 |
| --- | --- | --- |
| `system` | 开发者 | 设定身份与规则，如“只根据工具返回值回答” |
| `user` | 用户 | 提出问题 |
| `assistant` | 模型 | 直接回答，或提出工具调用 |
| `tool` | 后端 | 工具的执行结果，带回给模型 |

工具结果是以 `tool` 角色塞回对话的，模型下一条回复才能引用它。

下面这段代码给模型一个真实的 `add` 工具，让它算 3+3+3：模型不自己心算，而是开口要调工具，后端算完把结果塞回，模型再据此给出答案。没有配置 key 时这段会跳过，配置好之后可以真实跑一次。

```{code-cell} ipython3
# 给模型一个加法工具，让它算 3+3+3
import json
import os

import httpx

api_key = os.environ.get("LLM_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
model = os.environ.get("LLM_MODEL", "deepseek-flash")

TOOLS = [{"type": "function", "function": {
    "name": "add",
    "description": "计算两个数之和，遇到加法必须调用它，不要心算",
    "parameters": {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    },
}}]

def add(a: float, b: float) -> float:
    return a + b

def ask_model(messages: list[dict]) -> dict:
    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "tools": TOOLS, "messages": messages},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


if not api_key:
    print("未配置 LLM_API_KEY")
else:
    messages = [{"role": "user", "content": "请计算 3+3+3，每一步都要用 add 工具，不要自己心算"}]
    answer = None
    for round_no in range(1, 5):
        reply = ask_model(messages)
        messages.append(reply)
        calls = reply.get("tool_calls") or []
        if not calls:
            answer = reply.get("content")
            break
        for call in calls:
            args = json.loads(call["function"]["arguments"])
            print(f"第 {round_no} 轮：模型要调 {call['function']['name']}{args}")
            result = add(**args)
            print(f"  后端执行 add 得到 {result}，塞回对话")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": str(result)})
    print("模型回答:", answer if answer else "（轮次用尽，模型仍未给出最终答案）")
    print("消息序列:", [m["role"] for m in messages])
```

模型并没有“算”这道加法，它只负责判断“该调 add”并把参数递过来，真正的求和发生在代码里。3+3+3 要两次调用才走得完，这也说明函数调用为什么得写成循环，而不是发一次请求就完事。模型给的参数也要校验。参数是模型生成的，它可能把数字写成字符串 `"3"`，也可能少传一个字段，后端在执行前先校验类型与必填，不通过就拒绝执行并把错误塞回对话，让它重给。这实际上就是一个最简单的agent。

## 本节小结

- key 只放服务端，前端调自家后端，自家后端带 key 出网，读取收敛在一处。
- 流式让答案边生成边回来，增量逐段解析；结构化输出让结果能被程序校验和使用。
- 模型不知道的别让它编，函数调用三步走，要调、去查、塞回再答，参数不对就拒。
