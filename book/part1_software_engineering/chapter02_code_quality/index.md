---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第2章 构筑代码质量的护城河

> **本章学习目标**
> - 能够用 Python 类型标注与 `mypy` 严格模式在提交前捕获类型不一致，并用防御性编程让非法状态不可表示
> - 能够用 `Ruff` 统一替代 `Flake8` / `Black` / `isort` 完成静态检查与自动格式化，并在 `pyproject.toml` 中声明可复现的规则集
> - 能够按测试金字塔与 AAA 模式设计 pytest 用例，覆盖边界条件与异常路径
> - 能够用 `pytest` 的 `fixture` 作用域与 `unittest.mock` 隔离外部依赖（文件、网络、ASR/LLM）
> - 能够用覆盖率度量与 CI 质量门禁把“能跑”提升为“可信”，并解释覆盖率的边界与误用

> **为什么需要掌握本章**
> 第 1 章解决了“项目能跑、环境可复现、协作有秩序”，但“能跑”不等于“可信”。真实的 MeetingToText 流水线中，一次未校验的空字符串、一个未处理的 `None`、一段未覆盖的异常分支，都可能在演示现场或线上演变为静默失败。本章把类型、风格、测试与覆盖率四道工序织成护城河：类型系统在编辑期拦住形状错误，静态检查在提交前统一风格与低级缺陷，测试金字塔在运行期验证行为，覆盖率与门禁在协作期守住底线。四者共同回答“如何让代码在他人与时间面前仍然可靠”。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节都先讲清工程痛点，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定到 `m2t` 真实代码上。与第 1 章相同，所有示例均在书仓根目录的 `.venv` 环境中可复现，无需真实的 ASR 模型或 LLM 网络调用。

章内结构如下：

- [2.1 类型系统与防御性编程](2.1_type_system_defensive_programming.md) —— 为什么需要类型标注，`mypy` 严格模式如何把“约定”变成“检查”，防御性编程如何让错误尽早失败
- [2.2 静态检查与代码风格](2.2_static_check_code_style.md) —— `Ruff` 如何一站式替代 `Flake8` / `Black` / `isort`，工程化配置与自动修复的落地路径
- [2.3 测试的工程思维](2.3_testing_engineering_mindset.md) —— 测试金字塔、AAA 模式与边界条件，`pytest` 断言与最简可信用例
- [2.4 Pytest 进阶](2.4_pytest_advanced.md) —— `fixture` 作用域、工厂与 `unittest.mock` 对外部依赖的隔离
- [2.5 测试覆盖率与质量门禁](2.5_test_coverage_quality_gate.md) —— 覆盖率的度量、解读与 CI 红线，避免“为数字而测试”

此外，本章所有示例均可通过教学包 `m2t` 复用（如 `m2t/audio.py`、`m2t/store.py`、`m2t/export.py` 的真实签名），无需启动真实服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../chapter01_dev_meta_skills/index.md)。

文件 `book/part1_software_engineering/chapter02_code_quality/demo_index.py`（验证本章环境与 `m2t` 教学包可用）：

```{code-cell} ipython3
# 文件 book/part1_software_engineering/chapter02_code_quality/demo_index.py
import sys, pathlib

import m2t
from m2t.audio import load_audio
from m2t.store import TaskStore
from m2t.export import export

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("m2t modules:", [m for m in dir(m2t) if not m.startswith("_")][:5])
# 验证核心 API 可导入（无需真实模型/网络）
print("load_audio:", load_audio.__name__)
print("TaskStore:", TaskStore.__name__)
print("export:", export.__name__)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# m2t modules: [...]
# load_audio: load_audio
# TaskStore: TaskStore
# export: export
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import m2t; print(m2t.__version__)"
```
