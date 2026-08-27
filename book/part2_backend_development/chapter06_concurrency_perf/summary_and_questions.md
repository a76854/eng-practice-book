---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **并发、并行、异步的边界**：并发是“交替做”的结构，并行是“同时做”的执行，异步是“不等结果先做别的事”的调用方式；阻塞/非阻塞描述等待时是否让出。I/O 密集适合用线程或协程重叠等待，CPU 密集需用进程或 C 扩展实现真并行。
- **GIL 的真相**：GIL 保护 Python 对象内存管理的正确性，同一时刻只允许一个线程执行 Python 字节码；I/O 等待与 C 扩展会释放 GIL，因此多线程对 I/O 密集有效、对纯 Python 的 CPU 密集受限，必要时用 `multiprocessing` 各持独立 GIL。
- **异步编程核心**：`asyncio` 以单线程事件循环协作调度，`async def` 定义协程，`await` 是让出点，`Task` 是排程包装，`Future` 是结果占位符；`gather` / `Queue` / `wait_for` 是常用并发原语，协作式调度的前提是“遇 `await` 才让出”。
- **FastAPI 异步陷阱**：`async def` 路由跑在事件循环中，`def` 路由跑在线程池；在 `async def` 中直接调用 `time.sleep`、同步文件 I/O 或 CPU 循环会阻塞整个循环、让并发退化为串行，修复是用 `run_in_executor` / `anyio.to_thread` 移出循环，或改回 `def` 路由。
- **性能剖析闭环**：先度量再优化——`cProfile` 定位热点函数，`timeit` 稳定对比微基准，行级剖析思路深入热点行，`EXPLAIN QUERY PLAN` 检查是否走索引；每次优化只改一处、用同一基准回归、以可回退的方式验证。

本章与第二篇前三章形成闭环：[第3章 后端职责与分层](../chapter03_backend_essence/index.md) 给出“请求如何穿过系统”，[第4章 HTTP 语义](../chapter04_http_restful/index.md) 约束“如何暴露契约”，[第5章 持久化](../chapter05_persistence_sql_orm/index.md) 解决“如何存得可靠”，本章则回答“如何跑得并发且快得可证明”——四章共同构成后端核心基石。

## 思考题

1. **并发模型选型**：MeetingToText 需批量处理 20 个音频的 `load_audio`（文件 I/O）与随后的文本正则清洗（CPU 密集）两阶段。若全用 `threading` 会怎样？若全用 `multiprocessing` 又会怎样？你会如何为两阶段分别选型并说明代价？
2. **GIL 边界辨析**：有人说“Python 多线程没用，应该全部用异步”。请结合 GIL 在 I/O 时释放与 `asyncio` 单线程协作的特性，辨析该说法的适用边界与反例。
3. **事件循环阻塞的定位**：线上 FastAPI 服务在高并发下 P99 延迟突增，怀疑某 `async def` 路由阻塞了事件循环。你会如何用日志、剖析或最小复现脚本定位是哪一行阻塞？定位后会选择哪种修复（线程池 / 改同步路由 / 异步客户端）并说明理由？
4. **剖析与优化的可验证性**：你用 `cProfile` 发现 `slow_path` 占 80% 时间，用 `timeit` 验证某优化使该函数快 30%，但端到端请求仅快 5%。请解释可能的原因（Amdahl 定律、非热点瓶颈、数据库侧等），并设计一个“度量—优化—回归”的验证步骤。
5. **数据库并发与性能的权衡**：`m2t/store.py` 的 `idx_tasks_status` 能加速按状态查询，但会拖慢写入。若任务表的读写比从 10:1 变为 1:10，你是否仍保留该索引？请结合 [第5章 索引代价](../chapter05_persistence_sql_orm/5.1_relational_db_principles.md) 说明判断依据，并思考如何用 `EXPLAIN QUERY PLAN` 验证。
6. **异步与同步的协作设计**：若 MeetingToText 的转写流水线中，ASR 调用是 I/O 密集而重采样是 CPU 密集，你会如何设计一个“`asyncio` 负责 I/O 重叠 + 进程池负责计算”的混合流水线？需要考虑任务切分、结果汇合与错误传播的哪些细节？
