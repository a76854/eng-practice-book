---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# FastAPI 与分层架构

学完本节，你能回答：

- 为什么在 AI 时代，后端的主流选择是 Python？
- 为什么在 Python 生态里，FastAPI 是 I/O 密集后端的合适选择？
- 选完框架之后，代码应该如何组织，而不是把逻辑塞进路由函数一坨？
- Controller、Service、Repository 三层各自守什么边界，如何做到单向依赖？

> 建一条产线，要过三关：先选原料，再选机床，最后排工位。原料选错，后面步步受限；机床选错，手艺施展不开；工位排乱，再好的机器也转不动。

上一节我们得到了一个原则：选型是约束求解，而非偏好。本节把这个原则落到一个具体的选择上，依次回答三个连在一起的问题：用什么语言写、用哪个框架搭、代码如何组织。语言决定生态与人才，框架决定日常开发的手感与契约，组织决定代码能走多远。

## AI 时代的通用语言

在讨论框架之前，先回答一个更上层的问题，为什么后端要用 Python 来写。AI 重新塑造了软件开发的形态。过去开发者逐行实现逻辑，如今大量能力来自调用模型与处理数据，工作重心从"亲手写出每一行规则"转向"编排与调用智能"。

这种形态下，三门语言站在了舞台中央，各自占据分工的一环：

| 语言 | 分工 | 典型阵地 |
|---|---|---|
| Python | 智能与数据层，训练模型、处理数据、快速搭服务 | 大模型应用后端、数据科学、教学 |
| TypeScript | 界面与全栈层，浏览器与 Node 同构 | 前端、前后端同构应用 |
| Rust | 性能与系统层，推理引擎与底层组件 | AI 框架底层、高性能中间件 |

三门语言不是竞争，而是分工：Python 在上层编排智能，TypeScript 在界面层呈现，Rust 在底层压榨性能。

Python 能占据智能与数据这一环，靠的是几项叠加出来的优势：

**一是生态几乎绑定 AI 与数据。** PyTorch、TensorFlow、NumPy、Pandas、scikit-learn 等主流库让“训练模型、处理数据、搭建服务”能在同一门语言里闭环，省去了在多种语言之间搬运数据的成本。对 AI 应用来说，这几乎是一票否决级的便利。

**二是快速验证。** 动态类型与脚本化特性让原型迭代飞快，AI 应用恰恰是需要频繁试错、快速验证想法的领域，用 Python 能更快跑通一个念头，把脑中的假设迅速转化为可运行的代码。

::::{tab-set}

:::{tab-item} C++
```cpp
#include <iostream>
int main() {
    std::cout << "Hello world!" << std::endl;
    return 0;
}
```
:::

:::{tab-item} java
```java
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello world!");
    }
}
```
:::

:::{tab-item} python
```python
print("Hello world!")
```
:::

:::{tab-item} javascript
```javascript
console.log("Hello world!");
```
:::

:::{tab-item} typescript
```typescript
const greet: string = "Hello world!";
console.log(greet);
```
:::

:::{tab-item} rust
```rust
fn main() {
    println!("Hello world!");
}
```
:::

::::
**三是胶水语言属性。** Python 可以轻松调用 C、C++ 或 Rust 写出的底层扩展，将性能热点下沉到扩展层，自己则专注于高层的逻辑编排，在不牺牲整体速度的前提下保持开发的敏捷性。

**四是语法简洁、可读性强。** 清晰的结构既降低了新成员的入门门槛，也让团队协作时代码更易于审查和接手，这一点在人员流动频繁的 AI 研发团队中尤为重要。

**五是面向 AI 模型本身的亲和力。** Python 上手简单、用户基数庞大，这意味着互联网上沉淀了海量优质的 Python 公开代码语料。对于大模型预训练而言，数据即燃料，语料越丰沛，AI 学习生成该语言的准确率和完成度就越高。换句话说，Python 不仅是开发者用得顺手的工具，也是 AI 模型最“熟悉”的语言之一，这让“AI 辅助写 Python”这一场景天然比其他语言更加成熟和可靠。

这些优势叠在一起，"数据与 AI 密集型后端选 Python"是约束使然，而不是偏好。

