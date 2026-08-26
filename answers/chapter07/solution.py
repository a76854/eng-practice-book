"""week07 习题参考答案（hermetic，TestClient 进程内测试）。

所有实现均为纯函数/工厂函数，不依赖网络、文件系统或外部服务。
复用 m2t.export 的纯函数特性，mock 转写数据在内存中构造。
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from m2t.export import export


def _mock_segments() -> list[dict]:
    return [
        {"speaker": "说话人1", "text": "大家好，今天讨论排期", "start": 0.0, "end": 3.2},
        {"speaker": "说话人2", "text": "我这边周三可以", "start": 3.2, "end": 5.8},
    ]


def _make_fake_db() -> dict:
    return {
        "demo123": {
            "id": "demo123",
            "filename": "meeting.wav",
            "result": {"segments": _mock_segments(), "duration": 5.8, "full_text": ""},
            "minutes": "",
        },
    }


class TranscribeResponse(BaseModel):
    task_id: str
    status: str
    format: str
    content: str


def make_ping_app() -> FastAPI:
    """返回含 GET /ping -> {\"msg\": \"pong\"} 的最小应用。"""
    app = FastAPI(title="ping demo")

    @app.get("/ping")
    def ping() -> dict:
        return {"msg": "pong"}

    return app


def make_transcribe_app(db: dict | None = None) -> FastAPI:
    """返回含 GET /transcribe/{task_id} 的应用。

    参数:
        db: 任务字典，key 为 task_id，value 为 m2t.export 兼容的任务形状。
            为 None 时使用内置 demo123。
    """
    fake_db: dict = db if db is not None else _make_fake_db()
    app = FastAPI(title="m2t transcribe demo")

    @app.get("/transcribe/{task_id}", response_model=TranscribeResponse)
    def get_transcribe(
        task_id: str,
        fmt: str = Query(default="txt", description="导出格式：txt/srt/md"),
    ) -> dict:
        task = fake_db.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if fmt not in ("txt", "srt", "md"):
            raise HTTPException(status_code=400, detail="不支持的导出格式，可选: txt/srt/md")
        content = export(task, fmt)
        return {"task_id": task_id, "status": "done", "format": fmt, "content": content}

    return app


# 默认应用实例（供直接导入测试）
app = make_transcribe_app()
