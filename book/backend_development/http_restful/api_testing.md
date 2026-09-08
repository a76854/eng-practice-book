---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 接口测试

学完本节，你能回答：

- 第 3、4 章 code-cell 里那些 `assert` 为什么只是"顺手跑"，还不算测试套件？
- 一个 pytest 测试文件长什么样？`def test_xxx` 与 `fixture` 各自承担什么职责？
- `dependency_overrides` 解决什么问题？它如何让测试不连真实数据库、不发真实请求？
- 测试之间为什么要隔离？一张会被上一个测试污染的内存表会带来什么麻烦？

前面的每一节，code-cell 末尾都跟着几句 `assert`。它们证明了"此刻这条链路是通的"，却证明不了"下次改动后它还是通的"：改一行 Service、加一个字段，没人会回头重跑那些散在正文里的 cell，回归全靠自觉。这一节把"顺手跑"升级成"可回归的接口测试"。

> 第 3、4 章里那些断言，像工人每装完一个零件顺手拧一下螺栓，证明的是"刚才这一下没松"；测试套件像流水线上的一排自动检测仪，每次代码改动都把整条线重新过一遍，守住的是"以后每一批都不会松"。

第 2 章讲过 [pytest 与测试金字塔](../../software_engineering/code_quality/testing_coverage_and_ci.md)，第 3 章搭好了 [分层架构](../backend_essence/fastapi_and_layered_architecture.md)。这一节把两者接起来，讲接口测试的两件实事：怎么把断言组织成套件，怎么用依赖替换把真实数据库挡在测试之外。

## 从"顺手跑"到"可回归"

第 3、4 章的验证代码都长一个样：定义 app，`client = TestClient(app)`，然后一连串 `client.get(...)` 加 `assert`。它确实调用了真实路由、跑了真实校验，但有两个天生的缺陷：

一是**没人会重跑**。这些断言嵌在正文的演示流程里，你以后改代码，不会想着回头把第 3 章某个 cell 重新执行一遍。

二是**没法隔离**。真轮到连数据库的接口，这种"跑一遍"就要真连数据库、真的准备数据、真的留下脏数据，测完还得手动清理。

可回归的接口测试，本质是把这两点补上：把断言挪进 `tests/` 下的测试函数，让 CI 每次改动都自动重跑；用依赖替换搭一个假的运行环境，让测试不碰真实资源。

## 一个依赖可替换的最小应用

要让测试换得掉依赖，路由就不能把仓库写死成全局变量，而要经过 `Depends` 注入。下面这个最小应用和第 3 章的分层一脉相承：路由通过 `Depends(get_repo)` 拿仓库，`get_repo` 在正式环境注入真实数据库，测试里用 `dependency_overrides` 换成内存替身。

```{code-cell} ipython3
from typing import Protocol, Optional
from dataclasses import dataclass
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

@dataclass
class Task:
    id: str
    filename: str

class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[Task]: ...
    def create(self, task: Task) -> None: ...

class InMemoryTaskRepository:
    """内存替身：教学与测试用，正式环境换成连接数据库的实现。"""
    def __init__(self) -> None:
        self._store: dict[str, Task] = {}
    def get(self, task_id: str) -> Optional[Task]:
        return self._store.get(task_id)
    def create(self, task: Task) -> None:
        self._store[task.id] = task

class TaskIn(BaseModel):
    task_id: str
    filename: str

class TaskOut(BaseModel):
    id: str
    filename: str

# 关键：路由经 Depends 拿仓库，而不是模块级全局变量，所以测试才能换得掉
def get_repo() -> TaskRepository:
    raise RuntimeError("正式环境注入真实数据库，测试中必须用 dependency_overrides 替换")

app = FastAPI(title="Task API")

@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskIn, repo: TaskRepository = Depends(get_repo)):
    task = Task(id=payload.task_id, filename=payload.filename)
    repo.create(task)
    return TaskOut(id=task.id, filename=task.filename)

@app.get("/api/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: str, repo: TaskRepository = Depends(get_repo)):
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return TaskOut(id=task.id, filename=task.filename)

print("app 已定义：路由经 Depends(get_repo) 拿仓库，正式环境注入真实实现，测试中可替换")
```

