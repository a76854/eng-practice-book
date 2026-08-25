---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 周1 工程环境与项目骨架

> 为什么先搞环境？因为「能在自己机器上把项目跑起来」是所有后续工作的前提。没有可复现的环境，再好的算法也无法交付、无法协作、无法测试。本章先把工程化的地基打牢：学会用合适的工具隔离 Python 环境、理解前端为什么需要 Node、管理依赖的唯一真相来源 `pyproject.toml`，并掌握「拿到任意一个项目都能跑起来」的通用三步。学完本章，你拿到 MeetingToText（或任何一个规范的 Python 项目）都能在 10 分钟内跑通。

## 学习目标

完成本章后，你将能够：

1. 能解释 `venv` / `uv` / `miniforge` 各自解决什么问题，并为新项目选择合适的环境方案。
2. 能阅读并解释 `pyproject.toml` 中 `project.dependencies` / `requires-python` / `[project.scripts]` 三个段落的含义。
3. 能按「读 README → 建环境装依赖 → 跑入口」三步，在干净机器上把 MeetingToText（或同类项目）跑起来。
4. 能通过改动 `requires-python` / `__init__.py` / `[project.scripts]` 并预测行为，验证对 Python 包机制的理解。

## 先修要求

- 会用命令行（`cd` / `ls` / `cat`）与 Git 克隆项目。
- 装有 Python ≥3.12（系统自带或官网安装均可，本章会教你隔离）。
- 无需前端基础，Node 部分从零讲起。

## 正文

### 1.1 Python 环境管理：venv / uv / miniforge

Python 的「环境问题」本质是隔离：不同项目依赖不同版本的库，甚至不同版本的 Python 本身。三种主流工具分工不同：

| 工具 | 是什么 | 何时用 |
|---|---|---|
| `venv` | Python 标准库自带的虚拟环境，创建与项目绑定的独立 `site-packages` | 只需隔离 Python 包、无需多版本 Python 时；零额外安装 |
| `uv` | Astral 出品的极速包管理器与环境管理器（Rust 编写），兼容 `pip`/`venv` 接口，安装与解析快 10–100 倍 | 日常开发首选；需要快速创建环境、安装依赖、运行脚本时 |
| `miniforge` | 社区驱动的 `conda` 发行版（基于 `conda-forge`），能管理 Python 解释器本身与非 Python 依赖（如 `ffmpeg`、`librosa` 的系统库） | 需要多版本 Python 共存、或依赖含 C/Fortran/二进制扩展且 `pip` 难装时 |

三者可组合：用 `miniforge` 管理 Python 解释器，用 `uv` 管理包，用 `venv` 作为最轻量的备选。不要混淆「环境管理器」与「包管理器」的职责。

安装命令（示意片段，`{占位符}` 需替换为实际值）：

```bash
# venv（标准库，无需安装）
python3 -m venv {环境目录}
source {环境目录}/bin/activate

# uv（官方安装脚本）
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .

# miniforge（以 Linux x86_64 为例）
curl -L -O https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash Miniforge3-Linux-x86_64.sh
mamba create -n {环境名} python=3.12
mamba activate {环境名}
```

> 提示：本书仓库已提供 `.venv`，执行 `pip install -e .` 即可安装教学包 `m2t`（`import m2t` 可用）。MeetingToText 同理：克隆后 `pip install -e .`，入口命令见下文。

验证环境是否生效：

```{code-cell} ipython3
import sys
print(sys.version)
print(sys.executable)
```

### 1.2 Node / npm（前端依赖）

MeetingToText 的前端在 `frontend/` 目录下，是独立的 Vite + Vue 3 项目。前端依赖与 Python 完全隔离，由 Node.js 与 `npm` 管理：

```bash
# 安装 Node 20（推荐 nvm 或 fnm 管理多版本）
nvm install 20
nvm use 20
node -v  # 应显示 v20.x

# 安装前端依赖并启动开发服务器
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173，vite proxy 将 /api 转发至 http://localhost:8000
```

关键文件：

- `frontend/package.json`：声明前端依赖与脚本（`dev` / `build` / `preview`）。
- `frontend/package-lock.json`：钉死依赖树，确保 `npm ci` 可复现安装。

Python 开发者常见误区：把 `npm install` 当成「装 Python 包」——它只影响 `frontend/node_modules/`，与 `.venv` 互不干扰。

### 1.3 pyproject.toml 结构

`pyproject.toml` 是现代 Python 项目的唯一真相来源（PEP 517/518/621）。以 MeetingToText 为例（只读参考，字段以 HEAD 为准）：

```toml
[project]
name = "meetingtotext"
version = "0.1.0"
description = "会议录音转写与纪要生成系统"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "openai>=1.60.0",
    # ...
]

[project.scripts]
meetingtotext = "cli:main"

[tool.setuptools]
py-modules = ["cli"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not system'"
```

