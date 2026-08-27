# 实验三 里程碑A CLI 音频转写工具

> 对应理论 [第1章 开发者的元技能](../../book/part1_软件工程筑基/chapter01_开发者的元技能/index.md) 与 [第9章 与外部世界的集成](../../book/part4_现代工程进阶与交付/chapter09_与外部世界的集成/index.md) · 4 学时 · 任务说明与验收标准同 `book/part5_实验指导书/experiment03_里程碑A_CLI转写工具/index.md`

## 实验目标

- 能用 `argparse` 实现带子命令的 CLI，体会业务逻辑与输入输出解耦。
- 能将转写核心抽成纯函数，命令行层只做参数解析与文件读写，函数可被直接 `import` 复用。
- 能只读复用教学包 `m2t` 中的 `m2t.audio` 与 `m2t.asr`，理解只读依赖的协作边界。
- 能设计可验证的错误处理与退出码，使参数错误与文件异常时给出可读提示。
- 能在不依赖 Web 框架的前提下完成一次端到端转写闭环，并说清 CLI 与 Web 形态的取舍。

## 任务步骤

### 步骤 1 阅读理论

通读第1章 1.4 节与第9章 9.1 至 9.2 节，理解 `argparse` 封装与音频归一思想。

### 步骤 2 读懂骨架

进入 `starter/`，运行 `python main.py --help` 与 `python main.py transcribe --help`，观察子命令与选项的组织。

### 步骤 3 抽离转写函数

设计 `transcribe_file(audio_path, *, language=None) -> str` 纯函数，内部只读复用 `m2t.audio` 能力，保持可被 `import` 测试。

### 步骤 4 完善 CLI

补齐 `transcribe` 子命令的输入、输出与格式选项，加入参数校验，错误时给出可读提示与非零退出码。

### 步骤 5 本地验证

用示例音频验证 `python main.py transcribe <audio> --out result.txt` 能生成输出，并覆盖错误路径。

### 步骤 6 自检

运行 `python -m py_compile starter/main.py`，确认 `git status` 干净，准备演示分层思路。

## 验收标准

- [ ] `python starter/main.py --help` 退出码为 0，帮助信息完整。
- [ ] `python starter/main.py transcribe --help` 退出码为 0，子命令帮助包含输入、输出与格式说明。
- [ ] 转写核心为独立函数，CLI 层只做解析与读写，可 `import` 复用。
- [ ] 已只读复用 `m2t.audio` 或 `m2t.asr`，未改动教学包源码。
- [ ] 文件不存在与格式不支持等错误路径有可读提示且非零退出。
- [ ] `python -m py_compile starter/main.py` 通过，仓库干净。

## 提交要求

提交 `starter/main.py`、`pyproject.toml` 或 `requirements.txt`、`starter/README.md` 与顶层 `README.md`，写清运行与验证命令。以演示与讨论验收。

## 预估用时

4 学时。

## 起手代码

见 `starter/` 目录。先运行 `python starter/main.py --help` 验证起点可执行，再按实验文档步骤扩展转写逻辑与 CLI 选项。
