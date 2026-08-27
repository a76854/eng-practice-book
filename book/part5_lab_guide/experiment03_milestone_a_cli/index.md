# 实验三 里程碑A CLI 音频转写工具

本实验对应理论 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第9章 与外部世界的集成](../../part4_advanced_engineering/chapter09_external_integration/index.md)。建议先通读第1章 1.4 节的自动化脚本与第9章 9.1 至 9.2 节的第三方服务集成与音频归一，再动手。你会在本实验中以纯命令行形态完成 MeetingToText 的首个可交付切片，体会不依赖 Web 框架时如何把业务逻辑与输入输出干净分开。

## 实验目标

- 能用 `argparse` 实现带子命令的命令行工具，使 `python main.py --help` 与 `python main.py transcribe --help` 均可打印清晰帮助。
- 能将转写业务逻辑抽成纯函数，输入为音频路径与选项，输出为文本或结构化结果，命令行层只做参数解析与文件读写。
- 能在不引入 Web 框架的前提下完成一次端到端转写闭环，并说清 CLI 形态相比 Web 形态的取舍与演进路径。
- 能只读复用教学包 `m2t` 中的 `m2t.audio` 与 `m2t.asr`，解释为何教学包设计为只读依赖而非可改实现。
- 能为 CLI 设计可验证的错误处理与退出码，使参数错误、文件不存在、格式不支持时给出可读提示而非堆栈。

## 任务步骤

### 步骤 1 阅读理论与现状

1. 阅读 [第1章 1.4 Python 自动化脚本](../../part1_software_engineering/chapter01_dev_meta_skills/1.4_python_automation_scripts.md) 中关于 `argparse`、`subprocess` 与脚本封装的讨论，理解为何超过 10 行的自动化一律用 Python 而非 Shell。
2. 阅读 [第9章 9.1 第三方服务集成模式](../../part4_advanced_engineering/chapter09_external_integration/9.1_third_party_service_integration.md) 与 [9.2 语音识别接入](../../part4_advanced_engineering/chapter09_external_integration/9.2_asr_integration.md)，留意音频格式归一、结果多形状归一与错误脱敏的思想。
3. 在书仓根目录尝试 `python -c "from m2t.audio import load_audio; print(load_audio.__doc__[:80])"`，确认只读导入可用，无需启动真实 ASR 服务。

> 跨平台提示：本实验所有路径操作使用 `pathlib.Path`，示例中统一写 `/`。虚拟环境激活区分 `source .venv/bin/activate`（macOS / Linux）与 `.venv\Scripts\activate`（Windows）。

### 步骤 2 读懂起手骨架

1. 打开 `labs/lab03_milestone_a_cli/starter/main.py`，运行 `python main.py --help` 与 `python main.py transcribe --help`，观察子命令、选项与帮助文本的组织方式。
2. 阅读 `starter/README.md` 中关于目录结构与运行命令的说明，明确骨架中哪些是 CLI 层，哪些是待你补齐的业务函数。
3. 尝试 `python main.py transcribe --help` 之外的错误调用，例如缺参数或传入不存在的路径，观察当前骨架的报错与退出码。

### 步骤 3 抽离转写核心逻辑

1. 设计一个纯函数 `transcribe_file(audio_path: str | Path, *, language: str | None = None) -> str`，职责是接收音频路径并返回转写文本，不负责参数解析与打印。
2. 在函数内部只读复用 `m2t.audio.load_audio` 与 `m2t.audio.resample_audio` 完成音频读取与归一，或在无音频文件时用可控的占位逻辑模拟结果，保持函数可被直接导入测试。
3. 函数应对文件不存在、格式不支持、采样率异常等情况抛可读异常，由调用方统一转成面向用户的错误信息与非零退出码，而不是让堆栈直接暴露给终端。

### 步骤 4 完善命令行界面

1. 以骨架中的 `argparse` 子命令为起点，完善 `transcribe` 子命令的选项：至少包含输入音频位置参数、输出路径 `--out`、输出格式 `--format`（如 `txt` / `srt`），并为每个选项提供 `help` 说明。
2. 为参数加入校验：输入路径不存在则报错，格式不在允许列表则提示支持的格式，必要时用 `parser.error` 统一退出语义。
3. 在 `main()` 中保持解耦：解析参数后只做两件事，调用业务函数，再把结果按选项写入文件或打印到标准输出，不在 `main()` 里混入转写算法本身。

### 步骤 5 本地验证与错误路径

1. 用一条真实或示例音频路径验证 `python main.py transcribe <audio> --out result.txt` 能生成输出，重复执行覆盖写与追加写符合预期。
2. 刻意传入不存在的音频路径与不支持的格式，确认提示信息可读且退出码非零，再传正确路径确认零退出码。
3. 在 Python 交互环境中验证可复用性：`from starter.main import transcribe_file` 应可导入并被直接调用，不依赖 `argparse`。

### 步骤 6 自检与清理

1. 运行 `python -m py_compile starter/main.py` 与 `python starter/main.py --help`，确认语法与帮助均正常。
2. 用 `git status` 确认无 `.venv`、`__pycache__`、`*.egg-info` 等不应提交的内容，提交信息能讲清 CLI 分层思路。
3. 准备课堂演示：能现场解释为何要把业务逻辑与 IO 分开，以及只读复用 `m2t` 相比直接拷贝代码的协作收益。

## 验收标准

逐条自查，全部勾选即视为完成：

- [ ] `python starter/main.py --help` 与 `python starter/main.py transcribe --help` 均退出码为 0，帮助信息包含子命令、选项与描述。
- [ ] 转写核心抽成独立函数，CLI 层只做参数解析与文件读写，函数可被 `import` 直接调用。
- [ ] 至少一个子命令支持输入音频、输出路径与格式选项，参数校验失败时给出可读提示且非零退出。
- [ ] 已只读复用 `m2t.audio` 或 `m2t.asr` 相关能力，未直接改动教学包源码，能解释只读边界。
- [ ] 对文件不存在与格式不支持等错误路径有覆盖，能演示其提示与退出码。
- [ ] `python -m py_compile starter/main.py` 通过，`git status` 干净，无生成物残留。
- [ ] 能口头说明 CLI 形态与后续 Web 形态的演进关系，以及业务与 IO 解耦的收益。

## 提交要求

- 提交包含 `starter/main.py`、`starter/requirements.txt` 或 `starter/pyproject.toml`、`starter/README.md` 与顶层 `README.md` 的目录。`README.md` 需写清安装、运行与验证命令。
- 不需要提交 `.venv`、`__pycache__`、生成的结果文件与任何自动生成产物。
- 以演示与讨论作为验收，能现场运行帮助与转写命令并解释分层设计。

## 预估用时

4 学时。

建议分配：步骤 1 至 2 约 50 分钟，步骤 3 至 4 约 100 分钟，步骤 5 至 6 约 90 分钟。剩余时间用于自检与课堂讨论。