逐段解释：

- **`project.dependencies`**：运行时依赖列表。`pip install -e .` 会读取此表并安装；版本号用 `>=` 下界约束，保证兼容性。开发期额外依赖在 `[project.optional-dependencies]`（如 `dev = ["pytest", "ruff"]`）。
- **`requires-python`**：声明支持的 Python 版本区间。`>=3.12` 表示低于 3.12 的解释器应拒绝安装；`pip` 会在解析时检查此字段。
- **`[project.scripts]`**：声明命令行入口。`meetingtotext = "cli:main"` 表示安装后生成可执行命令 `meetingtotext`，其实现为 `cli` 模块的 `main` 函数。等价于手写一个 `bin/meetingtotext` 脚本，但由安装器自动生成、跨平台可用。

本书仓库 `pyproject.toml` 结构相同，`[project.scripts]` 暂未声明 CLI，教学包通过 `import m2t` 使用。

用代码解析一段 `pyproject.toml` 字符串（可运行）：

```{code-cell} ipython3
import sys
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

pyproject_text = """
[project]
name = "meetingtotext"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastapi>=0.115.0", "uvicorn[standard]>=0.34.0"]

[project.scripts]
meetingtotext = "cli:main"
"""

data = tomllib.loads(pyproject_text)
print("name:", data["project"]["name"])
print("requires-python:", data["project"]["requires-python"])
print("scripts:", data["project"]["scripts"])
print("deps:", data["project"]["dependencies"][:2])
```

### 1.4 拿到任意一个项目都能跑起来的通用三步

无论是 MeetingToText、本书仓库，还是你未来的任何项目，通用流程都是：

**第 1 步：读 README**

找到「快速开始 / Quick Start」小节，确认：

- 需要什么前置（Python 版本、Node 版本、系统依赖如 `ffmpeg`）。
- 安装命令是什么（`pip install -e .` 还是 `pip install -r requirements.txt`）。
- 启动命令是什么（`meetingtotext serve --reload` 还是 `python -m m2t`）。

MeetingToText 的 README 即按此组织：先 `pip install -e .`，再 `cd frontend && npm install`，最后 `meetingtotext serve --reload` 启动后端、`npm run dev` 启动前端。

**第 2 步：建环境、装依赖**

```bash
# 克隆
git clone {仓库URL}
cd {项目目录}

# 建环境（三选一，见 1.1）
uv venv --python 3.12 && source .venv/bin/activate
# 或 python3 -m venv .venv && source .venv/bin/activate

# 装依赖
pip install -e .          # 含 project.dependencies
pip install -e ".[dev]"   # 额外装开发依赖（pytest/ruff/mypy）
# 前端另装
cd frontend && npm install && cd ..
```

**第 3 步：跑入口**

```bash
# 后端（MeetingToText 示例）
meetingtotext serve --reload
# 访问 http://localhost:8000/docs（FastAPI 自动生成的 OpenAPI 文档）

# 本书仓库（验证 m2t 可用）
python -c "import m2t; print(m2t.__version__)"
```

如果第 3 步失败，回退检查：第 1 步是否漏了前置？第 2 步是否在正确的虚拟环境中执行？`which python` 与 `which meetingtotext` 是否指向 `.venv` 内？

再验证一次本书环境：

```{code-cell} ipython3
import m2t
print("m2t version:", m2t.__version__)
# 解析 pyproject.toml 的小工具（习题也会用到同类函数）
import sys
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

sample = '[project]\nname="demo"\nrequires-python=">=3.12"\n'
info = tomllib.loads(sample)
print("parsed requires-python:", info["project"]["requires-python"])
```

### 改动并预测

以下 4 个改动并预测实验均可在本章的 `{code-cell}` 或本地 shell 中复现。每个改动并预测实验按「改什么 → 预测 → 解释」三段式书写。

#### 改动并预测 实验 1：改 `requires-python` 为未来版本 → 预测 pip 行为

- **改什么**：把 `pyproject.toml` 中的 `requires-python = ">=3.12"` 改为 `requires-python = ">=3.99"`（一个不存在的未来版本），然后在 Python 3.12 环境中执行 `pip install -e .`。
- **预测**：`pip` 会报错拒绝安装，提示当前 Python 版本不满足要求（类似 `Requires-Python >=3.99` / `no matching distribution`）。
- **解释**：`requires-python` 是安装时的版本门槛，由 `pip` 在解析阶段检查。改成未来版本后，当前解释器 3.12 落在区间外，安装器直接拒绝，避免在不兼容的解释器上装出不可运行的环境。还原为 `>=3.12` 后即可正常安装。

#### 改动并预测 实验 2：删 `__init__.py` → 预测导入行为

