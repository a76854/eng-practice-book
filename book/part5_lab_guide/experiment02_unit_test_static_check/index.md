# 实验二 单元测试与静态检查实战

本实验对应理论 [第2章 构筑代码质量的护城河](../../part1_software_engineering/chapter02_code_quality/index.md)。建议先通读该章的 2.1 至 2.5 节，再动手。你会在本实验中为给定的工具函数补齐 pytest 用例，配置 mypy 与 Ruff 至严苛级别，并体会 CI 质量门禁如何拦截低质量合并。

## 实验目标

- 能按 AAA 模式与测试金字塔思想，为纯函数编写覆盖正常、边界与异常路径的 pytest 用例。
- 能用 `fixture` 与 `unittest.mock` 隔离外部依赖，使测试 hermetic 且快速。
- 能配置 `mypy` 严格模式与 `Ruff` 规则集，使类型与风格问题在本地即被检出。
- 能配置覆盖率度量并解读报告，理解覆盖率的价值与边界。
- 能解释 CI 质量门禁的拦截逻辑，说明为何门禁应阻止低质量合并而非事后补救。

## 任务步骤

### 步骤 1 准备实验环境

1. 阅读 [第2章 2.1 类型系统与防御性编程](../../part1_software_engineering/chapter02_code_quality/2.1_type_system_defensive_programming.md) 至 [2.5 测试覆盖率与质量门禁](../../part1_software_engineering/chapter02_code_quality/2.5_test_coverage_quality_gate.md)，留意 `mypy` 严格选项与 `Ruff` 规则含义。
2. 进入 `labs/lab02_unit_test_static_check/starter`，按其 `README.md` 安装最小依赖（若使用 `.venv`，先 `python -m venv .venv` 并激活）。

> 跨平台提示：`python -m venv .venv` 与 `pip install` 在三平台一致，激活命令区分 `source .venv/bin/activate`（macOS / Linux）与 `.venv\Scripts\activate`（Windows）。

### 步骤 2 读懂待测函数

1. 打开 `starter/main.py`，阅读其中提供的待测函数（如 `format_duration`、`normalize_text`、`chunk_list`）的签名、类型标注与 docstring，明确入参与返回值的约束。
2. 手动运行 `python main.py` 观察示例输出，确认函数在正常输入下的行为。
3. 列出每个函数至少 3 类输入：正常值、边界值（空串、零、单元素、超长）与非法值（类型错误、负数、越界），为下一步设计用例做准备。

### 步骤 3 编写 pytest 用例

1. 在项目根新建 `tests/` 目录，创建 `tests/test_text_utils.py`（文件名可自定，保持 `test_` 前缀便于 pytest 发现）。
2. 按 AAA 模式（Arrange, Act, Assert）为每个待测函数编写用例：
   - 正常路径：典型输入的预期输出。
   - 边界条件：空输入、单元素、临界值。
   - 异常路径：非法输入应抛 `ValueError` 或 `TypeError`，用 `pytest.raises` 断言。
3. 至少为一个涉及外部依赖的场景编写 `fixture` 或 `mock` 示例，例如用 `tmp_path` 隔离文件写入，或用 `unittest.mock` 替身替代网络调用。
4. 执行 `pytest -q` 或 `python -m pytest -q`，确认新增用例全部通过。刻意制造一个失败用例，观察错误定位是否清晰。

### 步骤 4 配置 mypy 严格检查

1. 在 `pyproject.toml` 中加入 `[tool.mypy]` 配置，启用 `strict = true` 或逐项开启 `warn_return_any`、`no_implicit_optional`、`disallow_untyped_defs` 等。
2. 运行 `mypy starter` 或 `mypy .`，修复所有类型报错。重点关注：
   - 函数签名是否完整标注参数与返回值。
   - 是否用 `Optional` 或 `X | None` 显式表达可空。
   - 是否避免 `Any` 逃逸。
3. 记录一条 `mypy` 曾拦截的类型错误，课堂上能解释为何该错误在运行时难以发现。

### 步骤 5 配置 Ruff 至严苛级别

1. 在 `pyproject.toml` 中配置 `[tool.ruff]` 与 `[tool.ruff.lint]`，至少启用 `E`、`F`、`W`、`I`、`B`、`UP`、`SIM` 规则，设置 `target-version = "py312"` 与 `line-length = 100`。
2. 运行 `ruff check .`，按提示修复或用 `ruff check --fix .` 自动修复可修复项。不可自动修复的需手动调整。
3. 运行 `ruff format .` 或 `ruff format --check .` 验证格式一致。

### 步骤 6 覆盖率与门禁思想验证

1. 安装 `pytest-cov` 后执行 `pytest --cov=starter --cov-report=term-missing`，阅读终端报告中的行覆盖与缺失行号。
2. 刻意删除一个分支的用例，观察覆盖率下降与报告变化，体会“为数字而测试”与“为行为而测试”的差异。
3. 在本地模拟门禁：编写一个简单脚本或 `Makefile` 目标，按顺序执行 `mypy`、`ruff check`、`pytest`，任一失败即整体失败（`set -e` 或脚本返回值）。在课堂上演示一次“门禁拦截低质量合并”的流程。

## 验收标准

逐条自查，全部勾选即视为完成：

- [ ] 已阅读第2章相关小节，能口头解释测试金字塔、AAA 模式与覆盖率边界的含义。
- [ ] `python starter/main.py` 可运行且输出符合预期，待测函数签名与类型标注完整。
- [ ] `tests/` 下新增的 pytest 用例覆盖每个待测函数的正常、边界与异常路径，`pytest -q` 全部通过。
- [ ] 至少一个用例使用 `fixture`（如 `tmp_path`）或 `unittest.mock` 隔离外部依赖，测试 hermetic 且可重复。
- [ ] `pyproject.toml` 中 `[tool.mypy]` 达到严格级别，`mypy .` 或 `mypy starter` 零错误。
- [ ] `[tool.ruff]` 与 `[tool.ruff.lint]` 已配置严苛规则，`ruff check .` 零错误，`ruff format --check .` 通过。
- [ ] `pytest --cov` 报告可生成，能指出未覆盖行，且能演示删除用例后覆盖率变化。
- [ ] 本地门禁脚本或 `Makefile` 能按序执行 `mypy`、`ruff check`、`pytest`，任一失败即拦截，流程可在课堂演示。

## 提交要求

- 提交包含 `starter/main.py`、`pyproject.toml`、`tests/` 用例与 `README.md` 的仓库。`README.md` 需说明如何运行 `pytest`、`mypy`、`ruff` 与覆盖率命令。
- 不需要提交 `.venv`、`__pycache__`、`.mypy_cache`、`.ruff_cache`、`htmlcov` 等生成物。
- 以演示与讨论作为验收，能现场运行测试与静态检查并解释门禁设计取舍。

## 预估用时

2 学时。

建议分配：步骤 1 至 2 约 20 分钟，步骤 3 约 50 分钟，步骤 4 至 5 约 30 分钟，步骤 6 约 20 分钟。
