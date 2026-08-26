---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 周10 并发与异步

> 为什么要在此时学并发（concurrency）与异步（async）？前几周你已能启动 FastAPI 服务、持久化任务、调用 ASR——但 MeetingToText 的转写流水线（`backend/app/services/pipeline.py`）并不是“请求进来就同步算完再返回”，而是把 `run_pipeline(task_id)` 提交到 `ThreadPoolExecutor(max_workers=1)` 后台执行，前端通过轮询进度获得反馈；取消转写时也不是“强制杀线程”，而是 `Future.cancel()` + `Event` 协作检查。你若只会同步写法，就无法理解“单工人队列为何能排队、为何排队的能取消而运行中的不能、以及协作取消如何避免资源泄漏”。本章以 pipeline 的单工人 Future 注册与协作取消为锚，补全线程池、Future、锁与竞态、`asyncio` 原语三块拼图，并用可运行代码让你亲手验证“并行求和 vs 串行”“排队取消 vs 运行中取消”。

## 学习目标

完成本章后，你将能够：

1. 能解释 `ThreadPoolExecutor(max_workers=1)` 单工人队列的串行语义、`Future` 的状态机（pending/running/finished/cancelled）与 `cancel()/done()/cancelled()/result()` 的行为差异，并预测排队任务与运行中任务的取消结果。
2. 能编写 `ThreadPoolExecutor` 并发求和与 `threading.Lock` 保护的共享计数，解释无锁时 `读-改-写` 为何导致竞态（race condition）与结果丢失，并用 `join` 确定性等待。
3. 能用 `threading.Event` 实现协作取消（cooperative cancellation），在循环检查点 `is_set()` 提前 `break`，并对照 `pipeline.py` 的 `_cancelled: set[str]` + `_check_cancelled()` 说明“请求取消 ≠ 强制终止”。
4. 能编写 `asyncio.gather` 并发等待多个 `async def` 任务，解释 `await asyncio.sleep(0)` 的让出语义与 `gather` 保持输入顺序的保证，并对比线程并发与协程并发的适用场景。

## 先修要求

- 完成 [周5 测试的思维与工程](week05_测试的思维与工程.md)与 [周9 调试与性能剖析](week09_调试与性能剖析.md)（会在 `.venv` 中 `pytest`，并理解 `tempfile/join/Event` 的确定性等待）。
- 会读 MeetingToText `backend/app/services/pipeline.py` 的 `pipeline_executor / _pipeline_futures / submit_pipeline / cancel_pipeline / _check_cancelled`（只读参考，不需运行 ASR 模型）。
- Python 基础：函数、列表分块、`with` 上下文、`async def / await` 语法已在前章或官方文档中见过。

## 正文

### 10.1 并发、并行与 GIL：先分清再动手

- **并发（concurrency）**：逻辑上“同时进行”，通过交错执行让多任务在重叠时间段内推进；单核也能并发。
- **并行（parallelism）**：物理上“同时执行”，需多核真正并行。
- **Python GIL（Global Interpreter Lock）**：CPython 中同一时刻只有一个线程执行 Python 字节码，故 `ThreadPoolExecutor` 对 **CPU 密集**任务加速有限，但对 **I/O 密集**（网络、文件、等待 ASR 外部进程）仍有效——因为等待时会释放 GIL。

MeetingToText 选择 `max_workers=1` 恰恰**不为加速、而为串行化**：转写是重 I/O + 重模型推理，单工人保证同一时刻只跑一个 `run_pipeline`，既避免并发抢 GPU/内存，又让“排队”语义天然成立（第二个提交的任务在队列中等待，`Future.cancel()` 才能生效）。

### 10.2 ThreadPoolExecutor 与 Future：提交、注册与状态

`ThreadPoolExecutor` 是“线程池（thread pool）+ 任务队列”的封装；`Future` 是“未来结果的占位符（placeholder）”。

