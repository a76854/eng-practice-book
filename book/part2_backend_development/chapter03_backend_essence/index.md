---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 后端开发到底是什么

> **本章学习目标**
> - 能够用一句话说清后端在前端、后端、存储三层中的职责边界，并用一体与分离的演进解释为何现代 Web 普遍采用 JSON API
> - 能够基于适用场景、生态与代价对 Java、C#、Go、PHP 与 Python 做客观横向对比，并对 Django、Flask 与 FastAPI 的框架谱系做出约束驱动的选型判断
> - 能够用异步原生、自动文档与类型安全三条理由解释在特定约束下为何选择 FastAPI
> - 能够用 Controller、Service、Repository 三层在 Python 中落地一个可测试、可替换存储的最小后端切片，并用本地测试验证完整链路

> **为什么需要掌握本章**
> 会写接口不等于理解后端。真实业务从接收请求到返回响应要穿越路由、校验、业务编排、持久化与防守，每一步都在考验职责边界的判断。本章是第二篇的起点，也是全书从代码质量迈向系统设计的转折，先把后端的版图与选型逻辑讲透，后续的 HTTP、存储与并发才有落脚点。

> **预计理论学时**：3学时

本章延续先动机、后定义、再示例的节奏，每一节都先讲清工程痛点，再给出最小可用定义，最后用可在本机复现的片段把概念固定下来。

章内结构如下：

- [3.1 后端是什么：从一体到分离](3.1_what_is_backend.md) —— 服务端模板直出与 JSON API 的演进、前端后端存储的三层定位与后端的四条边界
- [3.2 语言与框架生态](3.2_language_and_framework.md) —— 五种后端语言的横向对比与各自框架谱系，约束驱动的选型
- [3.3 FastAPI 与分层架构](3.3_fastapi_and_layered_architecture.md) —— AI 时代为何选 Python、为何在 Python 生态中选 FastAPI，以及 Controller、Service、Repository 的分层落地