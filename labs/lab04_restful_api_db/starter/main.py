"""Lab04 starter: FastAPI + 迁移思想骨架。

为什么这样分层：路由层只做契约校验与状态码，存储层负责持久化，
迁移层负责表结构演进。骨架先用内存字典让路由可验证，再替换为 SQLite。

Run:
  python -c "import ast; ast.parse(open('main.py').read()); print('parse ok')"
  uvicorn main:app --port 8000
  python main.py
"""

from __future__ import annotations

import argparse
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(
    title="Lab04 Starter - Meeting Tasks API",
    description="Lab04 starter: RESTful tasks API with migration mindset",
    version="0.1.0",
)

# 内存占位存储，方便先跑通路由再替换为 SQLite
_tasks: dict[str, dict[str, Any]] = {}
_next_id: int = 1

# 迁移版本占位，演示版本化思想
SCHEMA_VERSION = 1
# MIGRATION v1 -> v2: add status column (placeholder for Alembic or hand-written migration)
# upgrade: ALTER TABLE tasks ADD COLUMN status TEXT DEFAULT 'pending'
# downgrade: ALTER TABLE tasks DROP COLUMN status


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="task title")
    content: str | None = Field(default=None, max_length=5000, description="optional content")


class TaskOut(BaseModel):
    id: str
    title: str
    content: str | None = None
    # 预留字段，v2 迁移后可启用
    # status: str = "pending"

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    version: str
    schema_version: int


@app.get("/health", response_model=HealthOut, tags=["health"])
def health() -> HealthOut:
    return HealthOut(status="ok", version=app.version or "0.1.0", schema_version=SCHEMA_VERSION)


@app.get("/tasks", response_model=list[TaskOut], tags=["tasks"])
def list_tasks() -> list[TaskOut]:
    return [TaskOut(**v) for v in _tasks.values()]


@app.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(payload: TaskCreate) -> TaskOut:
    global _next_id
    task_id = str(_next_id)
    _next_id += 1
    record: dict[str, Any] = {"id": task_id, "title": payload.title, "content": payload.content}
    _tasks[task_id] = record
    return TaskOut(**record)


@app.get("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def get_task(task_id: str) -> TaskOut:
    record = _tasks.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    return TaskOut(**record)


@app.put("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def update_task(task_id: str, payload: TaskCreate) -> TaskOut:
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="task not found")
    _tasks[task_id] = {"id": task_id, "title": payload.title, "content": payload.content}
    return TaskOut(**_tasks[task_id])


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(task_id: str) -> None:
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="task not found")
    del _tasks[task_id]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Lab04 starter API")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="enable auto reload (dev)")
    return parser


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    args = build_parser().parse_args(argv)
    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
