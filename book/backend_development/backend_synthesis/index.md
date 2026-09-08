---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 综合实战

学完本节，你能回答：

- 一个搜索请求从进入到返回，依次穿过哪几层，每一层各自做什么？
- 搜索走外部 API、收藏走本地数据库，这两种数据来源为什么要分别抽象？
- 分层之后，Controller 如何把业务错误映射成正确的 HTTP 状态码？
- 为什么收藏要落库持久化，而不是只活在进程内存里？

> 一个搜索请求像一张快递单：从前台签收，交业务室核验，再分头去"外部搜索"与"本地仓库"两个地方取货，最后把回执寄回。每一站只干本分的活，单子才能在站点间顺畅流转，出了错也能一眼看出卡在哪一站。

前几章各自交付了一件工具：第 3 章给了分层组织与可替换依赖，第 4 章给了 HTTP 的契约与状态码，第 5 章给了持久化与参数化 SQL，第 6 章给了性能优化视角。本节用一个文档查询应用，把"外部搜索、HTTP、持久化"串成一条完整链路：看一个 `GET /api/search` 如何穿过框架调用搜索服务，一条数据如何存入数据库。

```{mermaid}
flowchart LR
    A["HTTP 请求<br/>POST /users/register"] --> C["路由层 Controller<br/>解析参数、映射状态码"]
    C --> S["服务层 Service<br/>校验、查重、密码哈希"]
    S --> R["存储层 Repository<br/>参数化写库"]
    R --> E["HTTP 响应<br/>201+搜索结果"]
```

## 定义数据模型与接口

分层的第一步是把边界画清楚。搜索返回的是 `Document`；外部搜索与本地收藏是两种不同的数据来源，各自抽象成接口：`DocumentRepository` 负责"搜索结果从哪来"，`FavoriteRepository` 负责"收藏存到哪里"。

```{code-cell} ipython3
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

@dataclass
class Document:
    id: str
    title: str
    source: str
    url: str
    content: str

class DocumentRepository(Protocol):
    def search(self, query: str) -> list[Document]: ...

class FavoriteRepository(Protocol):
    def add(self, doc_id: str) -> None: ...
    def remove(self, doc_id: str) -> None: ...
    def list_all(self) -> list[str]: ...
    def exists(self, doc_id: str) -> bool: ...

print("models ready:", Document.__name__)
```

模型与接口就位。两种数据来源各自一个抽象，这是本节的骨架：搜索与收藏可以独立替换、独立测试。

## Repository 层：数据源的抽象

这一层把"搜索"抽象成一次调用。基于 WebSearch 的 HTTP API 检索，把网页结果整理成 `Document`；未配置 key 时返回空。

```{code-cell} ipython3
import os
from tavily import TavilyClient

class WebSearchRepository:
    def __init__(self, api_key: str) -> None:
        self._client = TavilyClient(api_key=api_key) if api_key else None

    def search(self, query: str) -> list[Document]:
        if self._client is None:
            return []
        response = self._client.search(query, max_results=5)
        docs = []
        for r in response.get("results", []):
            docs.append(Document(
                id=r["url"], title=r["title"], source=urlparse(r["url"]).netloc,
                url=r["url"], content=r["content"],
            ))
        return docs

repo = WebSearchRepository(os.environ.get("WEBSEARCH_API_KEY", ""))
print("repository ready:", type(repo).__name__)
```

## FavoriteRepository 层：把收藏写进 SQLite

收藏不能只活在内存里，进程一退出就没了。这一层用标准库 `sqlite3` 实现持久化，沿用第 5 章的参数化占位符，`doc_id` 上挂 `PRIMARY KEY`，把"不重复收藏"从业务规则变成数据库门卫。

```{code-cell} ipython3
import sqlite3
import datetime

class SqliteFavoriteRepository:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS favorites ("
            " doc_id TEXT PRIMARY KEY,"
            " created_at TEXT NOT NULL"
            ")"
        )
        self._conn.commit()

    def add(self, doc_id: str) -> None:
        self._conn.execute(
            "INSERT INTO favorites (doc_id, created_at) VALUES (?, ?)",
            (doc_id, datetime.datetime.now().isoformat()),
        )
        self._conn.commit()

    def remove(self, doc_id: str) -> None:
        self._conn.execute("DELETE FROM favorites WHERE doc_id = ?", (doc_id,))
        self._conn.commit()

    def list_all(self) -> list[str]:
        rows = self._conn.execute("SELECT doc_id FROM favorites ORDER BY created_at").fetchall()
        return [r[0] for r in rows]

    def exists(self, doc_id: str) -> bool:
        return self._conn.execute("SELECT 1 FROM favorites WHERE doc_id = ?", (doc_id,)).fetchone() is not None

favorite_repo = SqliteFavoriteRepository()
print("favorite repo ready, empty:", favorite_repo.list_all())
assert favorite_repo.list_all() == []
```