```python
from concurrent.futures import ThreadPoolExecutor, Future

with ThreadPoolExecutor(max_workers=1) as ex:
    fut: Future[int] = ex.submit(lambda: 1 + 1)
    print(fut.done(), fut.cancelled())  # 运行极快，通常已 done
    print(fut.result(timeout=2))        # 阻塞等待结果，超时抛异常
```

`pipeline.py` 的关键三行（只读对照）：

```python
pipeline_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
_pipeline_futures: dict[str, Future] = {}

def submit_pipeline(task_id: str) -> Future:
    fut = pipeline_executor.submit(run_pipeline, task_id)
    _pipeline_futures[task_id] = fut
    fut.add_done_callback(lambda _: _pipeline_futures.pop(task_id, None))
    return fut
```

- `max_workers=1`：单工人，第二个 `submit` 的任务必排队。
- `_pipeline_futures[task_id] = fut`：**注册（register）**，让 `cancel_pipeline` 能按 `task_id` 找到 `Future`。
- `add_done_callback`：完成时自动注销，避免字典泄漏；无论成功/失败/取消都会触发。

Future 状态机（记住这张表，后文实验直接考）：

| 状态 | `done()` | `cancelled()` | `cancel()` 返回 | `result()` |
|---|---|---|---|---|
| pending/queued（排队中） | `False` | `False` | `True`（取消成功） | 抛 `CancelledError` |
| running（已开始） | `False` | `False` | `False`（不可取消） | 阻塞至完成 |
| finished（已完成） | `True` | `False` | `False` | 返回值 |
| cancelled（已取消） | `True` | `True` | `True` | 抛 `CancelledError` |

#### 可执行示例 1：线程池求和 vs 串行（验证结果一致）

```{code-cell} ipython3
from concurrent.futures import ThreadPoolExecutor, Future

def parallel_sum(nums: list[int], max_workers: int = 4) -> int:
    if not nums:
        return 0
    n = max(1, max_workers)
    chunk_size = max(1, (len(nums) + n - 1) // n)
    chunks = [nums[i:i+chunk_size] for i in range(0, len(nums), chunk_size)]
    def _sum_chunk(c: list[int]) -> int:
        return sum(c)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures: list[Future[int]] = [ex.submit(_sum_chunk, c) for c in chunks]
        return sum(f.result() for f in futures)

nums = list(range(1, 101))
print("serial:", sum(nums))
print("parallel(4):", parallel_sum(nums, max_workers=4))
print("parallel(1):", parallel_sum(nums, max_workers=1))
assert parallel_sum(nums, 4) == sum(nums)
assert parallel_sum([], 2) == 0
print("—— 断言通过：分块并发求和结果恒等于串行 sum ——")
```

`max_workers` 只影响分块数与并行度，不影响结果正确性——这正是习题 `parallel_sum` 的契约。

### 10.3 Future 取消语义：排队的能取消，运行中的不能

`Future.cancel()` 的语义常被误解为“杀掉线程”。实际是：**仅当任务仍在队列未开始时返回 `True`，已开始运行则返回 `False`（协作取消见 10.4）**。

`pipeline.py` 的 `cancel_pipeline` 正是此语义的工程封装：

```python
def cancel_pipeline(task_id: str) -> bool:
    _cancelled.add(task_id)  # 协作取消标记（见 10.4）
    fut = _pipeline_futures.pop(task_id, None)
    if fut is not None and not fut.done():
        cancelled = fut.cancel()  # 排队→True，运行中→False
        if cancelled:
            logger.info(f"cancelled pipeline for task={task_id}")
        return cancelled
    return False
```

- 先 `_cancelled.add`：即使 `cancel()` 因已运行而失败，`run_pipeline` 内的检查点仍能通过 `_check_cancelled` 提前退出。
- `fut.cancel()` 的返回值即“是否在队列中被拦截”。

#### 可执行示例 2：排队取消成功 vs 运行中取消失败（确定性等待）

