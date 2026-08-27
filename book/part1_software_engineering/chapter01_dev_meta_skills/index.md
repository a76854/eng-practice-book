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
> 算法与业务代码只占工程的一小部分，真正决定交付速度与协作质量的是“元技能”——能否把项目组织清楚、把环境隔离开、把重复操作自动化、把协作历史讲明白。没有这些能力，代码写得再巧，也会在“在我机器上能跑”“合并冲突”“环境不一致”中反复消耗团队。本章以 MeetingToText 为贯穿案例，把环境、脚本与协作三件套一次讲透，为后续所有章节打下可复现的工程底座。

> **预计理论学时**：3学时

本章是全书的工程起点，也是后续十章的风格锚点。我们遵循“先动机、后定义、再可运行示例”的节奏：每一节都先讲清“为什么需要这个能力”，再给出最小可用定义，最后用一段可在本机复现的代码把概念固定下来。读完本章，你将拥有一套可直接用于课程大作业与实习项目的工程脚手架。

章内结构如下：

- [1.1 工程化项目结构](1.1_engineering_project_structure.md) —— 为什么 `src` 布局能避免导入陷阱，`pyproject.toml` 如何统一 PEP 517/518/621 的构建与元数据
- [1.2 依赖与虚拟环境](1.2_dependencies_virtualenv.md) —— `venv` / `conda` / `uv` 的选型与隔离原理
- [1.3 Shell、文件系统、进程与管道](1.3_shell_fs_process_pipe.md) —— 把 Shell 当作“可组合的文本流水线”来理解
- [1.4 Python 自动化脚本](1.4_python_automation_scripts.md) —— 用 Python 代替人肉重复劳动
- [1.5 Git 核心模型与工作流](1.5_git_core_model_workflow.md) —— 从对象模型看懂分支，再选对工作流

此外，本章所有示例均可在书仓根目录的 `.venv` 环境中复现；涉及 MeetingToText 的片段统一通过教学包 `m2t` 复用（见 [m2t 源码](../../..//m2t/audio.py) 的精简实现），无需启动真实的 ASR 或 LLM 服务。

> **跨平台约定**：本章所有涉及路径与环境激活的命令均标注 Windows / macOS / Linux 差异，详见各小节对照表；正文跨章引用一律使用相对链接，如 [第2章 构筑代码质量的护城河](../chapter02_code_quality/index.md)。

文件 `book/part1_software_engineering/chapter01_dev_meta_skills/demo_index.py`（验证本章环境与 m2t 教学包可用）：

```{code-cell} ipython3
# 文件 book/part1_software_engineering/chapter01_dev_meta_skills/demo_index.py
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
# 本章所有 code-cell 均用 .venv 中的 Python 执行（macOS / Linux）
.venv/bin/python -c "import m2t; print(m2t.__version__)"
# Windows 需用
.venv\Scripts\python.exe -c "import m2t; print(m2t.__version__)"
```
