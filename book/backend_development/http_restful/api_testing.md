---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 接口测试

学完本节，你能回答：

- 第 3、4 章 code-cell 里那些 `assert` 为什么只是"顺手跑"，还不算测试套件？
- 一个 pytest 测试文件长什么样？`def test_xxx` 与 `fixture` 各自承担什么职责？
- `dependency_overrides` 解决什么问题？它如何让测试不连真实数据库、不发真实外部请求？
- 测试之间为什么要隔离？替身之间互相污染会带来什么麻烦？

前面的每一节，code-cell 末尾都跟着几句 `assert`。它们证明了"此刻这条链路是通的"，却证明不了"下次改动后它还是通的"：改一行 Service、加一个字段，没人会回头重跑那些散在正文里的 cell，回归全靠自觉。这一节把"顺手跑"升级成"可回归的接口测试"。

> 第 3、4 章里那些断言，像工人每装完一个零件顺手拧一下螺栓，证明的是"刚才这一下没松"；测试套件像流水线上的一排自动检测仪，每次代码改动都把整条线重新过一遍，守住的是"以后每一批都不会松"。

第 2 章讲过 [pytest 与测试金字塔](../../software_engineering/code_quality/testing_coverage_and_ci.md)，第 3 章搭好了 [分层架构](fastapi_routing.md) 之外更早的 [DocumentRepository 抽象](../backend_essence/fastapi_and_layered_architecture.md)。这一节把两者接起来，讲接口测试的两件实事：怎么把断言组织成套件，怎么用依赖替换把搜索与数据库挡在测试之外。

## 从"顺手跑"到"可回归"

第 3、4 章的验证代码都长一个样：定义 app，`client = TestClient(app)`，然后一连串 `client.get(...)` 加 `assert`。它确实调用了真实路由、跑了真实校验，但有两个天生的缺陷：

一是**没人会重跑**。这些断言嵌在正文的演示流程里，你以后改代码，不会想着回头把第 3 章某个 cell 重新执行一遍。

二是**没法隔离**。搜索在生产环境里要调 WebSearch 外部 API、要等网络，收藏要连数据库。测试绝不能真的去调外部 API、真的留下脏数据。所以测试里要靠依赖替换，把外部服务挡在门外。

可回归的接口测试，本质是把这两点补上：把断言挪进 `tests/` 下的测试函数，让 CI 每次改动都自动重跑；用依赖替换搭一个假的运行环境，让测试不碰真实外部资源。

## 一个依赖可替换的最小应用

要让测试换得掉搜索，路由就不能把搜索仓库 new 死在函数里，而要经过 `Depends` 注入。下面这个最小应用和第 3 章的分层一脉相承：路由通过 `Depends(get_repo)` 拿仓库，生产环境注入 WebSearch 仓库，测试里用 `dependency_overrides` 换成返回固定结果的替身。

```{code-cell} ipython3
from typing import Protocol
from dataclasses import dataclass
from fastapi import FastAPI, Depends
from pydantic import BaseModel

@dataclass
class Document:
    id: str
    title: str
    source: str
    url: str
    content: str

class DocumentRepository(Protocol):
    def search(self, query: str) -> list[Document]: ...

# 关键：路由经 Depends 拿仓库，而不是模块级直接 new，所以测试才能换得掉
def get_repo() -> DocumentRepository:
    raise RuntimeError("生产环境注入 WebSearch 仓库，测试中必须用 dependency_overrides 替换")

class DocOut(BaseModel):
    id: str
    title: str
    source: str
    url: str
    content: str

app = FastAPI(title="Doc Search API")

@app.get("/api/search", response_model=list[DocOut])
def search(q: str, client: DocumentRepository = Depends(get_repo)):
    docs = client.search(q)
    return [DocOut(id=d.id, title=d.title, source=d.source, url=d.url, content=d.content) for d in docs]

print("app 已定义：路由经 Depends(get_repo) 拿仓库，测试中可替换")
```