用 `Event` 制造“确定性的排队/运行中”，不用 `sleep` 猜时序（与习题一致）：

```{code-cell} ipython3
import threading
from concurrent.futures import ThreadPoolExecutor, Future

def demo_cancel_queued():
    started = threading.Event()
    blocker = threading.Event()
    def _blocking():
        started.set()
        blocker.wait(timeout=5)
        return "blocking_done"
    def _queued():
        return "queued_done"
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="demo-queued") as ex:
        f_blocking: Future[str] = ex.submit(_blocking)
        started.wait(timeout=2)  # 确保工人已取走首任务
        f_queued: Future[str] = ex.submit(_queued)
        cancelled = f_queued.cancel()
        blocker.set()
        f_blocking.result(timeout=2)
        return {"cancelled": cancelled, "done": f_queued.done(), "is_cancelled": f_queued.cancelled()}

def demo_cancel_running():
    started = threading.Event()
    blocker = threading.Event()
    def _running():
        started.set()
        blocker.wait(timeout=5)
        return 42
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="demo-running") as ex:
        fut: Future[int] = ex.submit(_running)
        started.wait(timeout=2)
        cancelled = fut.cancel()
        blocker.set()
        result = fut.result(timeout=2)
        return {"cancelled": cancelled, "was_cancelled": fut.cancelled(), "was_done": fut.done(), "result": result}

print("queued:", demo_cancel_queued())   # 期望 cancelled True
print("running:", demo_cancel_running()) # 期望 cancelled False, result 42
assert demo_cancel_queued()["cancelled"] is True
assert demo_cancel_running()["cancelled"] is False
print("—— 断言通过：排队可取消、运行中不可取消 ——")
```

这直接对应习题的 `future_cancel_queued` 与 `future_cancel_running`。

### 10.4 协作取消：检查点与 Event

线程无法被安全“杀死”，故取消必须是**协作式（cooperative）**：请求方置位标志，执行方在**检查点（checkpoint）**主动退出。

`pipeline.py` 的协作取消：

```python
_cancelled: set[str] = set()
def _check_cancelled(task_id: str) -> bool:
    if task_id in _cancelled:
        logger.info(f"pipeline for task={task_id} was cancelled, aborting")
        return True
    return False

def run_pipeline(task_id: str):
    if _check_cancelled(task_id):
        return
    # ... 中间每阶段前也可检查 ...
    if _check_cancelled(task_id):
        return
    # ...
    finally:
        _cleanup_cancelled(task_id)  # discard，避免泄漏
```

习题的 `cooperative_run` 把“按时间取消”改为“按步数取消”以保持 hermetic 确定性：

```{code-cell} ipython3
import threading

def cooperative_run(steps: int, cancel_after: int | None) -> list[int]:
    cancel_event = threading.Event()
    executed: list[int] = []
    for i in range(steps):
        if cancel_event.is_set():
            break
        executed.append(i)
        if cancel_after is not None and i == cancel_after:
            cancel_event.set()
    return executed

print(cooperative_run(5, None))  # [0,1,2,3,4]
print(cooperative_run(5, 2))     # [0,1,2]
print(cooperative_run(5, 0))     # [0]
assert cooperative_run(5, 2) == [0, 1, 2]
assert cooperative_run(5, None) == [0, 1, 2, 3, 4]
print("—— 协作取消：置位后下一轮检查点即 break ——")
```

跨线程变体 `cooperative_run_threaded` 用另一线程轮询 `len(executed)` 达到阈值后 `set()`，证明 `Event` 的跨线程可见性——但核心语义与单线程版一致。

### 10.5 asyncio 原语：单线程内的并发

`asyncio` 是**单线程协程（coroutine）并发**：`async def` 定义协程，`await` 让出执行权，`asyncio.gather` 并发等待多个协程。

