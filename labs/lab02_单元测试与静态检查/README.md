# 实验二 单元测试与静态检查实战

> 对应理论 [第2章 构筑代码质量的护城河](../../book/part1_软件工程筑基/chapter02_构筑代码质量的护城河/index.md) · 2 学时 · 任务说明与验收标准同 `book/part5_实验指导书/experiment02_单元测试与静态检查实战/index.md`

## 实验目标

- 按 AAA 模式与测试金字塔思想，为纯函数编写覆盖正常、边界与异常路径的 pytest 用例。
- 用 `fixture` 与 `mock` 隔离外部依赖，使测试 hermetic 且快速。
- 配置 `mypy` 严格模式与 `Ruff` 严苛规则，使类型与风格问题在本地即被检出。
- 度量并解读覆盖率，理解其价值与边界，体会 CI 门禁拦截低质量合并的思想。

## 任务步骤

### 步骤 1 环境准备

阅读第2章 2.1 至 2.5 节，进入 `starter/` 按 `README.md` 安装依赖。

### 步骤 2 读懂待测函数

打开 `starter/main.py`，运行 `python main.py` 观察输出，列出各函数正常、边界与非法输入。

### 步骤 3 编写 pytest 用例

在 `tests/test_text_utils.py` 中按 AAA 模式为每个函数写正常、边界与异常用例，用 `pytest.raises` 断言抛错。至少一个用例使用 `tmp_path` 或 `mock`。

### 步骤 4 mypy 严格检查

在 `pyproject.toml` 中启用 `strict = true`，运行 `mypy .` 至零错误。

### 步骤 5 Ruff 严苛检查

配置 `[tool.ruff]` 与 `select = ["E","F","W","I","B","UP","SIM"]`，运行 `ruff check .` 与 `ruff format --check .` 至通过。

### 步骤 6 覆盖率与门禁

运行 `pytest --cov=starter --cov-report=term-missing`，观察删用例后的变化。本地脚本按序执行 `mypy`、`ruff check`、`pytest`，任一失败即拦截。

## 验收标准

- [ ] `python starter/main.py` 可运行，待测函数签名完整。
- [ ] `tests/` 用例覆盖正常、边界与异常路径，`pytest -q` 全绿。
- [ ] 至少一个 `fixture` 或 `mock` 用例，测试可重复。
- [ ] `mypy .` 零错误，严格模式生效。
- [ ] `ruff check .` 与 `ruff format --check .` 通过。
- [ ] 覆盖率报告可生成，能指出未覆盖行。
- [ ] 本地门禁脚本能演示拦截流程。

## 提交要求

提交 `starter/main.py`、`pyproject.toml`、`tests/` 与 `README.md`，写清 `pytest`、`mypy`、`ruff` 与覆盖率命令。以演示与讨论验收。

## 预估用时

2 学时。

## 起手代码

见 `starter/` 目录。先运行 `python starter/main.py` 验证起点可执行，再按步骤扩展测试与检查配置。
