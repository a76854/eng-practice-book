"""M2 Web API 参考解 — FastAPI 单工人 + fake ASR + m2t.store。

路由分层 + get_task_or_404 + 状态机 对齐 MeetingToText 只读参考：
  backend/app/routers/{transcribe,upload}.py + deps.py

不实现 ASR 本体，复用 m2t（mock / fake 模型）；hermetic，无 funasr/torch/网络。
"""

from __future__ import annotations

import contextlib
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# fake 模型 — 确定性，覆盖 m2t.asr.normalize_result 形状 1
# ---------------------------------------------------------------------------

_FAKE_RAW_RESULT: list[dict[str, Any]] = [
    {
        "sentence_info": [
            {"text": "大家好，我们开始开会。", "start": 0, "end": 1200, "spk": 0},
            {"text": "好的，我先汇报一下进度。", "start": 1500, "end": 3000, "spk": 1},
        ]
    }
]


class _FakeModel:
    """确定性 fake 模型：实现 FunASR 的 generate 签名，返回固定形状。"""

    def generate(
        self,
        input: str,
        cache: dict[str, Any] | None = None,
        language: str = "auto",
        use_itn: bool = True,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:  # noqa: ANN002, ANN003
        _ = (input, cache, language, use_itn, kwargs)
        return [dict(item) for item in _FAKE_RAW_RESULT]


# ---------------------------------------------------------------------------
# 全局状态：TaskStore + 单工人池 + 结果缓存
# ---------------------------------------------------------------------------

_ALLOWED_FORMATS = {"txt", "srt", "md"}
_TASK_NOT_FOUND = "Task not found"

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="m2-webapi")

# store 相关：单例 + 锁 + 结果表（segments/duration 需另存，m2t.store 仅存 status/full_text）
_store_lock = threading.Lock()
_store_instance: Any | None = None
_store_db_path: str | None = None
_results: dict[str, dict[str, Any]] = {}
_results_lock = threading.Lock()


def _resolve_db_path(db_path: str | None) -> str:
    """解析 db 路径：显式传入则用之；否则用环境变量或 tmp 文件。

    传入 ``:memory:`` 时仍落盘为 tmp 文件，因为 m2t.store 每操作新建
    ``sqlite3.connect``，原生 ``:memory:`` 无法跨连接共享。
    """
    if db_path is not None:
        if db_path == ":memory:":
            import tempfile

            fd, p = tempfile.mkstemp(prefix="m2_webapi_", suffix=".db")
            os.close(fd)
            return p
        return db_path
    env = os.environ.get("M2T_DB_PATH", "")
    if env:
        if env == ":memory:":
            import tempfile

            fd, p = tempfile.mkstemp(prefix="m2_webapi_", suffix=".db")
            os.close(fd)
            return p
        return env
    import tempfile

    fd, p = tempfile.mkstemp(prefix="m2_webapi_", suffix=".db")
    os.close(fd)
    return p


def _get_store() -> Any:
    global _store_instance, _store_db_path
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                from m2t.store import TaskStore

                db_path = _resolve_db_path(None)
                _store_db_path = db_path
                _store_instance = TaskStore(db_path)
    return _store_instance


def _get_store_for_path(db_path: str | None) -> Any:
    """供 create_app 隔离测试使用的工厂：每次创建新的 TaskStore。"""
    from m2t.store import TaskStore

    path = _resolve_db_path(db_path)
    return TaskStore(path)


# ---------------------------------------------------------------------------
# 404 统一出口（对齐 deps.py:ensure_task_or_404）
# ---------------------------------------------------------------------------


def ensure_task_or_404(task: dict[str, Any] | None) -> dict[str, Any]:
    if task is None:
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND)
    return task


def get_task_or_404(task_id: str) -> dict[str, Any]:
    store = _get_store()
    task = store.get(task_id)
    return ensure_task_or_404(task)


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------


class TranscribeRequest(BaseModel):
    audio_path: str | None = None


# ---------------------------------------------------------------------------
# 后台转写逻辑
# ---------------------------------------------------------------------------


def _run_transcribe(task_id: str, audio_path: str) -> None:
    """后台单工人任务：pending -> processing -> done|error。"""
    store = _get_store()
    # 进入 processing（短暂延时让 pending 可被轮询观测）
    with contextlib.suppress(Exception):
        store.update(task_id, status="processing")
    # 让 pending→processing 的窗口对测试可观测
    time.sleep(0.12)

    try:
        # hermetic 转写：注入 fake 模型（不触 funasr）
        from m2t.asr import transcribe as m2t_transcribe

        # 若 audio_path 形如 "error*" 可模拟失败分支（测试不依赖）
        if audio_path.startswith("error"):
            raise RuntimeError("模拟转写失败")

        fake = _FakeModel()
        segments = m2t_transcribe(audio_path, model=fake, language="auto")
        if not segments:
            raise RuntimeError("未能识别到语音内容，请检查音频是否有效")

        # 构造 task 形态供导出复用
        try:
            duration = max(float(s.get("end", 0) or 0) for s in segments)
        except Exception:
            duration = 0.0
        full_text = "\n".join(
            (
                f"[{s.get('speaker')}] {s.get('text')}"
                if s.get("speaker")
                else str(s.get("text") or "")
            )
            for s in segments
        )
        with _results_lock:
            _results[task_id] = {"segments": segments, "duration": duration, "full_text": full_text}
        store.update(task_id, status="done", full_text=full_text)
    except Exception as exc:
        with _results_lock:
            _results.pop(task_id, None)
        with contextlib.suppress(Exception):
            store.update(task_id, status="error", full_text=str(exc))