```python
import asyncio

async def _double(n: int) -> int:
    await asyncio.sleep(0)  # 让出一次调度，允许其它协程交错
    return n * 2

async def gather_double(nums: list[int]) -> list[int]:
    results = await asyncio.gather(*(_double(n) for n in nums))
    return list(results)

# 在同步代码中驱动
asyncio.run(gather_double([3, 1, 4]))  # [6, 2, 8]，顺序与输入一致
```

关键保证：**`gather` 保持输入顺序**，无论内部完成先后，`results[i]` 对应 `nums[i]`。

```{code-cell} ipython3
import asyncio

async def gather_double(nums: list[int]) -> list[int]:
    async def _double(n: int) -> int:
        await asyncio.sleep(0)
        return n * 2
    return list(await asyncio.gather(*(_double(n) for n in nums)))

# Jupyter 已在运行事件循环，直接用顶层 await 驱动（asyncio.run 会因“事件循环已在运行”而报错）
cases = [[3, 1, 4, 1, 5], [], [7], [5, 3], [3, 5]]
for c in cases:
    print(c, "->", await gather_double(c))
assert await gather_double([3, 1, 4, 1, 5]) == [6, 2, 8, 2, 10]
assert await gather_double([5, 3]) == [10, 6]
print("—— gather 顺序保持：输入调换则输出相应调换 ——")
```

线程 vs 协程如何选：

| 场景 | 选谁 | 为什么 |
|---|---|---|
| 阻塞 I/O（文件/网络/子进程）且已同步 | `ThreadPoolExecutor` | 无需改调用方为 `async`，池即隔离 |
| 大量并发 I/O（数千连接） | `asyncio` | 协程切换成本远低于线程 |
| CPU 密集 | 均不合适，考虑 `ProcessPoolExecutor` | GIL 限制线程并行，协程更无法并行 |

### 10.6 竞态条件与锁

当多线程读写**共享可变状态**且操作非原子时，交错执行导致结果丢失——即**竞态条件（race condition）**。

习题 `run_counter` 刻意把 `holder[0] += 1` 拆为 `tmp = holder[0]; holder[0] = tmp + 1` 放大窗口：

```python
def _worker_no_lock():
    for _ in range(n_increments):
        tmp = holder[0]
        holder[0] = tmp + 1  # 另一线程可能在 tmp 读取后覆盖

def _worker_with_lock():
    for _ in range(n_increments):
        with lock:
            holder[0] += 1  # 原子化，恒等于期望
```

- `use_lock=True`：`n_threads * n_increments` 恒等于期望（确定性）。
- `use_lock=False`：结果 `<= 期望` 且 `>0`，可能丢失但不会崩溃；所有线程通过 `join` 确定性等待结束。

> 经验：锁（`threading.Lock`）是“互斥（mutual exclusion）+ 临界区”的最小原语；过度加锁会退化为串行、甚至死锁，故只保护最短临界区。本章习题用锁保护单行 `+=1`，真实 pipeline 用 `dict` + `Event` 的轻量协作而非全局锁。

### 改动并预测

以下 4 个实验均可在本章 `{code-cell}` 或本地 `.venv` 中复现，按“改什么 → 预测 → 解释”三段式。

#### 改动并预测 实验 1：`ThreadPoolExecutor(max_workers=4)` → `max_workers=1` → 预测 `parallel_sum` 结果与耗时

- **改什么**：把 `parallel_sum(nums, max_workers=4)` 改为 `parallel_sum(nums, max_workers=1)`，保持 `nums = list(range(1, 1001))` 与分块逻辑不变，重新运行并对比返回值与 wall-clock（可用 `time.perf_counter()` 包裹）。
- **预测**：返回值仍 `== sum(nums)` 且 `parallel_sum([], 2) == 0` 不变；耗时上 `max_workers=1` 退化为串行分块求和，不比直接 `sum` 更快（甚至略慢于 `max_workers=4` 的并行版，但差异在小数据上微弱）。
- **解释**：`max_workers` 只决定“同时取几个块并行算”，不改变“分块求和再汇总”的正确性；纯计算受 GIL 限制，线程数>1 也难显著加速，且 `max_workers=1` 时所有 `submit` 的任务在单工人队列中串行执行，等价于顺序 `sum` 各块。

