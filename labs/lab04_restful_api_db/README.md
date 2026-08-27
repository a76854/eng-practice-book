# 实验四 RESTful API 构建与数据库迁移

> 对应理论 [第4章 HTTP 与 RESTful 架构](../../book/part2_后端开发全景与核心基石/chapter04_HTTP与RESTful架构/index.md) 与 [第5章 数据持久化：从 SQL 到 ORM](../../book/part2_后端开发全景与核心基石/chapter05_数据持久化从SQL到ORM/index.md) · 4 学时 · 任务说明与验收标准同 `book/part5_实验指导书/experiment04_RESTful_API与数据库迁移/index.md`

## 实验目标

- 能用 FastAPI 与 Pydantic 实现会议记录的增删改查 API，使方法语义与状态码符合 RESTful 约定。
- 能用 `TestClient` 在本地不启服务的前提下验证契约，理解契约即代码的协作价值。
- 能用 `sqlite3` 或 SQLAlchemy 完成持久化闭环，并解释路由与存储的分层边界。
- 能用迁移思想管理表结构演进，理解 Alembic 的版本与回滚，或用手写 `schema_version` 表演示一次升级。

## 任务步骤

### 步骤 1 阅读理论

通读第4章 4.1 至 4.4 节与第5章 5.3 至 5.4 节，理解 HTTP 语义、FastAPI 校验与迁移的版本化思想。

### 步骤 2 读懂骨架

进入 `starter/`，按 `README.md` 安装依赖，尝试 `uvicorn main:app --port 8000` 并访问 `/docs`。

### 步骤 3 设计路由

实现 `GET /health`、`POST /tasks`、`GET /tasks`、`GET /tasks/{id}`、`DELETE /tasks/{id}`，可选 `PUT`，校验失败返回 422。

### 步骤 4 持久化与迁移

先用内存字典跑通，再替换为 SQLite；演示一次新增列的迁移，说明版本记录与回滚。

### 步骤 5 本地验证

用 `TestClient` 验证创建、查询、删除闭环，并覆盖非法输入的 422 路径。

### 步骤 6 自检

运行 `python -m py_compile starter/main.py`，确认 `git status` 干净，准备演示。

## 验收标准

- [ ] `main.py` 可被 `ast.parse` 解析，`app` 可被 `uvicorn main:app --port 8000` 引用。
- [ ] 5 个以上资源端点方法与状态码正确，Pydantic 校验生效，非法输入返回 422。
- [ ] 持久化闭环可用，删除后查询返回 404。
- [ ] 能演示一次迁移，说明版本与回滚，迁移与发布解耦。
- [ ] `TestClient` 本地验证通过，`python -m py_compile` 通过。
- [ ] `/docs` 可访问，仓库干净，能解释分层边界。

## 提交要求

提交 `starter/main.py`、`requirements.txt` 或 `pyproject.toml`、`README.md`，写清安装、启动与验证命令。以演示与讨论验收。

## 预估用时

4 学时。

## 起手代码

见 `starter/` 目录。先验证 `python -c "import ast; ast.parse(open('starter/main.py').read()); print('ok')"`，再按实验文档扩展路由与存储。
