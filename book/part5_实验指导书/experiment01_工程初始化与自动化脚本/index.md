# 实验一 工程初始化与自动化脚本

本实验对应理论 [第1章 开发者的元技能](../../part1_软件工程筑基/chapter01_开发者的元技能/index.md)。建议先通读该章的 1.1 至 1.4 节，再动手。你会在本实验中从零搭建一个可安装、可复现的 Python 项目，并用脚本把重复操作自动化。

## 实验目标

- 能用 `src` 布局从零创建标准 Python 项目，使 `pip install -e .` 后可在任意目录 `import` 包代码。
- 能编写符合 PEP 621 的 `pyproject.toml`，清晰声明项目元数据、依赖与工具配置。
- 能创建并激活虚拟环境，解释 `sys.prefix` 与 `sys.base_prefix` 分离的含义，并保证依赖可复现。
- 能配置 `pre-commit` 代码门禁，使不符合风格的提交在本地即被拦截。
- 能用 `subprocess` 与 `argparse` 编写一键启动脚本，支持参数校验与 `--help` 帮助信息。

## 任务步骤

### 步骤 1 准备空仓库与基础文件

1. 在本机新建空目录 `lab01-demo`，执行 `git init`，新建 `README.md` 与 `.gitignore`（忽略 `.venv/`、`__pycache__/`、`*.egg-info/`、`_build/` 等）。
2. 阅读 [第1章 1.1 工程化项目结构](../../part1_软件工程筑基/chapter01_开发者的元技能/1.1_工程化项目结构.md) 中关于 `src` 布局的讨论，理解为何 `src` 能避免导入歧义。

### 步骤 2 搭建 `src` 布局与 `pyproject.toml`

1. 创建目录结构：
   ```bash
   mkdir -p src/demo_pkg
   touch src/demo_pkg/__init__.py
   ```
2. 编写 `pyproject.toml`，至少包含 `[build-system]`、`[project]`（`name`、`version`、`requires-python`、`dependencies`）与 `[tool.setuptools]` 或 `[tool.setuptools.packages.find]`。
3. 参考本章示例与 `labs/lab01_工程初始化/starter/pyproject.toml` 中的最小声明，保持字段可解释。
4. 执行 `pip install -e .`，验证在任意目录 `python -c "import demo_pkg; print(demo_pkg.__file__)"` 能定位到 `src` 下的包。

> 跨平台提示：`pip install -e .` 在 macOS 与 Linux 上相同，Windows 上亦相同。路径分隔符在展示时用 `/`，`pathlib.Path` 会自动适配 `\`。

### 步骤 3 创建虚拟环境并验证隔离

1. 执行 `python -m venv .venv` 创建环境。
2. 激活环境：
   ```bash
   source .venv/bin/activate  # macOS / Linux
   .venv\Scripts\activate     # Windows CMD
   .venv\Scripts\Activate.ps1 # Windows PowerShell
   ```
3. 运行 `python -c "import sys; print(sys.prefix != sys.base_prefix)"`，确认输出 `True` 表示已在虚拟环境中。
4. 在环境内执行 `pip install -e .`，并用 `pip freeze` 观察 `demo_pkg` 是否可复现安装。

### 步骤 4 配置 `pre-commit` 门禁

1. 在 `pyproject.toml` 或独立配置中加入 `ruff` 规则（可参考 `[tool.ruff]` 最小集），确保 `ruff check .` 能运行。
2. 编写 `.pre-commit-config.yaml`，至少包含 `ruff` 检查与 `ruff --fix` 或格式化钩子。
3. 执行 `pre-commit install`，然后故意制造一个风格问题并尝试 `git commit`，观察钩子是否拦截。
4. 修复后重新提交，确认门禁通过。记录门禁拦截的提示信息，课堂上能解释其含义。

### 步骤 5 编写一键启动脚本

1. 以 `labs/lab01_工程初始化/starter/main.py` 为起点，扩展一个带 `argparse` 的命令行入口。要求：
   - 支持 `--help` 自动生成帮助信息。
   - 支持子命令或选项，例如 `--name`、`--verbose`、`--dry-run`。
   - 用 `subprocess.run([...], capture_output=True, text=True, check=True)` 调用至少一个外部命令（如 `git status` 或 `pip list`），禁止使用 `shell=True`。
2. 脚本需满足 `python starter/main.py --help` 退出码为 0 且打印帮助信息。
3. 将脚本入口同时声明到 `pyproject.toml` 的 `[project.scripts]`（可选），验证 `pip install -e .` 后可直接以命令名启动。

### 步骤 6 自检与清理

1. 删除 `.venv` 后重新按步骤 3 与步骤 2 复现安装，确认从零可在 3 分钟内恢复可运行环境。
2. 运行 `ruff check .` 与 `python -m py_compile src/demo_pkg/*.py`，确认无错误。
3. 用 `git status` 确认未提交无关文件，`git log --oneline` 可读。

## 验收标准

逐条自查，全部勾选即视为完成：

- [ ] 项目采用 `src` 布局，`src/demo_pkg/__init__.py` 存在，`pyproject.toml` 包含 `[build-system]` 与 `[project]` 关键字段且可被 `pip install -e .` 识别。
- [ ] 虚拟环境创建与激活流程在当前平台可复现，`sys.prefix != sys.base_prefix` 验证通过，`pip freeze` 能反映项目依赖。
- [ ] `pip install -e .` 后可 `import demo_pkg`，且从项目外目录导入仍成功，无 `sys.path` 手动拼接。
- [ ] `.pre-commit-config.yaml` 已配置且 `pre-commit install` 生效，故意违规的提交被拦截，修复后可通过。
- [ ] 启动脚本 `main.py` 具备 `if __name__ == "__main__": main()` 入口，`python main.py --help` 退出码为 0，`argparse` 帮助信息完整。
- [ ] 脚本中至少一处使用 `subprocess.run` 列表形式调用外部命令，未使用 `shell=True`，且包含 `try/except` 或 `check` 错误处理。
- [ ] `ruff check .` 无报错，`git status` 干净，无 `.venv`、`__pycache__` 等不应提交的内容。

## 提交要求

- 提交一个本地可复现的仓库目录或压缩包，包含 `src/`、`pyproject.toml`、`.pre-commit-config.yaml`、`main.py`（或等价启动脚本）、`README.md` 与 `.gitignore`。
- `README.md` 需说明环境创建、安装、门禁启用与脚本运行命令，保证助教按文档可在 5 分钟内复现。
- 不需要提交虚拟环境目录 `.venv`、编译产物与任何自动生成文件。
- 课堂验收以现场演示为准，能口头解释 `src` 布局价值、`pyproject.toml` 各段作用与 `pre-commit` 拦截原理。

## 预估用时

2 学时。

建议分配：步骤 1 至 2 约 40 分钟，步骤 3 至 4 约 40 分钟，步骤 5 至 6 约 40 分钟。剩余时间用于自检与课堂讨论。