#### 改动并预测 实验 2：排队任务的 `Future.cancel()` → 运行中任务的 `cancel()` → 预测返回值

- **改什么**：把示例 2 中的 `demo_cancel_queued`（`started.wait` 后排队任务 `cancel()`）改为 `demo_cancel_running`（`started.wait` 后对**已开始**的 `Future` 调用 `cancel()`），对比 `cancelled / done / cancelled()` 与 `result`。
- **预测**：排队版 `cancelled is True, done is True, is_cancelled is True`；运行中版 `cancelled is False, was_cancelled is False, was_done is True, result == 42`；后者的 `result()` 仍阻塞至 `blocker.set()` 后返回真实值而非抛 `CancelledError`。
- **解释**：`cancel()` 仅对“未开始（queued）”有效，已 `running` 的任务无法被池强制终止，必须靠协作取消（10.4）。`pipeline.py` 因此在 `cancel_pipeline` 中既尝试 `fut.cancel()`（拦截排队），又 `add` 到 `_cancelled` 集合（让运行中的 `run_pipeline` 在检查点退出）。

#### 改动并预测 实验 3：`asyncio.gather` 输入顺序调换 → 预测输出顺序

- **改什么**：把 `asyncio.run(gather_double([5, 3]))` 改为 `asyncio.run(gather_double([3, 5]))`，保持 `_double` 内 `await asyncio.sleep(0)` 不变，观察两次输出。
- **预测**：`[5, 3] -> [10, 6]`，`[3, 5] -> [6, 10]`；输出顺序始终与输入顺序一致，不因协程内部让出顺序而乱序；空列表 `[] -> []` 保持空。
- **解释**：`gather` 的契约是“按传入顺序收集结果”，与完成先后无关；`await sleep(0)` 仅让出调度以允许交错，不改变结果容器的索引对应。若需“谁先完成先取谁”，应改用 `asyncio.as_completed`，但本章习题锁定 `gather` 的顺序语义。

#### 改动并预测 实验 4：`run_counter(use_lock=True)` → `use_lock=False` → 预测结果上界

- **改什么**：把 `run_counter(4, 1000, use_lock=True)` 改为 `run_counter(4, 1000, use_lock=False)`，保持 `n_threads * n_increments = 4000` 不变，多次运行取最大值观察。
- **预测**：`use_lock=True` 恒 `== 4000`；`use_lock=False` 时结果 `>0 且 <= 4000`，通常 `<4000`（因 `tmp=holder[0]; holder[0]=tmp+1` 非原子，交错导致覆盖丢失），但不断言具体丢失数以保持确定性不 flaky。
- **解释**：无锁的 `读-改-写` 非原子，两个线程同读 `tmp=10` 后各写 `11`，一次增量丢失；`Lock` 将 `holder[0]+=1` 变为互斥临界区，消除交错。`join` 保证主线程在所有 `Thread` 结束后再读 `holder[0]`，故观察到的 `<= 期望` 是竞态的确定性上界。

## 习题

> 参考答案与测试在 `answers/week10/`，运行 `.venv/bin/pytest answers/week10/ -q` 验证。题目均为 hermetic（不依赖网络/外部服务/真实模型），并发断言均用 `join / Future.result / Event` 确定性等待，不用 `sleep` 猜时序。以下题干与 `answers/week10/solution.py` 的函数签名一一对应，改签名即测试失败。

1. **线程池分块求和**：实现 `parallel_sum(nums: list[int], max_workers: int = 4) -> int`，将 `nums` 均分分块后用 `ThreadPoolExecutor(max_workers=max_workers)` 并发求各块之和，再汇总。要求 `parallel_sum([], max_workers=2) == 0`；`parallel_sum([42], max_workers=4) == 42`；`parallel_sum(list(range(1,101)), max_workers=4) == sum(range(1,101))` 且 `max_workers=1` 时亦相等。

