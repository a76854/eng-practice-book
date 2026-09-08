---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# FastAPI 路由

学完本节，你能回答：

- 上一节的方法、状态码、资源三条准则，在 FastAPI 里分别由什么承载？
- 路径参数、查询参数、请求体三者在 HTTP 语义上的分工是什么？
- FastAPI 如何用类型标注自动完成校验，让校验失败统一以 422 暴露？
- Depends 依赖注入如何让分页与参数校验可复用？

> FastAPI 是一台把 HTTP 信封格式"印"进代码里的机器。你声明类型与约束，它自动完成校验、生成文档、返回正确的状态码，替你把上一节的那些规范扛在肩上。

上一节讲了三条准则：方法是动词，状态码是责任归属，资源是名词。这一节看它们在 FastAPI 里怎么落地。FastAPI 的做法是用 Python 类型标注声明契约，框架在边界自动校验、自动给状态码，让你专注于写清楚"这个接口要什么、回什么"。

## 三条准则在 FastAPI 里的落点

| 上一节的准则 | FastAPI 里的落点 | 例子 |
|---|---|---|
| 方法（动词） | 路由装饰器 | `@app.get` / `@app.post` / `@app.delete` |
| 状态码 | status_code 参数 | 收藏用 201，取消收藏用 204 |
| 资源（名词） | 路径结构 | /docs 表示文档集合，/docs/{doc_id} 表示单个文档 |

FastAPI 的路由装饰器天然把 HTTP 方法映射成 Python 函数，路径里写资源、方法上写动作、status_code 写责任归属，三条准则一次到位。

## 三类参数的分工

把 HTTP 请求比作一份快递单，三类参数各有分工：

| 参数类型 | HTTP 位置 | 语义 | 用法 |
|---|---|---|---|
| 路径参数 | URL 路径，如 /docs/{doc_id} | 资源的身份，必填且唯一 | 定位要操作的资源 |
| 查询参数 | URL 问号后，如 ?q=pydantic | 资源的搜索、筛选、分页 | 修饰集合 |
| 请求体参数 | Body | 创建或更新的完整载荷 | 承载业务数据 |

分工混了契约就模糊：把搜索关键词塞进 Body 无法被缓存与收藏，把文档 ID 放进 Query 则丢了可寻址性。FastAPI 用函数签名声明这三类参数：路径参数从路径提取，查询参数从问号后提取，请求体由 Pydantic 模型承载。

## 方法与状态码落地

下面这段代码用内存集合模拟收藏，走完"收藏、查收藏、取消收藏"的链路，每个环节都由 HTTP 方法与状态码表达语义。

```{code-cell} ipython3
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

class FavoriteIn(BaseModel):
    doc_id: str

favorites: set[str] = set()

app = FastAPI(title="Doc Search API")

@app.get("/api/favorites/{doc_id}")
def get_favorite(doc_id: str):
    if doc_id not in favorites:
        raise HTTPException(status_code=404, detail="not favorited")
    return {"doc_id": doc_id, "favorited": True}

@app.post("/api/favorites", status_code=status.HTTP_201_CREATED)
def add_favorite(payload: FavoriteIn):
    if payload.doc_id in favorites:
        raise HTTPException(status_code=409, detail=f"{payload.doc_id} already favorited")
    favorites.add(payload.doc_id)
    return {"doc_id": payload.doc_id, "favorited": True}

@app.delete("/api/favorites/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(doc_id: str):
    favorites.discard(doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

client = TestClient(app)

r1 = client.post("/api/favorites", json={"doc_id": "d01"})
print("POST favorite:", r1.status_code)
assert r1.status_code == 201

r2 = client.post("/api/favorites", json={"doc_id": "d01"})
print("POST duplicate:", r2.status_code)
assert r2.status_code == 409

r3 = client.get("/api/favorites/d01")
print("GET favorited:", r3.status_code)
assert r3.status_code == 200

r4 = client.delete("/api/favorites/d01")
r5 = client.delete("/api/favorites/d01")
print("DELETE twice:", r4.status_code, r5.status_code)
assert r4.status_code == 204
assert r5.status_code == 204

r6 = client.get("/api/favorites/d01")
print("GET after delete:", r6.status_code)
assert r6.status_code == 404
```