JavaScript 与 TypeScript 站在界面与全栈层，同样受益于庞大的开发者群体和开源生态，积累了极为丰富的前后端同构代码语料，使 AI 在 UI 交互逻辑与 Node 服务代码生成上表现同样亮眼。而 Rust 则走上了一条互补的路径——它不以海量语料见长，却凭借极其严苛的编译器充当了“内置考官”的角色：AI 生成的代码只要存在内存安全隐患或类型不匹配，编译器便会抛出明确的错误反馈，AI 能据此反复修正，形成“生成—验证—修复”的敏捷闭环。三者各司其职——Python 凭丰沛语料与深厚生态统领智能编排与数据链路，TS/JS 凭同构能力主攻界面呈现，Rust 则凭编译器约束在底层实现精密加固，共同构成了 AI 时代从上层应用到系统底座的完整语言拼图。

## 为什么是 FastAPI

Python 生态里框架不少，上一节已经摆过 Django、Flask、FastAPI 三张牌。对 AI 应用后端这类"大量时间花在等 I/O、前后端协作频繁、输入输出形状复杂"的服务，FastAPI 的三项能力正好对上了三条约束。

| 约束 | FastAPI 的对应能力 | 前提与边界 |
|---|---|---|
| I/O 密集与可扩展 | 异步原生，等待时让出事件循环 | 异步是放大器而非银弹，真实瓶颈常在数据库与外部服务 |
| 契约先行与协作 | 自动文档，从类型标注生成 OpenAPI | 文档质量取决于模型定义是否充分 |
| 类型安全与可维护 | 类型驱动，Pydantic 在边界解析与校验 | 需配合类型标注与检查工具共同生效 |

**异步原生**：后端的时间，大量花在"等待"上：调用大模型 API 要等几秒，模型推理要等，读写数据库要等。同步写法下，一次等待就占用一个线程；异步写法下，等待期间线程让出，去服务其他请求。FastAPI 基于 asyncio 原生支持异步，I/O 密集路径用 async，CPU 密集或存量同步代码用 def，两者可以共存，无需全量重写。真实瓶颈约在数据库与外部服务，异步是放大器而非银弹，但方向正确：先把等待变成可重叠的等待。

**自动文档**：AI 应用前后端协作频繁，前端要集成接口、要联调。若契约靠口头约定或手写文档维持，漂移是迟早的事。FastAPI 从类型标注与 Pydantic 模型自动生成 OpenAPI 与交互式文档，改动模型即改动文档，前端可直接据此生成请求代码，契约漂移在测试中即可被捕获。这是协作型项目里最能省心的一项能力。

**类型安全**：AI 应用的输入输出形状复杂，各类模型参数与嵌套结构交织。若没有边界校验，非法输入会深入业务层才爆炸。FastAPI 与 Pydantic 把请求与响应的形状从文档约束变成运行时校验，非法输入在边界即被拦截并返回明确的 422，下游拿到的是已校验、带类型的对象。再配合静态检查工具，形状错误在提交前就能被发现。

## 从选型到组织：为什么需要分层

语言和框架都定了，还差最后一步：代码怎么组织。FastAPI 解决了"如何接收请求、校验参数、生成文档"，但它没有回答"业务逻辑放在哪、数据怎么存取"。如果图省事把这些全写进路由函数，会遇到三个真实的痛点：

一是测试麻烦。改一行业务要端到端起服务、连数据库、调外部接口才能验证。二是替换难。换一种存储方式，要改遍所有碰数据的地方。三是定位慢。一次请求出错，分不清是校验、业务还是存储的问题。

分层用单向依赖解决这三个痛点：Controller 依赖 Service，Service 依赖 Repository，下层不感知上层。每层只对自己的抽象负责，替换与测试都沿边界进行。

| 层次 | 职责 | 守什么 | 如何测试与替换 |
|---|---|---|---|
| Controller | 表现层，HTTP 翻译官 | 路由、参数解析、状态码与错误体，不含业务规则 | 用 TestClient 测路由与校验，可注入替身 Service |
| Service | 业务层，领域编排者 | 业务规则与事务边界，通过 Repository 接口操作数据 | 可注入替身 Repository 聚焦业务分支 |
| Repository | 数据层，数据源抽象 | 封装数据从哪来，提供领域友好的方法 | 用替身验证，替换数据源只需实现同一接口 |