2. **加锁计数与竞态上界**：实现 `run_counter(n_threads: int, n_increments: int, use_lock: bool) -> int`，启动 `n_threads` 个线程各执行 `n_increments` 次 `+=1`。`use_lock=True` 时用 `threading.Lock` 保护，恒 `== n_threads * n_increments`；`use_lock=False` 时拆为 `tmp = holder[0]; holder[0] = tmp + 1` 且不用锁，返回 `>0 且 <= 期望`；所有线程通过 `join` 确定性等待。

3. **Future 排队取消（可取消）**：实现 `future_cancel_queued() -> dict`，用 `ThreadPoolExecutor(max_workers=1)` 先提交阻塞任务（`Event` 确保已开始），再提交排队任务并 `cancel()`。返回 `{"cancelled": bool, "done": bool, "is_cancelled": bool}`，期望 `cancelled is True, done is True, is_cancelled is True`。

4. **Future 运行中不可取消**：实现 `future_cancel_running() -> dict`，用 `max_workers=1` 提交已开始任务（`Event` 确保 running），立即 `cancel()`。返回 `{"cancelled": bool, "was_cancelled": bool, "was_done": bool, "result": int}`，期望 `cancelled is False, was_cancelled is False, was_done is True, result == 42`；`result` 通过 `Future.result(timeout=2)` 确定性获取。

5. **asyncio.gather 顺序保持**：实现 `async def gather_double(nums: list[int]) -> list[int]`，对每个 `n` 执行 `await asyncio.sleep(0)` 后返回 `n*2`，用 `asyncio.gather` 并发等待并保持输入顺序。要求 `asyncio.run(gather_double([3,1,4,1,5])) == [6,2,8,2,10]`；`gather_double([]) == []`；`gather_double([5,3]) == [10,6]` 且调换输入顺序输出相应调换。

6. **协作取消（检查点）**：实现 `cooperative_run(steps: int, cancel_after: int | None) -> list[int]`，循环 `steps` 次、每轮先检查 `Event.is_set()` 再 `executed.append(i)`，当 `cancel_after` 非 `None` 且 `i == cancel_after` 时 `set()`。要求 `cooperative_run(5, None) == [0,1,2,3,4]`；`cooperative_run(5, 2) == [0,1,2]`；`cooperative_run(5, 0) == [0]`；`cooperative_run(3, 10) == [0,1,2]`（超出范围等价不取消）。

## 延伸挑战

1. **单工人队列的背压**：在 `parallel_sum` 基础上，把 `max_workers` 固定为 `1`，提交 100 个 `sleep(0.01)` 任务，用 `Future.add_done_callback` 统计完成顺序，验证单工人下完成顺序恒等于提交顺序；再改为 `max_workers=4` 观察完成顺序不再保证，思考 pipeline 为何选 `1` 而非 `4`。
2. **协作取消的真实线程版**：基于 `cooperative_run_threaded(steps, cancel_after)`（`answers/week10/solution.py` 已提供跨线程变体），让 `canceller` 线程轮询 `len(executed)` 达到阈值后 `Event.set()`，对比单线程自置位版的时序差异，思考“轮询间隔 0.001s 对取消延迟的影响”。
3. **asyncio 取消与超时**：用 `asyncio.wait_for(gather_double([1,2,3]), timeout=0.001)` 包裹本章 `gather_double`，捕获 `TimeoutError` 后改用 `asyncio.wait` 的 `FIRST_COMPLETED` 模式，体会协程取消（`task.cancel()`）与线程 `Future.cancel()` 在语义上的异同。

> 本章内容原创，概念对应 MeetingToText 的 `backend/app/services/pipeline.py`（`ThreadPoolExecutor(max_workers=1)` + `Future` 注册与 `add_done_callback` + `_cancelled` 协作取消），`asyncio` 与竞态示例为教学原创，表述与代码均为原创。
