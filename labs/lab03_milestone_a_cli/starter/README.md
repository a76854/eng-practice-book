# Lab03 starter 说明

本目录是实验三的起点骨架，对应 `book/lab_guide/cli.md`。

## 包含内容

- `main.py`：带 `argparse` 子命令的最小可运行 CLI，含 `transcribe` 与 `info` 两个子命令，能打印 `--help`。
- `pyproject.toml`：最小项目声明，保持与实验一和实验二一致的 PEP 621 风格。
- `requirements.txt`：空依赖声明，本实验仅用标准库即可完成。

核心设计是把业务与 IO 分开：`transcribe_file` 只做转写逻辑，`main()` 只做参数解析与文件读写，方便后续被 Web 层或其他调用方复用。

## 运行命令

```bash
# 查看顶层帮助（必须成功，退出码 0）
python main.py --help

# 查看子命令帮助
python main.py transcribe --help
python main.py info --help

# 转写示例（骨架为占位实现，会回显输入路径）
python main.py transcribe sample.wav --out result.txt
python main.py transcribe sample.wav --format srt --out result.srt

# 信息子命令
python main.py info

# 语法检查
python -m py_compile main.py
```

> 提示：示例中的 `sample.wav` 可换成任意已存在的音频路径。骨架的 `transcribe_file` 为占位逻辑，便于先跑通 CLI 再替换为真实实现。

## 替换占位实现

`transcribe_file` 是留给你的替换点。骨架只回显文件大小，实验里应把它改成真实调用，并保持两件事：

- 异常在函数内收口成可读文案，不把堆栈抛给终端；
- 返回值仍是字符串，调用方与格式化逻辑保持不变。

```python
def transcribe_file(audio_path, *, language=None) -> str:
    # 调用外部服务或本地推理，失败时抛出可读异常
    ...
```

不要引入 Web 框架，也不要让业务函数依赖 `argparse`。

## 环境说明

- 路径操作使用 `pathlib.Path`，示例中统一写 `/`。
- 子命令与选项解析依赖标准库 `argparse`，行为一致。

## 下一步

按实验文档步骤 3 至 5 补齐 `transcribe_file` 的真实逻辑，完善参数校验与错误提示，保持 CLI 层轻薄。
