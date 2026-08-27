---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第1章 开发者的元技能

> **本章学习目标**
> - 能够用 `src` 布局与 `pyproject.toml`（PEP 517/518/621）从零搭建一个可安装、可测试的 Python 工程，并解释每个配置段的作用
> - 能够根据项目规模选型 `venv` / `conda` / `uv`，并用可复现的方式阐明虚拟环境隔离的本质
> - 能够用 Shell 的文件系统、进程与管道思想完成日常工程操作，并用 Python 复刻其核心抽象
> - 能够用 `subprocess` / `shutil` / `argparse`（或 `click`）编写可复用、带参数校验的自动化脚本与命令行工具
> - 能够用 Git 对象模型（blob / tree / commit）解释分支与合并的本质，并对比 Git Flow 与 GitHub Flow 的适用边界

> **为什么需要掌握本章**
> 算法与业务代码只占工程的一小部分，真正决定交付速度与协作质量的是“元技能”——能否把项目组织清楚、把环境隔离开、把重复操作自动化、把协作历史讲明白。没有这些能力，代码写得再巧，也会在“在我机器上能跑”“合并冲突”“环境不一致”中反复消耗团队。本章把环境、脚本与协作三件套一次讲透，为后续所有章节打下可复现的工程底座，所用示例均围绕一个通用的 Python 项目展开，无需任何特定领域背景即可跟随。

> **预计理论学时**：3学时

本章是全书的工程起点，也是后续十章的风格锚点。我们遵循“先动机、后定义、再可运行示例”的节奏：每一节都先讲清“为什么需要这个能力”，再给出最小可用定义，最后用一段可在本机复现的代码把概念固定下来。读完本章，你将拥有一套可直接用于课程大作业与实习项目的工程脚手架。

章内结构如下：

- [1.1 工程化项目结构](1.1_engineering_project_structure.md) —— 为什么 `src` 布局能避免导入陷阱，`pyproject.toml` 如何统一 PEP 517/518/621 的构建与元数据
- [1.2 依赖与虚拟环境](1.2_dependencies_virtualenv.md) —— `venv` / `conda` / `uv` 的选型与隔离原理
- [1.3 Shell、文件系统、进程与管道](1.3_shell_fs_process_pipe.md) —— 把 Shell 当作“可组合的文本流水线”来理解
- [1.4 Python 自动化脚本](1.4_python_automation_scripts.md) —— 用 Python 代替人肉重复劳动
- [1.5 Git 核心模型与工作流](1.5_git_core_model_workflow.md) —— 从对象模型看懂分支，再选对工作流

本章所有示例均可在书仓根目录的 `.venv` 环境中复现。正文示例优先使用通用项目名 `myproject` / `mypackage` / `demo`，通过教学包 `m2t`（见 [m2t 源码](../../..//m2t/audio.py)）提供可运行的最小实现，无需启动任何外部服务即可验证概念。每节末尾的“贯穿案例”会将通用做法映射到具体项目，帮助你在后续章节中平滑过渡到真实案例。

> **贯穿案例 — MeetingToText**：本书以 MeetingToText（会议录音转写与纪要生成）作为全书贯穿案例。第1章仅在每节末尾以案例框形式出现，帮助你把通用工程模式与真实项目对照理解。从第2章起，随着业务复杂度提升，案例会逐步成为正文主角。

> **环境约定**：全书命令均面向 **Linux**（以 Ubuntu / Debian 系为例）。路径与环境激活命令统一使用 Linux 语法与 `/` 分隔符；正文示例均可在书仓根目录的 `.venv` 环境中直接复现。正文跨章引用一律使用相对链接，如 [第2章 构筑代码质量的护城河](../chapter02_code_quality/index.md)。

文件 `book/part1_software_engineering/chapter01_dev_meta_skills/demo_index.py`（验证本章环境与教学包可用）：

```{code-cell} ipython3
import sys, pathlib, importlib.metadata

# 验证教学包 m2t 可导入（无需真实模型）
import m2t
print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("platform sys.prefix:", pathlib.Path(sys.prefix).name)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# platform sys.prefix: .venv 或系统前缀
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import m2t; print(m2t.__version__)"
```
