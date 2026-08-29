---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 部署、容器化与持续集成

> **本章学习目标**
> - 能够说清部署从物理机到虚拟机再到容器的演进动因，并用隔离层级解释“在我机器上能跑”为何在容器化后才可复现
> - 能够编写层缓存友好的 Dockerfile，解释 COPY 顺序与多阶段构建对镜像体积与构建速度的影响，并读懂实验八 `labs/lab08_fullstack_container/starter/Dockerfile` 的层缓存设计
> - 能够用 `docker-compose.yml` 描述 Nginx 前端、后端与持久化服务的联动关系，并用 `depends_on` 与健康检查表达启动依赖
> - 能够用 GitHub Actions 的工作流、作业与步骤三层模型解释 CI 流水线，并说明校验、测试与编排校验如何串成门禁链路
> - 能够把上述能力串联为 MeetingToText 的“构建镜像 → 编排联调 → 自动化门禁”最小交付闭环，并在本地用纯文本解析完成可验证的交付预演

> **为什么需要掌握本章**
> 会写代码只是起点，让代码在任何机器上可复现、可回滚、可自动验证才是交付。MeetingToText 从单机脚本演进为前后端分离、依赖原生库与模型权重的服务后，“环境不一致”“上线靠人肉”“回归靠自觉”会成为最贵的隐形成本。本章把部署与交付收敛为三件可落地套件——用容器固化环境、用编排声明拓扑、用流水线固化门禁——让每一次提交都自动经过“构建—校验—联调预检”的可复现路径。

> **预计理论学时**：2学时

本章是第五篇实验之前的理论收官，也是全书从“把系统做对”到“把系统可重复地交出去”的转折。我们延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清真实的交付痛点，再给出最小可用抽象，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 9、10 章相同，所有示例均在书仓根目录的 `.venv` 环境中用标准库、`m2t` 教学包与 `yaml` 本地验证，无需启动 Docker 守护进程、真实镜像构建或外部网络。

章内结构如下：

- [11.1 部署演进史](11.1_deployment_evolution.md) —— 从物理机到虚拟机再到容器：隔离思想如何一步步收敛
- [11.2 Dockerfile 最佳实践](11.2_dockerfile_best_practices.md) —— 层缓存、多阶段构建与 COPY 顺序对构建速度的决定性影响
- [11.3 Docker Compose 编排](11.3_docker_compose_orchestration.md) —— 用声明式 YAML 让 Nginx、前后端与依赖服务按依赖有序联动
- [11.4 CI/CD 流水线](11.4_cicd_pipeline.md) —— GitHub Actions 的工作流、作业与步骤模型与本地可验证的门禁链路

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t` 教学包（见 [m2t 源码](../../../m2t/store.py) 的精简实现），部署与 CI 片段以通用内联示例呈现，并在实验八 `labs/lab08_fullstack_container/starter/` 提供可对照的 Dockerfile 与 Compose 脚手架，仅做文本与 YAML 解析，不依赖容器运行时。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第10章 健壮性与安全底线](../chapter10_robustness_security/index.md)。

示例（验证本章环境与教学包可访问）：

```{code-cell} ipython3
import sys, pathlib, importlib.metadata

import m2t
import yaml

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("yaml version:", yaml.__version__)
print("prefix:", pathlib.Path(sys.prefix).name)

print("index 校验通过：环境与教学包均可访问")
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# yaml version: 6.x.x
# prefix: .venv 或系统前缀
# index 校验通过：环境与教学包均可访问
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import m2t, yaml; print(m2t.__version__, yaml.__version__)"
```
