---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 并发模型与性能工程

> **本章学习目标**
> - 能够辨析并发、并行、异步、阻塞与非阻塞五概念，并在 I/O 密集与 CPU 密集场景下为线程、进程与协程做出选型
> - 能够解释 Python GIL 的作用边界与适用场景，并用 `threading` 与 `multiprocessing` 的对照实测说明何时该用进程
> - 能够用事件循环、Task、Future 与 `async`/`await` 写出可并发的 `asyncio` 程序，并规避事件循环阻塞等常见坑点
> - 能够识别 FastAPI 中“在异步路由中调用同步阻塞代码”拖垮事件循环的性能陷阱，并用线程池或同步路由予以修复
> - 能够用 `cProfile` / `timeit` 与数据库查询分析的思路定位热点，并给出可验证、可回退的优化路径

> **为什么需要掌握本章**
> 演示项目的真实链路充满并发：用户批量上传音频、服务端并行做重采样与分段、ASR 与 LLM 调用在 I/O 等待中可重叠、任务状态需在并发写入下保持一致。把并发当作“多开几个线程就行”，会在 GIL、事件循环阻塞与数据库锁上反复踩坑；把性能当作“感觉变快了”，则无法用数据证明优化是否有效。本章以 `m2t/audio.py` 的批量处理与 `m2t/asr.py` 的 I/O 等待为贯穿场景，把并发模型与性能剖析串成一条可验证的链路——让系统既“跑得并发”也“快得可证明”。

> **预计理论学时**：3学时

章内结构如下：

- [6.1 并发、并行与异步](6.1_concurrency_parallel_async.md) —— 并发/并行/异步/阻塞/非阻塞辨析：从“同时做”与“交替做”的本质差异切入，落到线程/进程/协程的选型
- [6.2 Python GIL](6.2_python_gil.md) —— GIL 是什么、保护什么、何时成为瓶颈：用线程 vs 进程的对照实测看清边界
- [6.3 异步编程核心](6.3_async_programming_core.md) —— 事件循环、Task、Future、`async`/`await`：`asyncio` 的协作式并发如何工作
- [6.4 FastAPI 异步陷阱](6.4_fastapi_async_pitfalls.md) —— 异步路由 vs 同步路由：为什么在 `async def` 中调用阻塞代码会拖垮整个服务
- [6.5 性能剖析方法论](6.5_performance_profiling.md) —— `cProfile`、`timeit`、行级剖析思路与数据库查询分析：先度量再优化