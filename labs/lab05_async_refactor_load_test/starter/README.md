# Lab05 starter 说明

本目录是实验五的起点骨架，对应 `book/lab_guide/async_refactor_load_test/index.md`。

## 包含内容

- `main.py`：同步 vs 异步的最小可运行对比，同步用 `time.sleep` 模拟阻塞 I/O，异步用 `asyncio.sleep` 模拟非阻塞等待，打印总耗时与吞吐。
- `bench.py`：标准库压测辅助脚本，支持 `--mode`、`--requests`、`--concurrency`、`--delay`，输出总耗时、平均时延、P50 / P95 近似与吞吐，思路对齐 `ab` / `locust` 的核心度量。
- `requirements.txt`：空依赖声明，本实验仅用标准库即可完成。

骨架刻意保持“无第三方”，便于在任意 `.venv` 中直接对比。后续可把 `sync_fetch` / `async_fetch` 替换为真实的数据库或接口调用，压测脚本的并发与度量逻辑可复用。

## 运行命令

```bash
# 同步与异步耗时对比（必须成功，打印两组耗时）
python main.py
python main.py --tasks 8 --delay 0.04

# 查看帮助（必须成功，退出码 0）
python main.py --help

# 压测辅助脚本
python bench.py
python bench.py --mode sync --requests 20 --concurrency 5
python bench.py --mode async --requests 20 --concurrency 5 --delay 0.03
python bench.py --mode both --requests 20 --concurrency 10 --csv
python bench.py --help

# 语法检查
python -m py_compile main.py bench.py
```

## 压测思路提示

本实验不要求你安装 `ab` 或 `locust`，重点是体会压测的度量与对照：

```bash
# 同步串行：总耗时约 requests * delay
# 异步并发：总耗时约 ceil(requests / concurrency) * delay
# 吞吐随并发度先升后平，时延分布随并发度与资源竞争变化
```

可在分析报告中用表格记录两组对照的耗时与吞吐，并讨论“何时异步有效、何时需托底到线程池”。

## 环境说明

- `asyncio`、`time`、`argparse` 均为标准库，在 Linux 环境行为一致。
- 路径示例统一写 `/`，`pathlib.Path` 自动适配 `\`。

## 下一步

按实验文档步骤 3 至 5 把同步数据库或文件操作改造为异步，用 `bench.py` 做固定环境下的多次对照，并撰写包含环境、方法、数据与结论的分析报告。
