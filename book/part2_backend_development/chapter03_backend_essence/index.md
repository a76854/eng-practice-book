---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 后端开发到底是什么

> **本章学习目标**
> - 能够用一句话说清后端在“前端—后端—存储”三层中的职责边界，并用 API 设计、业务逻辑、数据流转、安全防护四要素解释一条请求的完整生命周期
> - 能够基于适用场景与代价对 Java / C# / Go / PHP 与 Python 做客观横向对比，并在给定约束下做出不偏袒的选型判断
> - 能够区分 Django（全栈）、Flask（微架构）、FastAPI（高性能异步）三类框架的生态定位与 trade-off
> - 能够用异步原生、自动文档、类型安全三条理由解释本书为何选择 FastAPI + Pydantic 作为后端主栈
> - 能够用 Controller-Service-Repository 三层在 Python 中落地一个可测试、可替换存储的最小后端切片

> **为什么需要掌握本章**
> 会写接口不等于理解后端。真实业务从“上传音频”到“返回纪要”要穿越网关、鉴权、校验、业务编排、持久化、外部服务集成与可观测性——每一步都在考验你对职责边界的判断。本章是第二篇的起点，也是全书从“代码质量”迈向“系统设计”的转折点：先把后端的版图与选型逻辑讲透，后续的 HTTP、存储、并发与部署才有落脚点。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节都先讲清工程痛点，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 1、2 章相同，所有示例均在书仓根目录的 `.venv` 环境中可复现，无需真实的 ASR 模型或 LLM 网络调用。

章内结构如下：

- [3.1 后端是什么](3.1_what_is_backend.md) —— 从展示、业务与存储混杂的痛点出发，用 JSON API、`/api` 前缀和四条职责线建立稳定边界
- [3.2 语言横向对比](3.2_language_comparison.md) —— 用负载、团队、存量、生态和运维约束客观比较 Java / C# / Go / PHP 与 Python
- [3.3 框架生态谱系](3.3_framework_ecosystem.md) —— 比较 Django、Flask、FastAPI 分别替团队承担哪些工程责任，以及各自的适用代价
- [3.4 为何选择 FastAPI](3.4_why_fastapi.md) —— 将 I/O 等待、前后端契约与边界校验映射到异步、OpenAPI 和 Pydantic
- [3.5 分层架构落地](3.5_layered_architecture.md) —— 用可替换 Repository 与可独立测试的 Service 落地 Controller—Service—Repository 单向依赖

此外，本章所有示例均可在书仓 `.venv` 环境中复现；涉及示例的片段统一通过教学包 `m2t` 复用（如 `m2t/store.py` 的 `TaskStore`），无需启动真实服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第2章 构筑代码质量的护城河](../../part1_software_engineering/chapter02_code_quality/index.md)。

示例（验证本章环境与核心依赖可用）：

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
# 验证 .venv 前缀（环境：.venv 目录名一致，路径分隔符由 pathlib 处理）
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
