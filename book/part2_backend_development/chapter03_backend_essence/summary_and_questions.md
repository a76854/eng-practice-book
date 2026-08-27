---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **后端是“守边界”的工程**：API 设计定契约、业务逻辑做编排、数据流转管持久化与映射、安全防护贯穿入口与落库前。四者以“契约 → 校验 → 业务 → 持久化 → 响应”的单向流协作，职责越清晰，测试与替换成本越低。
- **语言选型无银弹，只有约束求解**：Java / C# 适合大型企业与强规范场景，Go 适合高并发网关与二进制交付，PHP 适合内容型存量与快速上线，Python 适合数据与 AI 集成型后端。结论需附带场景、团队、存量与运维约束，并以官方文档或公开基准为据。
- **框架谱系是约束的映射**：Django（全栈、约定）适合规范强、后台重的项目；Flask（微核、扩展）适合原型与可视化教学；FastAPI（现代、类型+异步）适合 I/O 密集、需自动文档与强校验的服务。三者无替代关系，只有 trade-off。
- **FastAPI + Pydantic 在本课程约束下胜出**：异步原生让 I/O 等待可让出，自动文档让契约即代码、协作不漂移，类型安全让非法输入在边界即被拦截。三者共同服务于“音频+ASR+LLM”的全链路闭环，而非偏好。
- **分层让每一层可独立演进**：Controller 薄而专注 HTTP 翻译，Service 厚而承载业务与事务，Repository 封装存储细节。依赖方向为 `Controller → Service → Repository`，替换存储或编排业务时只需沿边界操作，结合 `m2t.store.TaskStore` 与 `TestClient` 即可在本地完成可回归的验证。
- **贯穿启示**：本章的“职责—选型—框架—分层”四步为后续章节提供了锚点—— [第4章的 HTTP 与 RESTful](../chapter04_http_restful/index.md) 细化契约，[第5章的持久化](../chapter05_persistence_sql_orm/index.md) 深化 Repository，[第6章的并发](../chapter06_concurrency_perf/index.md) 展开异步，[第10章的安全](../../part4_advanced_engineering/chapter10_robustness_security/index.md) 回到纵深防护。

## 思考题

1. **职责切分**：在 MeetingToText 的“上传 → 转写 → 纪要”链路中，若把“生成纪要”放在前端调用 LLM 而非后端 Service，会对安全、计费与可观测性带来哪些影响？职责边界应如何重新划分？
2. **选型再辨**：假设团队以 Java 为主但需集成 Python 的 ASR 模型，你会选择“Java 网关 + Python 微服务”还是“全量切 Python”？请列出约束清单（人才、存量、延迟、运维）并说明判断依据。
3. **框架取舍**：一个以管理后台为主、定制少、交付期紧的课程项目，你会选 Django 还是 FastAPI？若后期需暴露大量 OpenAPI 给外部团队，结论会如何变化？
4. **异步的边界**：FastAPI 的异步能提升 I/O 密集场景的吞吐，但在 CPU 密集的音频预处理中为何未必有效？结合 [第6章的 GIL 与异步](../../part2_backend_development/chapter06_concurrency_perf/index.md) 讨论何时该用异步、何时该用进程或外部服务。
5. **分层的度**：三层架构在小项目中是否过度设计？请讨论“何时合并 Service 与 Repository、何时拆分”的判断信号，以及合并后对测试与替换的影响。
6. **契约的演进**：当前后端通过 Pydantic 自动生成 OpenAPI，若前端已据此生成代码，后端新增一个必填字段会如何影响协作？应如何通过版本、默认值与兼容性设计降低契约漂移的成本？
7. **存储替换**：若将 `SqliteTaskRepository` 替换为基于 SQLAlchemy 的 Postgres 实现，哪些层需要改动、哪些层可保持不变？`TaskRepository` 接口应如何设计以承载事务与分页等新需求？

文件 `book/part2_backend_development/chapter03_backend_essence/demo_summary.py`（本章贯通校验：分层 + 持久化 + 契约的最小闭环）：

```{code-cell} ipython3
# 文件 book/part2_backend_development/chapter03_backend_essence/demo_summary.py
import tempfile, pathlib
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from m2t.store import TaskStore

# 复用 3.5 的分层思想：Repository → Service → Controller 的最小闭环
class TaskRepo:
    def __init__(self, db_path: pathlib.Path):
        self.store = TaskStore(db_path)
    def create(self, tid: str, filename: str):
        self.store.create(tid, filename)
    def get(self, tid: str):
        return self.store.get(tid)

class TaskService:
    def __init__(self, repo: TaskRepo):
        self.repo = repo
    def create(self, tid: str, filename: str):
        if not tid or not filename:
            raise ValueError("empty")
        if self.repo.get(tid) is not None:
            raise ValueError("exists")
        self.repo.create(tid, filename)
        return self.repo.get(tid)

class CreateIn(BaseModel):
    task_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)

class CreateOut(BaseModel):
    id: str
    filename: str
    status: str

with tempfile.TemporaryDirectory() as td:
    db_path = pathlib.Path(td) / "summary.db"
    repo = TaskRepo(db_path)
    svc = TaskService(repo)
    app = FastAPI(title="Chapter03 Summary")

    @app.post("/tasks", response_model=CreateOut)
    def create(payload: CreateIn):
        try:
            row = svc.create(payload.task_id, payload.filename)
        except ValueError as e:
            if "exists" in str(e):
                raise HTTPException(status_code=409, detail=str(e))
            raise HTTPException(status_code=422, detail=str(e))
        return CreateOut(id=row["id"], filename=row["filename"], status=row["status"])

    @app.get("/tasks/{tid}", response_model=CreateOut)
    def get_one(tid: str):
        row = repo.get(tid)
        if row is None:
            raise HTTPException(status_code=404, detail="not found")
        return CreateOut(id=row["id"], filename=row["filename"], status=row["status"])

    client = TestClient(app)

    # 1) 创建并查询（覆盖契约→业务→持久化）
    r1 = client.post("/tasks", json={"task_id": "s1", "filename": "demo.wav"})
    print("create s1:", r1.json())
    assert r1.status_code == 200

    r2 = client.get("/tasks/s1")
    print("get s1:", r2.json())
    assert r2.json()["filename"] == "demo.wav"

    # 2) 校验边界：空 id → 422（Pydantic 在 Controller 层拦截）
    r3 = client.post("/tasks", json={"task_id": "", "filename": "x.wav"})
    print("empty id status:", r3.status_code)
    assert r3.status_code == 422

    # 3) 业务边界：重复 → 409
    r4 = client.post("/tasks", json={"task_id": "s1", "filename": "demo.wav"})
    print("duplicate status:", r4.status_code)
    assert r4.status_code == 409

    # 4) 持久化验证：TaskStore 仍可独立使用（分层的“可替换与可独立测试”）
    assert repo.get("s1") is not None
    assert repo.get("missing") is None

    print("贯通校验通过：分层 + 持久化 + 契约在同一闭环中可回归")
# 预期输出:
# create s1: {'id': 's1', 'filename': 'demo.wav', 'status': 'pending'}
# get s1: {'id': 's1', 'filename': 'demo.wav', 'status': 'pending'}
# empty id status: 422
# duplicate status: 409
# 贯通校验通过：分层 + 持久化 + 契约在同一闭环中可回归
```
