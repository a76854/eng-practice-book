---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第4章 HTTP 与 RESTful 架构

> **本章学习目标**
> - 能够用方法语义、幂等性、状态码与 Header 四要素解释 HTTP 的设计意图，并在 FastAPI 中用契约化方式表达这些语义
> - 能够用 Richardson 成熟度模型（Level 0–3）辨析 RPC-style、资源、HTTP 动词与 Hypermedia 四个阶梯的代价与收益，并在 MeetingToText 的 API 上做出选型判断
> - 能够用 FastAPI + Pydantic 完成路径参数、查询参数与请求体的声明式校验，并解释校验失败如何以 422 统一暴露
> - 能够设计统一的成功/失败响应信封与全局异常处理器，使业务错误与校验错误在同一契约下可被前端可靠消费
> - 能够利用 FastAPI 自动生成的 OpenAPI/Swagger 契约完成前后端契约测试，理解“契约即代码”对协作的保障作用

> **为什么需要掌握本章**
> 后端的第一触点就是 HTTP：前端、网关、可观测与外部集成都通过它对话。把 HTTP 当作“发送 JSON 的管道”会让状态码随意、幂等性丢失、错误格式各异，调试与联调成本随之上扬。本章以示例后端路由（如 `upload` / `transcribe` / `export` / `health`）为例，把 HTTP 语义、RESTful 成熟度、FastAPI 路由、统一响应与 OpenAPI 契约串成一条可验证的协作闭环——让契约在代码中可执行，而非文档中可漂移。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清“为什么需要这个概念”，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 1、3 章相同，所有示例均在书仓根目录的 `.venv` 环境中用 `TestClient` 本地验证，无需真实的 ASR 模型、LLM 网络调用或外部服务。

章内结构如下：

- [4.1 HTTP 协议精髓](4.1_http_protocol_essence.md) —— HTTP 方法/状态码用法：方法语义、幂等性与状态码的契约化表达
- [4.2 RESTful 成熟度模型](4.2_restful_maturity_model.md) —— RESTful API 设计入门：从 RPC-style 到资源的演进与选型
- [4.3 FastAPI 路由设计](4.3_fastapi_routing.md) —— 路径/查询/请求体参数的声明式校验与依赖注入
- [4.4 异常处理与全局响应](4.4_exception_global_response.md) —— 统一返回格式与全局异常处理的协作价值
- [4.5 OpenAPI 契约测试](4.5_openapi_contract_test.md) —— 自动生成 Swagger 与前后端契约测试

此外，本章所有示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t.store.TaskStore` 与 FastAPI 的 `TestClient`（见 [m2t 源码](../../../m2t/store.py) 的精简实现），无需启动真实服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第3章 后端开发到底是什么](../chapter03_backend_essence/index.md)。

示例（验证本章环境与 FastAPI 核心依赖可用）：

```{code-cell} ipython3
import sys, pathlib

import m2t
from m2t.store import TaskStore
import fastapi, pydantic

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("fastapi:", fastapi.__version__)
print("pydantic:", pydantic.__version__)
print("TaskStore:", TaskStore.__name__)
print("prefix:", pathlib.Path(sys.prefix).name)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# fastapi: 0.141.x
# pydantic: 2.x.x
# TaskStore: TaskStore
# prefix: .venv 或系统前缀
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import m2t, fastapi, pydantic; print(m2t.__version__, fastapi.__version__)"
```