# ---------------------------------------------------------------------------
# App 工厂
# ---------------------------------------------------------------------------


def create_app(db_path: str | None = None) -> FastAPI:
    """创建新的 FastAPI 实例（测试隔离用）。"""
    # 若指定 db_path，则覆盖全局 store，便于测试隔离
    global _store_instance, _store_db_path
    if db_path is not None:
        with _store_lock:
            # 清理旧隔离文件（若为 tmp）
            # 不强制删除；交由测试 teardown
            _store_instance = _get_store_for_path(db_path)
            _store_db_path = db_path

    app = FastAPI(title="M2 Web API — MeetingToText mock")

    # ------------------------------------------------------------------
    @app.post("/transcribe")
    def post_transcribe(body: dict[str, Any] | None = None) -> dict[str, str]:
        # 兼容空 body 与非 dict
        if body is None or not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="缺少参数: audio_path")
        audio_path = body.get("audio_path")
        # Pydantic 风格兼容：同时处理 TranscribeRequest 解析失败
        if audio_path is None:
            raise HTTPException(status_code=400, detail="缺少参数: audio_path")
        if not isinstance(audio_path, str) or audio_path.strip() == "":
            raise HTTPException(status_code=400, detail="缺少参数: audio_path")

        audio_path = audio_path.strip()
        is_mock = audio_path == "mock" or audio_path.startswith("mock:")

        # 非 mock 时校验文件存在性（mock 跳过以 hermetic）
        if not is_mock and (not os.path.exists(audio_path) or os.path.isdir(audio_path)):
            raise HTTPException(status_code=400, detail=f"文件不存在或为目录: {audio_path}")

        task_id = uuid.uuid4().hex
        filename = os.path.basename(audio_path) if not is_mock else "mock.wav"
        store = _get_store()
        try:
            store.create(task_id, filename, status="pending", full_text="")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"创建任务失败: {exc}") from exc

        # 提交后台单工人
        _executor.submit(_run_transcribe, task_id, audio_path)
        return {"task_id": task_id, "status": "pending"}

    # ------------------------------------------------------------------
    @app.get("/status/{task_id}")
    def get_status(task_id: str) -> dict[str, str]:
        task = get_task_or_404(task_id)
        # task 来自 m2t.store，字段为 id/filename/status/created_at/full_text
        result: dict[str, str] = {
            "task_id": str(task.get("id") or task_id),
            "status": str(task.get("status") or "pending"),
            "filename": str(task.get("filename") or ""),
        }
        # 透出 error（若为 error 状态）
        if task.get("status") == "error" and task.get("full_text"):
            result["error"] = str(task.get("full_text") or "")
        else:
            result["error"] = ""
        return result

    # ------------------------------------------------------------------
    @app.get("/export/{task_id}")
    def get_export(
        task_id: str,
        format: str | None = Query(default=None, alias="format"),  # noqa: A002
    ) -> PlainTextResponse:
        if format is None or str(format).strip() == "":
            raise HTTPException(status_code=400, detail="缺少参数: format")
        fmt = str(format).strip().lower().lstrip(".")
        if fmt not in _ALLOWED_FORMATS:
            msg = f"不支持的格式: {fmt}，支持: {', '.join(sorted(_ALLOWED_FORMATS))}"
            raise HTTPException(status_code=400, detail=msg)

        task = get_task_or_404(task_id)
        status = str(task.get("status") or "")
        if status != "done":
            raise HTTPException(status_code=400, detail="任务未完成，无法导出")

        # 从 _results 取 segments/duration；若缺失则回退用 full_text 单段
        with _results_lock:
            cached = _results.get(task_id)

        if cached is not None:
            segments = cached.get("segments", [])
            duration = cached.get("duration", 0.0)
        else:
            # 回退：无缓存时用 full_text 构造单段（保证至少 txt 可导出）
            full_text = str(task.get("full_text") or "")
            if full_text:
                segments = [{"speaker": "", "text": full_text, "start": 0, "end": 0}]
            else:
                segments = []
            duration = 0.0

        task_filename = str(task.get("filename") or "meeting")
        # 构造 m2t.export 兼容的 task 形态（dict 分支）
        export_task: dict[str, Any] = {
            "filename": task_filename,
            "id": task_id,
            "result": {"segments": segments, "duration": duration},
            "minutes": "",
            "full_text": str(task.get("full_text") or ""),
        }
        try:
            from m2t.export import export as m2t_export

            content = m2t_export(export_task, fmt)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"导出失败: {exc}") from exc

        return PlainTextResponse(content=content, media_type="text/plain; charset=utf-8")

    # ------------------------------------------------------------------
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# 默认单例（tests 以 `from app import app` 驱动）
app = create_app()


def reset_state() -> None:
    """测试隔离：清空任务表与结果缓存。"""
    try:
        store = _get_store()
        with store._get_conn() as conn:  # type: ignore[attr-defined]
            conn.execute("DELETE FROM tasks")
            conn.commit()
    except Exception:
        pass
    with _results_lock:
        _results.clear()


# 显式导出，供测试/重置使用
__all__ = ["app", "create_app", "reset_state", "ensure_task_or_404", "get_task_or_404"]
