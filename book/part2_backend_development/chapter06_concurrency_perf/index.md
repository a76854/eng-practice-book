---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第6章 并发模型与性能工程

> **本章学习目标**
> - 能够辨析并发、并行、异步、阻塞与非阻塞五概念，并在 I/O 密集与 CPU 密集场景下为线程、进程与协程做出选型
> - 能够解释 Python GIL 的作用边界与适用场景，并用 `threading` 与 `multiprocessing` 的对照实测说明何时该用进程
> - 能够用事件循环、Task、Future 与 `async`/`await` 写出可并发的 `asyncio` 程序，并规避事件循环阻塞等常见坑点
> - 能够识别 FastAPI 中“在异步路由中调用同步阻塞代码”拖垮事件循环的性能陷阱，并用线程池或同步路由予以修复
> - 能够用 `cProfile` / `timeit` 与数据库查询分析的思路定位热点，并给出可验证、可回退的优化路径

> **为什么需要掌握本章**
> MeetingToText 的真实链路充满并发：用户批量上传音频、服务端并行做重采样与分段、ASR 与 LLM 调用在 I/O 等待中可重叠、任务状态需在并发写入下保持一致。把并发当作“多开几个线程就行”，会在 GIL、事件循环阻塞与数据库锁上反复踩坑；把性能当作“感觉变快了”，则无法用数据证明优化是否有效。本章以 `m2t/audio.py` 的批量处理与 `m2t/asr.py` 的 I/O 等待为贯穿场景，把并发模型与性能剖析串成一条可验证的链路——让系统既“跑得并发”也“快得可证明”。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清“为什么需要这个概念”，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 3、4、5 章相同，所有示例均在书仓根目录的 `.venv` 环境中用标准库本地验证，无需真实的 ASR 模型、LLM 网络调用或外部服务。

章内结构如下：

- [6.1 并发、并行与异步](6.1_concurrency_parallel_async.md) —— 并发/并行/异步/阻塞/非阻塞辨析：从“同时做”与“交替做”的本质差异切入，落到线程/进程/协程的选型
- [6.2 Python GIL 真相](6.2_python_gil.md) —— GIL 是什么、保护什么、何时成为瓶颈：用线程 vs 进程的对照实测看清边界
- [6.3 异步编程核心](6.3_async_programming_core.md) —— 事件循环、Task、Future、`async`/`await`：`asyncio` 的协作式并发如何工作
- [6.4 FastAPI 异步陷阱](6.4_fastapi_async_pitfalls.md) —— 异步路由 vs 同步路由：为什么在 `async def` 中调用阻塞代码会拖垮整个服务
- [6.5 性能剖析方法论](6.5_performance_profiling.md) —— `cProfile`、`timeit`、行级剖析思路与数据库查询分析：先度量再优化

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t` 教学包（见 [m2t 源码](../../../m2t/audio.py) 的精简实现），无需启动真实服务。

> **环境约定**：本书面向 Linux，本章命令均面向 Linux，路径与环境激活统一使用 `source .venv/bin/activate` 与 `/` 分隔符；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第5章 数据持久化](../chapter05_persistence_sql_orm/index.md)。

文件 `book/part2_backend_development/chapter06_concurrency_perf/demo_index.py`（验证本章环境与并发原语可用）：

```{code-cell} ipython3
# 文件 book/part2_backend_development/chapter06_concurrency_perf/demo_index.py
import sys, pathlib, asyncio, threading, concurrent.futures, cProfile, pstats, io

import m2t

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("threading:", threading.current_thread().name)
print("asyncio:", asyncio.__name__)
print("concurrent.futures:", concurrent.futures.ThreadPoolExecutor.__name__)
print("cProfile:", cProfile.__name__)
print("prefix:", pathlib.Path(sys.prefix).name)
# 最小可用性校验：线程与协程均可启动
def _noop():
    return 42

with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
    fut = ex.submit(_noop)
    print("thread pool result:", fut.result())

async def _hello():
    await asyncio.sleep(0)
    return "async ok"

print("asyncio result:", await _hello())
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# threading: MainThread
# asyncio: asyncio
# concurrent.futures: ThreadPoolExecutor
# cProfile: cProfile
# prefix: .venv 或系统前缀
# thread pool result: 42
# asyncio result: async ok
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行
.venv/bin/python -c "import asyncio, threading, cProfile; print('ch06 env ok')"
```
