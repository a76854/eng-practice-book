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

前面三节的对象存储、缓存、队列，都是后端自己的手艺，可以先把基础设施搭好、跑通，再上生产。本节的新同事不一样：大模型的能力不在自家服务器上，只能通过网络，一次次地向服务方借。向外部借力这件事，本章还没有系统讲过，而它有自己的规矩。一次调用可能花上十几秒，按字数计费，失败的方式也五花八门。

本节先给"调用外部服务"立一套通用规矩，超时、重试、熔断，这些规矩对大模型之外的支付、地图同样成立；再讲大模型自己的几件特殊事：怎么把问题送出去、怎么让答案边生成边回来、怎么让结果能被程序使用、怎么让它查到它不知道的东西；最后收在两笔账上，成本与安全。

## 调用外部服务的通用姿势

先从通用规矩开始。不管调的是大模型、支付还是地图，只要请求跨出自家机房，三件事要先定好。

超时防的是永远等下去。外部服务也可能卡死，不给请求设截止时间，自己的线程就被它拖住。任何外部调用都要有超时，大模型这类生成式接口，30 秒起步。

重试防的是抖一下。网络闪断、对方限流（429），这类错误过一会儿大概率能成功，值得重试，但要设次数上限并间隔退避；而 400 这类请求本身写错的错误，重试多少次都一样，不能重试。

熔断防的是雪崩。下游持续出错时，继续把请求灌过去只会堆积，把自己的资源也耗光。熔断的做法是：连续失败到一定程度，直接停掉对它的调用，快速失败、走降级，过一会儿再放少量请求试探。

还有一类交互方向相反的场景：不是我们请求别人，而是别人来通知我们。支付成功的通知、解析完成的回调，这类事件什么时候发生不由我们决定，做法是把自己的一个地址注册给对方，事件发生时由对方来调这个地址，这种模式叫 Webhook。收到的请求同样要验签、要幂等、要尽快返回，角色反过来，纪律不变。最后提醒一句：服务端代用户去请求外部 URL 时，目标地址要严格校验，否则它会变成攻击内网的跳板，这类漏洞叫 SSRF，[数据校验与注入防御](../robustness_security/data_validation_injection.md)一节会展开。

## 普通调用

规矩立好，从最小的一次调用开始。

调用大模型就是往它的接口发一条 HTTP 请求，把问题装进去，把回答取出来。兼容 OpenAI 的接口协议目前是事实标准，多数云端厂商和本地部署方案都照着它提供。第一个要定的是钥匙放哪：API key 只放服务端。前端直接带 key 的后果是爬虫抄走随便刷，账单全算你头上；正确结构是前端调自家后端，自家后端带 key 出网。

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

观测小结：有 key 时打出模型的一句话介绍，无 key 时只打印跳过信息，两种路径都不报错。`LLM_BASE_URL` 与 `LLM_MODEL` 可配，换厂商、切本地部署都只改环境变量，不改代码。

## 流式响应

调用能通了，体感问题随之而来：一次生成短则几秒，长则几十秒，等全量返回再渲染，用户对着空白页面干等。

流式的思路是边算边回：模型每生成一小段就把这一小段推给客户端，界面渐渐长出来，首字时延从秒级降到百毫秒级。协议上通常用 SSE（Server-Sent Events）：服务器持续输出若干行文本，每行以 `data:` 开头携带一段增量，最后用 `[DONE]` 收尾。

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

- 调外部服务先立三条规矩，超时防永远等，可重试的才重试，下游持续失败就熔断降级。
- key 只放服务端，前端调自家后端，自家后端带 key 出网，读取收敛在一处。
- 流式让答案边生成边回来，增量逐段解析；结构化输出让结果能被程序校验和使用。
- 模型不知道的别让它编，函数调用三步走，要调、去查、塞回再答，参数不对就拒。
- token 按量计费，长文先截断，用量记日志；key 泄露是安全事故，收口与轮换都要准备好。