观测要点：`get_repo` 里直接 `raise`，是因为生产环境绝不该在测试里被触发（那会调用外部搜索），若哪条测试忘了替换，立刻报错而不是悄悄发外部请求。

## 用依赖替换把外部搜索挡在测试之外

接下来把 `get_repo` 替换成一个返回固定结果的替身，再用 TestClient 走一遍断言。替身返回的是最小占位结果，它只为验证路由与断言的接线，搜索由第 3 章的 WebSearchRepository 负责。

```{code-cell} ipython3
from fastapi.testclient import TestClient

class FakeDocumentRepository:
    """测试替身：返回固定结果，不发真实网络请求。"""
    def search(self, query: str) -> list[Document]:
        return [
            Document(
                id="https://docs.pydantic.dev/latest/concepts/models/",
                title="BaseModel",
                source="docs.pydantic.dev",
                url="https://docs.pydantic.dev/latest/concepts/models/",
                content="模型是继承 BaseModel 的类。",
            )
        ]

app.dependency_overrides[get_repo] = lambda: FakeDocumentRepository()

client = TestClient(app)

r1 = client.get("/api/search", params={"q": "pydantic"})
print("search:", r1.status_code, [d["title"] for d in r1.json()])
assert r1.status_code == 200
assert len(r1.json()) == 1
assert r1.json()[0]["title"] == "BaseModel"
```

观测要点：`dependency_overrides` 一行把外部搜索换成返回固定结果的替身，三条断言跑通。测试里没有一次外部网络请求——替身是测试的临时脚手架，只活在测试里。

## 组织成 pytest 套件

上面这段还只是"在 notebook 里跑"。真正可回归的形态，是把每条断言写成一个 `test_xxx` 函数，把共享的 client 与替身放进 `fixture`，整件事落成 `tests/` 下的文件。上面 cell 里的 app 与依赖，在真实工程里会落到 `src/main.py`，测试文件 import 它：

```python
# tests/test_api.py —— 测试套件的落点，CI 每次改动都会重跑这个文件
import pytest
from fastapi.testclient import TestClient

from src.main import app, get_repo, Document


class FakeDocumentRepository:
    def search(self, query: str) -> list[Document]:
        return [Document(id="u", title="t", source="s", url="u", content="c")]


@pytest.fixture
def client():
    # 每个测试函数都换成独立的替身，测试之间互不污染
    app.dependency_overrides[get_repo] = lambda: FakeDocumentRepository()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_search_returns_results(client):
    r = client.get("/api/search", params={"q": "pydantic"})
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_empty_query_still_returns_ok(client):
    assert client.get("/api/search", params={"q": ""}).status_code in (200, 422)
```

对照着看职责分工：`fixture` 为每个测试函数准备一个独立的替身（测试之间互不污染），`test_xxx` 只负责断言一条明确的行为。测试结束 `clear` 掉依赖，下一个测试又拿到一个全新的替身。

```bash
# 改动代码后，用一条命令自动重跑整条防线
pytest tests/ -v
```

## 从替换到隔离：两条路

替身适合纯逻辑与服务层的快速验证，但要测"SQL 语句真的写进去了、真的读得回来"，就得连真数据库。这时隔离换一种玩法：每个测试用独立的临时数据库（SQLite 内存库或临时文件），或在每个测试后回滚事务，让测试的副作用不落地。异步接口的测试则用 pytest-asyncio 或 anyio 跑事件循环。这些用到时再查文档即可，原则只有一个：**测试不依赖任何真实且会被污染的外部资源。**

## 本节小结

- 接口测试的本质，是把散在演示里的断言，搬进 CI 每次都会重跑的测试文件里。
- 路由经 `Depends` 拿仓库才谈得上替换，`dependency_overrides` 一行把 WebSearch 换成测试替身。
- `fixture` 备替身、`test_xxx` 断言行为、`clear` 保证隔离，三者构成一个可回归的接口测试。
- 要碰真数据库时，用临时库或事务回滚隔离副作用，别让测试依赖会被污染的真实资源。

金句：顺手跑一遍证明的是此刻，测试套件守住的是每一次改动。
