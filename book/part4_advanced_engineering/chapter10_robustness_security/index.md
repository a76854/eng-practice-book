---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第10章 健壮性与安全底线

> **本章学习目标**
> - 能够用 HMAC-SHA256 自签与校验 JWT，解释头部 / 载荷 / 签名的分工，并设计短有效期访问令牌 + 长有效期刷新令牌的轮转与 RBAC 校验流程
> - 能够用参数化查询阻断 SQL 注入，用转义与 CSP 思路缓解 XSS，并用同步随机令牌缓解 CSRF，区分“校验输入”与“转义输出”的职责边界
> - 能够设计结构化、分级的日志方案，解释级别、上下文与采样，并用 ELK 的索引与检索思想完成从日志到可观测的闭环
> - 能够用错误边界与优雅降级把局部故障隔离在可控范围，给出重试有界、超时明确、回退可预期的容错策略

> **为什么需要掌握本章**
> 会跑的功能只是半成品，能在异常输入、恶意请求、依赖抖动与人为误操作下依然“可预期、可审计、可恢复”，才是可上线的系统。MeetingToText 从上传、转写到摘要与导出，每一步都暴露在不受信任的输入与不可靠的网络中；缺少认证与校验，接口就是敞开的门，缺少日志与降级，故障就是黑盒。本章把“安全与健壮性”收敛为四套可落地的工程手段，让系统在攻防与故障面前守住底线。

> **预计理论学时**：3学时

本章是第四篇的收束，也是全书从“把功能做出来”到“让系统可信”的转折。我们延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清真实故障或攻击如何发生，再给出最小可用模型，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 9 章相同，所有示例均在书仓根目录的 `.venv` 环境中用标准库与 `m2t` 教学包本地验证，无需真实的网络、云端密钥或外部服务。

章内结构如下：

- [10.1 认证与授权 JWT](10.1_auth_jwt.md) —— 无状态令牌的原理、签名与刷新、RBAC 的最小实现
- [10.2 数据校验与防注入](10.2_data_validation_injection.md) —— SQL 注入、XSS、CSRF 的成因与防御分层
- [10.3 日志系统设计](10.3_logging_design.md) —— 结构化日志、分级与采样、ELK 的检索思想
- [10.4 错误边界与优雅降级](10.4_error_boundary_graceful_degradation.md) —— 边界隔离、重试与回退、面向用户的可预期失败

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t` 教学包（见 [m2t 源码](../../../m2t/store.py) 的精简实现），无需启动真实的 ASR 模型或 LLM 服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第9章 与外部世界的集成](../chapter09_external_integration/index.md)。

文件 `book/part4_advanced_engineering/chapter10_robustness_security/demo_index.py`（验证本章环境与教学包可用）：

```{code-cell} ipython3
import sys, pathlib, hashlib, hmac, json, base64

import m2t
from m2t.store import TaskStore

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("TaskStore:", TaskStore.__name__)
# 快速验证标准库可完成 HMAC（后续 JWT 小节的基础）
msg = b"chapter10-index-check"
digest = hmac.new(b"demo-secret", msg, hashlib.sha256).hexdigest()
print("hmac sha256 prefix:", digest[:16])
assert len(digest) == 64
print("prefix:", pathlib.Path(sys.prefix).name)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# TaskStore: TaskStore
# hmac sha256 prefix: <16 位十六进制>
# prefix: .venv 或系统前缀
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import m2t; print(m2t.__version__)"
```