观测要点：收藏返回 201，重复收藏返回 409 而非覆盖，DELETE 连续执行两次结果一致，查询一个没被收藏的文档返回 404。上一节的"方法、状态码、幂等"在这里变成了一段可直接运行、可直接断言的代码。这一应用里没有"改资源"的需求，所以用不上 PUT（整体替换）和 PATCH（局部更新），这两个方法在需要改资源时再出现。

## 三类参数与校验：声明约束而非手写判断

第二段代码演示路径参数、查询参数、请求体三类参数如何分工，以及 Pydantic 如何在请求进入业务之前就拦住非法输入。搜索在生产环境里由 WebSearch 返回结果，未配置 key 时返回空列表，不妨碍观察校验行为。

```{code-cell} ipython3
import os
from typing import Annotated
from fastapi import FastAPI, Query, Path, Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from tavily import TavilyClient

class FavoriteIn(BaseModel):
    doc_id: str = Field(min_length=1, max_length=64, description="文档 ID")

class Page(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

def paginate(
    limit: Annotated[int, Query(ge=1, le=100, description="每页数量")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量")] = 0,
) -> Page:
    return Page(limit=limit, offset=offset)

_websearch = TavilyClient(api_key=os.environ["WEBSEARCH_API_KEY"]) if os.environ.get("WEBSEARCH_API_KEY") else None

app = FastAPI(title="Doc Search API")

@app.get("/api/search")
def search(
    q: Annotated[str, Query(min_length=1, description="搜索关键词")],
    p: Annotated[Page, Depends(paginate)],
):
    if _websearch is None:
        return []
    items = _websearch.search(q, max_results=10).get("results", [])
    return items[p.offset : p.offset + p.limit]

@app.get("/api/favorites/{doc_id}")
def get_favorite(doc_id: Annotated[str, Path(min_length=1, description="文档 ID")]):
    return {"doc_id": doc_id}

@app.post("/api/favorites", status_code=201)
def add_favorite(payload: FavoriteIn):
    return {"doc_id": payload.doc_id, "favorited": True}

client = TestClient(app)

r1 = client.get("/api/search", params={"q": ""})
print("empty q:", r1.status_code)
assert r1.status_code == 422

r2 = client.get("/api/search", params={"q": "pydantic", "limit": 999})
print("limit overflow:", r2.status_code)
assert r2.status_code == 422

r3 = client.get("/api/search", params={"q": "pydantic"})
print("search pydantic:", r3.status_code, "返回", len(r3.json()), "条")
assert r3.status_code == 200

r4 = client.get("/api/favorites/d01")
print("get favorite d01:", r4.status_code, r4.json()["doc_id"])
assert r4.status_code == 200

r5 = client.post("/api/favorites", json={"doc_id": ""})
print("empty doc_id:", r5.status_code)
assert r5.status_code == 422

print("params & validation passed")
```

观测要点：路径参数来自 URL，查询参数来自问号后，请求体由 Pydantic 承载。空关键词、分页超限、空文档 ID 都在进入业务之前被 422 拦截，路由代码里没有一句手写的 if 判断。

## 本节小结

- 方法对应装饰器、状态码对应 status_code、资源对应路径，上一节的三条准则在 FastAPI 里各有明确落点。
- 路径参数定位资源、查询参数修饰集合、请求体承载载荷，三者分工写在函数签名里。
- 类型标注加 Field 约束让校验在边界自动发生，以 422 暴露，路由里不写手工判断。
- Depends 让分页等可复用逻辑从路由中抽离，保持路由薄而可测。

> 声明契约，而不是手写防线，框架自会在边界替你站岗。
