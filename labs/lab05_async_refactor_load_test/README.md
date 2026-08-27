# 实验五 异步改造与接口压力测试

> 对应理论 [第6章 并发模型与性能工程](../../book/part2_backend_development/chapter06_concurrency_perf/index.md) · 4 学时 · 任务说明与验收标准同 `book/part5_lab_guide/experiment05_async_refactor_load_test/index.md`

## 实验目标

- 理解同步阻塞与异步非阻塞在事件循环中的差异，解释为何同步 DB 操作会卡住并发。
- 把同步查询或写入改造为异步形态，掌握 `async` / `await` 与 `asyncio.gather` 的协作。
- 用标准库并发脚本模拟压测，采集耗时与吞吐并对比验证优化是否有效。
- 按“度量、定位、优化、回归”闭环写出压测分析报告。

## 任务步骤

### 步骤 1 阅读理论

通读第6章 6.3 至 6.5 节，关注异步核心、FastAPI 异步陷阱与性能剖析方法。

### 步骤 2 读懂骨架

进入 `starter/`，运行 `python main.py` 观察同步与异步耗时对比，阅读 `bench.py` 的压测思路。

### 步骤 3 异步改造

以 `sync_fetch` 为起点实现 `async_fetch`，用 `asyncio.gather` 重叠等待，必要时用 `run_in_executor` 托底阻塞调用。

### 步骤 4 压测脚本

完善 `bench.py` 的并发与度量，支持 `--concurrency` 与请求数，输出总耗时、平均时延与吞吐。

### 步骤 5 分析报告

在固定环境下各执行 3 次取均值，撰写包含环境、方法、数据与结论的分析小节。

### 步骤 6 自检

运行 `python -m py_compile starter/main.py starter/bench.py`，确认 `python starter/main.py --help` 退出码为 0，`git status` 干净。

## 验收标准

- [ ] 两条路径可运行且契约一致，异步批量耗时接近单任务时延。
- [ ] 压测脚本输出耗时、时延与吞吐，对照数据可复现。
- [ ] 已撰写分析报告并能解释异步生效边界与陷阱修复。
- [ ] `python -m py_compile` 通过，帮助信息完整，仓库干净。

## 提交要求

提交 `starter/main.py`、`starter/bench.py`、`requirements.txt` 或 `pyproject.toml`、`README.md`，并附压测分析报告。以演示与讨论验收。

## 预估用时

4 学时。

## 起手代码

见 `starter/` 目录。先验证 `python starter/main.py` 能打印同步与异步耗时对比，再按实验文档扩展改造与压测。