收藏存储就绪，初始为空。`PRIMARY KEY` 保证同一文档不会收藏两次，这与第 5 章"约束是数据库门卫"一脉相承。

## Service 层：编排两种数据来源

这一层承载业务规则，不感知 HTTP。搜索时校验关键词、按 URL 去重；收藏时查重。它持有两个依赖——DocumentRepository 与 FavoriteRepository。

```{code-cell} ipython3
class SearchService:
    def __init__(self, repo: DocumentRepository, favorites: FavoriteRepository) -> None:
        self.repo = repo
        self.favorites = favorites

    def search(self, query: str) -> list[Document]:
        q = query.strip()
        if not q:
            return []
        docs = self.repo.search(q)
        seen: set[str] = set()
        unique: list[Document] = []
        for d in docs:
            if d.url not in seen:
                seen.add(d.url)
                unique.append(d)
        return unique

    def add_favorite(self, doc_id: str) -> None:
        if self.favorites.exists(doc_id):
            raise ValueError("已收藏")
        self.favorites.add(doc_id)

    def list_favorites(self) -> list[str]:
        return self.favorites.list_all()

service = SearchService(repo, favorite_repo)

assert service.search("  ") == []   # 空关键词拦截

service.add_favorite("https://docs.pydantic.dev/latest/concepts/models/")
print("favorites after add:", service.list_favorites())
assert len(service.list_favorites()) == 1

try:
    service.add_favorite("https://docs.pydantic.dev/latest/concepts/models/")
except ValueError as e:
    print("重复收藏被拦截:", e)

print("service ready")
```

Service 不 import HTTP 模块，只面对两个接口。搜索与收藏的业务规则都落在这里，Controller 与两个数据源各司其职。

## Controller 层：路由与状态码

最上面一层只做 HTTP 翻译。搜索成功回 200；收藏成功回 201、重复回 409。

```{code-cell} ipython3
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

class FavoriteIn(BaseModel):
    doc_id: str

class DocOut(BaseModel):
    id: str
    title: str
    source: str
    url: str
    content: str

app = FastAPI(title="Doc Search API")

@app.get("/api/search", response_model=list[DocOut])
def search(q: str = ""):
    docs = service.search(q)
    return [DocOut(id=d.id, title=d.title, source=d.source, url=d.url, content=d.content) for d in docs]

@app.post("/api/favorites", status_code=201)
def add_favorite(payload: FavoriteIn):
    try:
        service.add_favorite(payload.doc_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"doc_id": payload.doc_id, "favorited": True}

@app.get("/api/favorites")
def list_favorites():
    return service.list_favorites()

print("routes:", [r.path for r in app.routes if getattr(r, "path", "").startswith("/api")])
```

路由函数又薄又清晰：不碰数据库、不发外部请求，只负责把 HTTP 的进出翻译好。业务错误 `ValueError("已收藏")` 在这里被映射成 409。

## 一个请求的完整往返

最后用 TestClient 走一遍：搜索走 WebSearch（未配置 key 时返回空），收藏落进 SQLite。

```{code-cell} ipython3
client = TestClient(app)

r1 = client.get("/api/search", params={"q": "python pydantic"})
print("搜索:", r1.status_code, "返回", len(r1.json()), "条")
assert r1.status_code == 200

r2 = client.get("/api/search", params={"q": "  "})
print("空关键词:", r2.status_code, len(r2.json()))
assert r2.status_code == 200
assert r2.json() == []

r3 = client.post("/api/favorites", json={"doc_id": "https://docs.pydantic.dev/"})
print("收藏:", r3.status_code)
assert r3.status_code == 201

r4 = client.post("/api/favorites", json={"doc_id": "https://docs.pydantic.dev/"})
print("重复收藏:", r4.status_code, r4.json()["detail"])
assert r4.status_code == 409

r5 = client.get("/api/favorites")
print("收藏列表:", r5.json())
assert "https://docs.pydantic.dev/" in r5.json()

# 收藏确实写进了数据库，而不只是返回里出现
assert favorite_repo.exists("https://docs.pydantic.dev/")
print("收藏已持久化到 SQLite")
```

一个 `GET /api/search` 从 TestClient 发出，经路由层翻译、服务层编排、搜索返回结果；一条 `POST /api/favorites` 落进 SQLite，从数据库层也能查回。

## 朝花夕拾

| 章节 | 这一节用到了什么 |
|---|---|
| 第3章 分层 | Controller 薄、Service 厚、依赖抽象沿边界替换（DocumentRepository 与 FavoriteRepository）|
| 第4章 HTTP | GET 查询、POST 创建，状态码表达责任（200 / 201 / 409）|
| 第5章 持久化 | 参数化 SQL 防注入，`PRIMARY KEY` 约束在库层兜底收藏不重复 |

> 分层定寿命，契约定协作，持久化定记忆，三者合起来才是一条能交付的完整链路。
