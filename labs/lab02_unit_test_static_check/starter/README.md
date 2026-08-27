# Lab02 starter 说明

本目录是实验二的起点骨架，对应 `book/part5_实验指导书/experiment02_单元测试与静态检查实战/index.md`。

## 包含内容

- `main.py`：待测函数 `format_duration`、`normalize_text`、`chunk_list`、`write_summary`，含 `main()` 演示入口。
- `pyproject.toml`：最小项目声明与 `[tool.mypy]`、`[tool.ruff]` 严苛配置起点。
- `requirements.txt`：可选依赖声明。

待测函数设计为纯函数与轻量 I/O，便于按 AAA 模式编写正常、边界与异常用例。

## 运行命令

```bash
# 演示待测函数
python main.py
python main.py --help

# 安装后运行 pytest（需自建 tests/ 目录）
pip install -e .
pip install pytest pytest-cov
pytest -q
pytest --cov=starter --cov-report=term-missing

# 静态检查
mypy .
ruff check .
ruff format --check .
```

## 测试骨架提示

在项目根新建 `tests/test_text_utils.py`，参考如下结构：

```python
import pathlib
import pytest
from starter.main import format_duration, normalize_text, chunk_list, write_summary

def test_format_duration_typical():
    assert format_duration(65) == "1:05"

def test_format_duration_boundary_zero():
    assert format_duration(0) == "0:00"

def test_format_duration_raises_on_negative():
    with pytest.raises(ValueError):
        format_duration(-1)

def test_write_summary_with_tmp_path(tmp_path: pathlib.Path):
    p = write_summary(tmp_path / "out.txt", ["a", "b"])
    assert p.read_text() == "a\nb\n"
```

更多用例按正常、边界、异常三类自行扩展，至少一个用例使用 `tmp_path` 或 `unittest.mock`。

## 跨平台说明

- 路径操作使用 `pathlib.Path`，示例中统一写 `/`。
- 虚拟环境激活：`source .venv/bin/activate`（macOS / Linux）与 `.venv\Scripts\activate`（Windows）。

## 下一步

按实验文档步骤 3 至 6 补齐测试、调严 `mypy` 与 `Ruff`、度量覆盖率并本地模拟门禁拦截。