三层协作让变更沿边界收敛：改校验不碰存储，换数据库不改路由，增规则只在 Service 内调整。下面用三段代码在同一内核中顺序执行，逐层看清这条链路。

## Repository 层：数据源的抽象

本段定义 Repository 层：数据源的抽象。本例的数据来自外部搜索服务，抽象只承诺一个 `search` 方法，调用 WebSearch 的 HTTP API，把网页结果整理成首尾一致的 `Document`。

```{code-cell} ipython3
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
from tavily import TavilyClient

@dataclass
class Document:
    id: str
    title: str
    source: str
    url: str
    content: str
class DocumentRepository(Protocol):
    def search(self, query: str) -> list[Document]: ...

class WebSearchRepository:
    """把关键词搜索转成对 WebSearch 的外部 HTTP 调用。"""
    def __init__(self, api_key: str) -> None:
        self._client = TavilyClient(api_key=api_key) if api_key else None

    def search(self, query: str) -> list[Document]:
        if self._client is None:
            return []
        response = self._client.search(query, max_results=5)
        docs: list[Document] = []
        for r in response.get("results", []):
            docs.append(Document(
                id=r["url"],
                title=r["title"],
                source=urlparse(r["url"]).netloc,
                url=r["url"],
                content=r["content"],
            ))
        return docs

print("DocumentRepository 抽象与 WebSearchRepository 已定义")
```

Repository 的存储抽象已就绪，初始为空，可被 Service 依赖注入。

## Service 层：业务规则与依赖注入

本段定义 Service 层，承载搜索的业务规则（空关键词拦截、按 URL 去重），依赖注入 DocumentRepository，不感知 HTTP。

```{code-cell} ipython3
import os

class SearchService:
    def __init__(self, repo: DocumentRepository) -> None:
        self.repo = repo

    def search(self, query: str) -> list[Document]:
        q = query.strip()
        if not q:
            return []
        docs = self.repo.search(q)
        # 业务规则：同一 URL 只留一条
        seen: set[str] = set()
        unique: list[Document] = []
        for d in docs:
            if d.url not in seen:
                seen.add(d.url)
                unique.append(d)
        return unique

api_key = os.environ.get("WEBSEARCH_API_KEY", "")
service = SearchService(WebSearchRepository(api_key=api_key))

if not api_key:
    print("提示：未配置 WEBSEARCH_API_KEY")
else:
    results = service.search("python pydantic")
    for d in results[:4]:
        print(" -", d.title[:44], "|", d.source)
    print("搜索返回", len(results), "条结果")

empty = service.search("  ")
print("empty keyword:", len(empty))
assert len(empty) == 0

print("service ready: search works as expected")
```

Service 的业务规则生效，空关键词被拦截、同一 URL 去重，搜索结果沿 DocumentRepository 落地。

## Controller 层：HTTP 翻译与本地验证

本段定义 Controller 层，用 FastAPI 路由与 Pydantic 模型暴露搜索接口，并用 TestClient 走通搜索与空关键词的链路。

```{code-cell} ipython3
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

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

client = TestClient(app)

r1 = client.get("/api/search", params={"q": "  "})
print("search empty:", r1.status_code, len(r1.json()))
assert r1.status_code == 200
assert r1.json() == []

if api_key:
    r2 = client.get("/api/search", params={"q": "python pydantic"})
    print("search:", r2.status_code, "返回", len(r2.json()), "条")
    assert r2.status_code == 200
    assert len(r2.json()) >= 1

print("layered validation passed")
```

分层链路贯通：Controller 仅做 HTTP 翻译，搜索请求沿 Service 与 DocumentRepository 返回结果。

## 本节小结

- 语言是第一步，AI 时代的智能与数据层由 Python 主导，靠生态、快速验证、胶水能力与可读性叠加出的优势站住脚跟。
- 框架是第二步，FastAPI 的异步原生、自动文档与类型安全三条能力，分别对上了 I/O 密集、契约先行与类型安全的约束。
- 组织是第三步，分层用单向依赖解决测试贵、替换难、定位慢三个痛点。
- Controller 薄而专注 HTTP，Service 厚而承载业务，Repository 封装数据源，替换或测试都沿边界进行。

> 语言定生态，框架定手感，分层定寿命，三者环环相扣，缺一不可。