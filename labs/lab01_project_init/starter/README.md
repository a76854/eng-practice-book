# Lab01 starter 说明

本目录是实验一的起点骨架，对应 `book/part5_实验指导书/experiment01_工程初始化与自动化脚本/index.md`。

## 包含内容

- `main.py`：带 `argparse` 与 `subprocess` 的最小可运行入口，支持 `--help`、`--name`、`--check`、`--verbose`。
- `pyproject.toml`：符合 PEP 621 的最小项目声明，展示 `[build-system]` 与 `[project]` 的必要字段。
- `requirements.txt`：空依赖声明，本实验仅用标准库即可完成。

## 运行命令

```bash
# 查看帮助（必须成功，退出码 0）
python main.py --help

# 常规运行
python main.py --name World

# 触发 subprocess 检查
python main.py --check --verbose

# 可选：以可安装包形式验证 src 布局
pip install -e .
python -c "import demo_pkg; print(demo_pkg.__file__)"
```

## 跨平台说明

- 路径分隔符用 `pathlib` 自动适配，示例中统一写 `/`。
- 虚拟环境激活：`source .venv/bin/activate`（macOS / Linux）与 `.venv\Scripts\activate`（Windows）。
- `subprocess.run` 采用列表形式，未使用 `shell=True`，三平台行为一致。

## 下一步

按实验文档步骤 2 至 5 扩展此骨架，完成 `src` 布局、`pre-commit` 门禁与一键脚本的完整实现。