- **改什么**：在 `m2t/` 包目录中临时重命名或删除 `m2t/__init__.py`，然后执行 `python -c "import m2t; print(m2t.__version__)"`。
- **预测**：Python 3.12 仍能 `import m2t`（因为 PEP 420 命名空间包允许无 `__init__.py` 的包），但 `m2t.__version__` 会报 `AttributeError`（该属性定义在 `__init__.py` 中）。
- **解释**：自 Python 3.3 起，没有 `__init__.py` 的目录可作为命名空间包被导入，但包初始化代码（`__version__` 等）不会执行。本项目依赖 `__init__.py` 暴露版本与文档，属于「常规包（regular package）」而非命名空间包，故需保留该文件。

#### 改动并预测 实验 3：改 `[project.scripts]` 入口名 → 预测命令变化

- **改什么**：把 `[project.scripts]` 中的 `meetingtotext = "cli:main"` 改为 `mtt = "cli:main"`，重新 `pip install -e .`，然后分别尝试 `meetingtotext --help` 与 `mtt --help`。
- **预测**：`meetingtotext` 命令不存在（`command not found`），`mtt --help` 生效并打印帮助信息。
- **解释**：`[project.scripts]` 的键即生成的可执行文件名，值 `cli:main` 指定入口函数。改名后安装器只生成新名字对应的脚本，旧名字不会保留。验证了「入口名由配置决定，而非代码文件名」的机制。

#### 改动并预测 实验 4：改 `project.dependencies` 删一项 → 预测运行时行为

- **改什么**：把 `project.dependencies` 中的 `fastapi>=0.115.0` 删除，重新 `pip install -e .`（或在已安装环境中 `pip uninstall fastapi -y`），然后执行 `python -c "import m2t.llm; print('import ok')"` 与 `python -c "from fastapi import FastAPI; print('fastapi ok')"` 对比。
- **预测**：`import m2t` 仍成功（`m2t` 的核心依赖仅 `numpy`/`soundfile`，见本书 `pyproject.toml`），但 `from fastapi import FastAPI` 报 `ModuleNotFoundError`；若尝试启动 `meetingtotext serve` 则直接失败。
- **解释**：`project.dependencies` 是「声明式依赖」，删掉即表示项目不再声明需要该库，安装器不会自动装它。`m2t` 与 `meetingtotext` 的依赖集合不同，验证了「依赖按项目声明、按需安装」的原则——不要把未声明的库当成已可用。

## 习题

> 参考答案与测试在 `answers/week01/`，运行 `pytest answers/week01/ -q` 验证。题目均为 hermetic 纯函数，不依赖网络或外部服务。

1. **解析 `requires-python`**：实现 `parse_requires_python(pyproject_text: str) -> str`，从 `pyproject.toml` 文本中解析 `project.requires-python`，不存在则返回 `""`。
2. **必填字段检查**：实现 `required_fields_present(pyproject_text: str) -> list[str]`，检查 `project.name` / `project.version` / `project.requires-python` / `project.dependencies` 四项是否齐全，返回缺失字段名列表（空列表表示齐全）。
3. **版本约束校验**：实现 `normalize_version_constraint(s: str) -> bool`，判断字符串是否为合法的版本约束（如 `>=3.12`、`==1.0.0`、`~=2.3`、`*`），非法返回 `False`。
4. **入口脚本解析**：实现 `parse_scripts(pyproject_text: str) -> dict[str, str]`，解析 `[project.scripts]` 段，返回 `{命令名: "模块:函数"}` 映射，无该段返回 `{}`。
5. **依赖名提取**：实现 `extract_dependency_names(pyproject_text: str) -> list[str]`，从 `project.dependencies` 中提取包名列表（如 `"fastapi>=0.115.0"` → `"fastapi"`），保持原顺序。
6. *（附加）* 实现 `is_python_version_compatible(requires: str, version: str) -> bool`，判断给定版本（如 `"3.12.1"`）是否满足约束（如 `">=3.12"`），支持 `>=` / `>` / `==` / `<=` / `<` / `~=` / `*`。

## 延伸挑战

1. 在本机用 `uv` 与 `venv` 各建一个环境，分别 `pip install -e .` 后对比 `pip list` 与 `which python`，记录差异并解释 `uv` 快在哪里（可查 `uv pip --help`）。
2. 给本书仓库的 `pyproject.toml` 新增一个 `[project.scripts]` 入口 `m2t-hello = "m2t:__version__"`（或自定义函数），安装后验证 `m2t-hello` 是否可执行，思考「脚本入口 vs `python -m`」的适用场景。
3. 研究 `frontend/package.json` 的 `scripts` 与 `dependencies`，对比 Python 的 `project.scripts` 与 `project.dependencies`，用表格总结两套生态的对应关系。
4. 尝试用 `miniforge` 创建 Python 3.11 与 3.12 两个环境，分别安装本书项目，观察 `requires-python = ">=3.12"` 在 3.11 环境中的行为。

本章内容原创，概念对应 MeetingToText 的 pyproject.toml / README。