观测要点：`get_repo` 里直接 `raise`，是因为正式环境绝不该在测试里被真实触发，若哪条测试忘了替换，立刻报错而不是悄悄连库。

## 用依赖替换把数据库挡在门外

接下来把 `get_repo` 替换成返回同一个内存仓库的工厂，再用 TestClient 走一遍断言。注意这个仓库得是单例：创建和读取要落在同一张表上，所以同一个测试里所有请求都得共享同一个实例。

```{code-cell} ipython3
from fastapi.testclient import TestClient

# 同一个测试里，所有请求共享同一个内存仓库，创建与读取才能落在同一张表上
test_repo = InMemoryTaskRepository()
app.dependency_overrides[get_repo] = lambda: test_repo

client = TestClient(app)

r1 = client.post("/api/tasks", json={"task_id": "t1", "filename": "demo.wav"})
print("create:", r1.status_code)
assert r1.status_code == 201

r2 = client.get("/api/tasks/t1")
print("get:", r2.status_code, r2.json())
assert r2.status_code == 200
assert r2.json()["filename"] == "demo.wav"

r3 = client.get("/api/tasks/missing")
print("missing:", r3.status_code)
assert r3.status_code == 404
```

观测要点：`dependency_overrides` 一行把真实依赖换成内存替身，创建与读取落在同一张表上，三条断言跑通。测试里看不到一句真实数据库的代码。

## 组织成 pytest 套件

上面这段还只是"在 notebook 里跑"。真正可回归的形态，是把每条断言写成一个 `test_xxx` 函数，把共享的 client 与替身放进 `fixture`，整件事落成 `tests/` 下的文件。上面两个 cell 里的 app 与依赖，在真实工程里会落到 `src/main.py`，测试文件 import 它：

```python
# tests/test_api.py —— 测试套件的落点，CI 每次改动都会重跑这个文件
import pytest
from fastapi.testclient import TestClient

from src.main import app, get_repo, InMemoryTaskRepository

@pytest.fixture
def client():
    # 每个测试函数新建一个内存仓库：测试之间互不污染，测试内部共享这一个实例
    repo = InMemoryTaskRepository()
    app.dependency_overrides[get_repo] = lambda: repo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_create_and_get(client):
    r1 = client.post("/api/tasks", json={"task_id": "t1", "filename": "demo.wav"})
    assert r1.status_code == 201
    r2 = client.get("/api/tasks/t1")
    assert r2.status_code == 200
    assert r2.json()["filename"] == "demo.wav"

def test_missing_returns_404(client):
    assert client.get("/api/tasks/nope").status_code == 404
```

对照着看职责分工：`fixture` 为每个测试函数新建一个仓库（同一测试内的请求共享它），`test_xxx` 只负责断言一条明确的行为。测试结束 `clear` 掉依赖，下一个测试又拿到一张全新的表，前一个测试写进去的数据不会漏进来。这就是隔离的意义。

```bash
# 改动代码后，用一条命令自动重跑整条防线
pytest tests/ -v
```

## 从内存到真实数据库：隔离的两条路

内存替身适合纯逻辑与服务层的快速验证，但要测"SQL 语句真的写进去了、真的读得回来"，就得连真数据库。这时隔离换一种玩法：每个测试用独立的临时数据库（SQLite 内存库或临时文件），或在每个测试后回滚事务，让测试的副作用不落地。异步接口的测试则用 pytest-asyncio 或 anyio 跑事件循环。这些用到时再查文档即可，原则只有一个：**测试不依赖任何真实且会被污染的外部资源。**

## 本节小结

- 接口测试的本质，是把散在演示里的断言，搬进 CI 每次都会重跑的测试文件里。
- 路由经 `Depends` 拿依赖才谈得上替换，`dependency_overrides` 一行把真实实现换成内存替身。
- `fixture` 备环境、`test_xxx` 断言行为、工厂函数保证隔离，三者构成一个可回归的接口测试。
- 要碰真数据库时，用临时库或事务回滚隔离副作用，别让测试依赖会被污染的真实资源。

金句：顺手跑一遍证明的是此刻，测试套件守住的是每一次改动。