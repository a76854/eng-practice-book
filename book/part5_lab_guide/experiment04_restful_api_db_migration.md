# RESTful API 构建与数据库迁移

本实验对应理论 [第4章 HTTP 与 RESTful 架构](../../part2_backend_development/chapter04_http_restful/index.md) 与 [第5章 数据持久化：从 SQL 到 ORM](../../part2_backend_development/chapter05_persistence_sql_orm/index.md)。建议先通读第4章 4.1 至 4.4 节的 HTTP 语义与 FastAPI 路由，再通读第5章 5.3 至 5.4 节的数据库访问三境界与迁移思想，再动手。你会在本实验中用 FastAPI 实现会议记录的增删改查接口，并用版本化思想管理表结构演进。

## 实验目标

- 能用 FastAPI 声明路径参数、查询参数与请求体，并用 Pydantic 完成校验，使非法输入以 422 统一暴露。
- 能按 RESTful 约定设计资源路由，使方法语义与状态码符合预期，并用 `TestClient` 在本地完成契约验证。
- 能用 `sqlite3` 或 SQLAlchemy 实现会议记录的持久化，完成创建、查询、更新、删除的完整闭环。
- 能用迁移思想管理表结构演进，理解版本表与可回滚脚本的价值，能用 Alembic 概念或手写 `schema_version` 表演示一次升级。
- 能说清路由层与存储层的边界，以及迁移脚本为何要与业务发布解耦。

## 任务步骤

### 步骤 1 阅读理论与现状

1. 阅读 [第4章 4.1 HTTP 与 RESTful](../../part2_backend_development/chapter04_http_restful/4.1_http_and_restful.md) 至 [4.3 统一响应与契约](../../part2_backend_development/chapter04_http_restful/4.3_error_and_contract.md)，留意方法语义、状态码与统一响应的协作价值。
2. 阅读 [第5章 5.3 SQL](../../part2_backend_development/chapter05_persistence_sql_orm/5.3_accessing_database.md) 与 [5.4 ORM](../../part2_backend_development/chapter05_persistence_sql_orm/5.4_orm.md)，理解参数化查询与 ORM 配合迁移的必要性。
3. 在书仓根目录运行 `python -c "import fastapi, pydantic; print(fastapi.__version__, pydantic.__version__)"`，确认 FastAPI 与 Pydantic 可用。

> 环境约定：本书面向 Linux，`uvicorn` 与 `pytest` 在行为一致，路径分隔符在展示时统一写 `/`，`pathlib.Path` 自动适配 `\`。

### 步骤 2 读懂起手骨架

1. 打开 `labs/lab04_restful_api_db/starter/main.py`，运行 `python -c "import ast; ast.parse(open('starter/main.py').read()); print('parse ok')"` 确认文件可解析。
2. 阅读 `starter/README.md`，按说明安装 `fastapi` 与 `uvicorn`，尝试 `uvicorn main:app --port 8000` 启动，并访问 `http://127.0.0.1:8000/docs` 观察自动生成的 Swagger。
3. 运行 `python main.py` 观察骨架的直接启动路径，留意 `if __name__ == "__main__"` 分支如何复用同一 `app` 对象。

### 步骤 3 设计资源与路由

1. 选定资源名为 `tasks` 或 `records`，设计至少 5 个端点：`GET /health`、`POST /tasks`、`GET /tasks`、`GET /tasks/{id}`、`DELETE /tasks/{id}`，可选 `PUT /tasks/{id}`。
2. 为每个端点声明正确的 HTTP 方法与状态码：创建返回 201，查询返回 200，不存在返回 404，校验失败由 FastAPI 自动返回 422。
3. 用 Pydantic 模型声明请求体与响应体，例如 `TaskCreate` 与 `TaskOut`，字段含 `title`、`content` 等，保持模型精简可演示。

### 步骤 4 实现持久化与迁移思想

1. 选择 `sqlite3` 标准库或 SQLAlchemy 作为存储层，实现任务的增删改查，示例可用内存字典先跑通，再替换为 SQLite 文件。
2. 引入版本化迁移：至少演示一次表结构演进，例如新增 `status` 或 `created_at` 列。可用 Alembic 概念描述升级与回滚，或手写一张 `schema_version` 表记录当前版本并用 SQL 脚本演示 `upgrade` 与 `downgrade`。
3. 保持迁移脚本可重放与可回滚，避免在业务代码中直接手改表结构，保证多人协作时演进可追溯。

### 步骤 5 本地验证

1. 用 `TestClient` 编写一次请求闭环：创建任务后查询列表，再按 id 查询与删除，断言状态码与返回体的字段符合 Pydantic 模型。
2. 在未启动真实服务的前提下运行 `pytest -q` 验证上述闭环，或在交互环境中用 `from fastapi.testclient import TestClient; client = TestClient(app)` 手动验证。
3. 刻意发送非法请求体，例如缺 `title` 或传空串，观察 422 的错误细节是否可读且与模型校验一致。

### 步骤 6 自检与清理

1. 运行 `python -m py_compile starter/main.py`，确认语法通过。
2. 运行 `uvicorn main:app --port 8000 --help` 或 `python main.py --help` 观察启动选项，确认文档中的运行命令在当前平台可复现。
3. 用 `git status` 确认无 `.venv`、`__pycache__`、`*.db`、`.mypy_cache` 等不应提交的内容，准备演示路由与迁移的协作边界。

## 验收标准

逐条自查，全部勾选即视为完成：

- [ ] `python -c "import ast; ast.parse(open('starter/main.py').read())"` 通过，`app = FastAPI()` 在 `main.py` 中可被 `uvicorn main:app --port 8000` 引用。
- [ ] 至少包含 `GET /health`、`POST /tasks`、`GET /tasks`、`GET /tasks/{id}`、`DELETE /tasks/{id}` 且方法与状态码符合 RESTful 约定。
- [ ] 请求体与响应体由 Pydantic 模型校验，非法输入返回 422 且错误细节可读。
- [ ] 持久化闭环可用，创建后可查询，删除后再次查询返回 404，数据在 SQLite 或等价存储中可验证。
- [ ] 能演示一次表结构迁移，说明版本记录与回滚思路，迁移与业务发布解耦。
- [ ] 能用 `TestClient` 在本地不启动服务的前提下验证主要端点，`python -m py_compile` 通过。
- [ ] `GET /docs` 可访问 Swagger，`git status` 干净，能口头解释路由与存储的分层边界。

## 提交要求

- 提交包含 `starter/main.py`、`starter/requirements.txt` 或 `starter/pyproject.toml`、`starter/README.md` 与顶层 `README.md` 的目录。`README.md` 需写清安装、启动与验证命令。
- 不需要提交 `.venv`、`__pycache__`、`*.db`、`htmlcov` 等生成物。
- 以演示与讨论作为验收，能现场启动服务并用 `TestClient` 或 `curl` 演示增删改查与迁移演进。

## 预估用时

4 学时。

建议分配：步骤 1 至 2 约 50 分钟，步骤 3 至 4 约 110 分钟，步骤 5 至 6 约 80 分钟。剩余时间用于自检与课堂讨论。
