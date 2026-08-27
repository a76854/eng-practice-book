# 实验一 工程初始化与自动化脚本

> 对应理论 [第1章 开发者的元技能](../../book/part1_software_engineering/chapter01_dev_meta_skills/index.md) · 2 学时 · 任务说明与验收标准同 `book/part5_lab_guide/experiment01_project_init_automation/index.md`

## 实验目标

- 能用 `src` 布局从零创建标准 Python 项目，使 `pip install -e .` 后可在任意目录 `import` 包代码。
- 能编写符合 PEP 621 的 `pyproject.toml`，清晰声明项目元数据、依赖与工具配置。
- 能创建并激活虚拟环境，解释 `sys.prefix` 与 `sys.base_prefix` 分离的含义，并保证依赖可复现。
- 能配置 `pre-commit` 代码门禁，使不符合风格的提交在本地即被拦截。
- 能用 `subprocess` 与 `argparse` 编写一键启动脚本，支持参数校验与 `--help` 帮助信息。

## 任务步骤

### 步骤 1 准备空仓库与基础文件

1. 新建空目录 `lab01-demo`，执行 `git init`，新建 `README.md` 与 `.gitignore`。
2. 阅读第1章 1.1 节关于 `src` 布局的讨论。

### 步骤 2 搭建 `src` 布局与 `pyproject.toml`

1. 创建 `src/demo_pkg/__init__.py`。
2. 编写 `pyproject.toml`，至少包含 `[build-system]`、`[project]` 与包发现配置。
3. 执行 `pip install -e .` 并验证任意目录 `import demo_pkg` 成功。

### 步骤 3 创建虚拟环境并验证隔离

1. `python -m venv .venv` 并按平台激活。
2. 验证 `sys.prefix != sys.base_prefix` 为 `True`。
3. 在环境内 `pip install -e .`，用 `pip freeze` 观察依赖。

### 步骤 4 配置 `pre-commit` 门禁

1. 在 `pyproject.toml` 中加入 `[tool.ruff]` 最小规则集。
2. 编写 `.pre-commit-config.yaml` 并执行 `pre-commit install`。
3. 故意制造风格问题并尝试提交，观察拦截与修复流程。

### 步骤 5 编写一键启动脚本

1. 以 `starter/main.py` 为起点，扩展 `argparse` 入口，支持 `--help`、`--name`、`--verbose` 等选项。
2. 用 `subprocess.run([...], capture_output=True, text=True, check=True)` 调用至少一个外部命令，禁止 `shell=True`。
3. 验证 `python starter/main.py --help` 退出码为 0。

### 步骤 6 自检与清理

重新创建环境并复现安装，运行 `ruff check .` 与 `python -m py_compile`，确认干净。

## 验收标准

- [ ] `src` 布局正确，`pyproject.toml` 关键字段完整且 `pip install -e .` 可用。
- [ ] 虚拟环境可复现，`sys.prefix != sys.base_prefix` 验证通过。
- [ ] 任意目录 `import demo_pkg` 成功，无 `sys.path` hack。
- [ ] `pre-commit` 生效，违规提交被拦截。
- [ ] `python starter/main.py --help` 退出码为 0，帮助信息完整。
- [ ] 脚本使用 `subprocess.run` 列表形式调用，未用 `shell=True`，含错误处理。
- [ ] `ruff check .` 无报错，`git status` 干净。

## 提交要求

提交包含 `src/`、`pyproject.toml`、`.pre-commit-config.yaml`、启动脚本、`README.md` 与 `.gitignore` 的仓库。`README.md` 需写清环境创建、安装、门禁启用与运行命令。无需提交 `.venv` 等生成物。以演示与口头解释作为验收。

## 预估用时

2 学时。

## 起手代码

见 `starter/` 目录。运行 `python starter/main.py --help` 验证起点可执行。
