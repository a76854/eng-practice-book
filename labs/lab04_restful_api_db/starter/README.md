# Lab04 starter 说明

本目录是实验四的起点骨架，对应 `book/part5_实验指导书/experiment04_RESTful_API与数据库迁移/index.md`。

## 包含内容

- `main.py`：FastAPI 应用骨架，含 `app = FastAPI()`、`GET /health` 与 `tasks` 资源的占位路由，能被 `uvicorn` 直接引用。
- `pyproject.toml`：最小项目声明，依赖 `fastapi` 与 `uvicorn`。
- `requirements.txt`：等价的 pip 依赖声明。

骨架保持“路由轻、存储可替换”的分层：路由层只做参数校验与状态码，存储层先用内存字典占位，方便后续替换为 SQLite 或 SQLAlchemy。

## 运行命令

```bash
# 安装依赖（任选其一，macOS / Linux 与 Windows 一致）
pip install -r requirements.txt
# 或
pip install -e .

# 语法检查
python -c "import ast; ast.parse(open('main.py').read()); print('parse ok')"

# 启动服务（开发模式）
uvicorn main:app --port 8000 --reload
# 生产或演示启动
uvicorn main:app --port 8000
# 直接用 Python 启动（复用同一 app 对象）
python main.py

# 启动后访问
# http://127.0.0.1:8000/health
# http://127.0.0.1:8000/docs   (Swagger)
# http://127.0.0.1:8000/openapi.json

# 本地契约验证（无需启动服务）
python -c "from fastapi.testclient import TestClient; from main import app; c=TestClient(app); print(c.get('/health').json())"
```

## 迁移思想提示

本实验不要求你立刻引入 Alembic 完整工具链，重点是体会版本化迁移：

```python
# 手写 schema_version 表的思路
# 1. 建表时写入版本 1
# 2. 新增列时执行 ALTER TABLE 并把版本提到 2
# 3. 回滚时执行逆向 SQL 并把版本降回 1
```

可在 `main.py` 中用注释标记 `MIGRATION v1 -> v2: add status column`，并在内存存储或 SQLite 中演示一次升级。后续实验再接入 Alembic 时，这段思考可直接复用。

## 跨平台说明

- 路径与端口参数在三平台一致，示例中统一写 `/`。
- 虚拟环境激活：`source .venv/bin/activate`（macOS / Linux）与 `.venv\Scripts\activate`（Windows）。
- `uvicorn` 的 `--reload` 在三平台均可用，生产环境建议去掉。

## 下一步

按实验文档步骤 3 至 5 补齐 `tasks` 资源的完整 CRUD、Pydantic 模型与持久化，再用 `TestClient` 验证闭环与 422 路径。
