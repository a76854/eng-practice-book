"""M3 全栈参考解 — FastAPI 单工人 + fake ASR + fake LLM + m2t.store + 内联 HTML。

路由分层 + get_task_or_404 + 状态机 对齐 MeetingToText 只读参考：
  backend/app/routers/{transcribe,upload,generate}.py + deps.py

不实现 ASR 本体，复用 m2t（mock / fake 模型 / fake LLM）；hermetic，无 funasr/torch/openai/网络。
前端为最小可服务 HTML（内联 template，GET /），不必完整 Vue 重搭。
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
from fastapi.responses import HTMLResponse, PlainTextResponse

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

_FAKE_MINUTES = """# 会议纪要

## 概要
本次会议讨论了项目进度与下一步计划。

## 待办
- 待办：张三 负责整理需求文档
- 待办：李四 下周完成原型

## 下一步
- 下周复盘原型评审
"""


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


class _FakeLLM:
    """确定性 fake LLM：generate 返回固定纪要，不触 openai。"""

    def generate(
        self,
        system_prompt: str = "",
        user_message: str = "",
        **kwargs: Any,
    ) -> str:  # noqa: ANN002, ANN003
        _ = (system_prompt, user_message, kwargs)
        return _FAKE_MINUTES


# ---------------------------------------------------------------------------
# 全局状态：TaskStore + 单工人池 + 结果/纪要缓存
# ---------------------------------------------------------------------------

_ALLOWED_FORMATS = {"txt", "srt", "md"}
_TASK_NOT_FOUND = "Task not found"

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="m3-fullapp")

_store_lock = threading.Lock()
_store_instance: Any | None = None
_store_db_path: str | None = None
_results: dict[str, dict[str, Any]] = {}
_results_lock = threading.Lock()
_minutes: dict[str, str] = {}
_minutes_lock = threading.Lock()

_HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>MeetingToText — 会议转写</title></head>
<body>
<h1>MeetingToText 会议转写</h1>
<h2>任务列表</h2>
<div id="tasks">加载中...</div>
<template id="task-template"><div class="task"><span class="task-id"></span> <span class="task-status"></span></div></template>
<script>
async function loadTasks(){
  const res = await fetch("/tasks");
  const data = await res.json();
  const list = Array.isArray(data) ? data : (data.tasks || []);
  const el = document.getElementById("tasks");
  el.textContent = list.length ? list.map(t=> (t.task_id||t.id)+":"+(t.status||"")).join("\\n") : "暂无任务";
}
loadTasks();
async function uploadMock(){
  await fetch("/transcribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({audio_path:"mock"})});
  loadTasks();
}
</script>
<button onclick="uploadMock()">Mock 上传</button>
</body>
</html>
"""


def _resolve_db_path(db_path: str | None) -> str:
    """解析 db 路径：显式传入则用之；否则用环境变量或 tmp 文件。

    传入 ``:memory:`` 时仍落盘为 tmp 文件，因为 m2t.store 每操作新建
    ``sqlite3.connect``，原生 ``:memory:`` 无法跨连接共享。
    """
    if db_path is not None:
        if db_path == ":memory:":
            import tempfile

            fd, p = tempfile.mkstemp(prefix="m3_fullapp_", suffix=".db")
            os.close(fd)
            return p
        return db_path
    env = os.environ.get("M3T_DB_PATH", "") or os.environ.get("M2T_DB_PATH", "")
    if env:
        if env == ":memory:":
            import tempfile

            fd, p = tempfile.mkstemp(prefix="m3_fullapp_", suffix=".db")
            os.close(fd)
            return p
        return env
    import tempfile

    fd, p = tempfile.mkstemp(prefix="m3_fullapp_", suffix=".db")
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
# 后台转写逻辑
# ---------------------------------------------------------------------------


def _run_transcribe(task_id: str, audio_path: str) -> None:
    """后台单工人任务：pending -> processing -> done|error。"""
    store = _get_store()
    with contextlib.suppress(Exception):
        store.update(task_id, status="processing")
    # 让 pending→processing 的窗口对测试可观测
    time.sleep(0.12)

    try:
        from m2t.asr import transcribe as m2t_transcribe

        if audio_path.startswith("error"):
            raise RuntimeError("模拟转写失败")

        fake = _FakeModel()
        segments = m2t_transcribe(audio_path, model=fake, language="auto")
        if not segments:
            raise RuntimeError("未能识别到语音内容，请检查音频是否有效")

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
    global _store_instance, _store_db_path
    if db_path is not None:
        with _store_lock:
            _store_instance = _get_store_for_path(db_path)
            _store_db_path = db_path

    app = FastAPI(title="M3 Full App — MeetingToText mock")

    # ------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def get_index() -> HTMLResponse:
        return HTMLResponse(content=_HTML_PAGE, media_type="text/html; charset=utf-8")

    # ------------------------------------------------------------------
    @app.post("/transcribe")
    def post_transcribe(body: dict[str, Any] | None = None) -> dict[str, str]:
        if body is None or not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="缺少参数: audio_path")
        audio_path = body.get("audio_path")
        if audio_path is None:
            raise HTTPException(status_code=400, detail="缺少参数: audio_path")
        if not isinstance(audio_path, str) or audio_path.strip() == "":
            raise HTTPException(status_code=400, detail="缺少参数: audio_path")

        audio_path = audio_path.strip()
        is_mock = audio_path == "mock" or audio_path.startswith("mock:")

        if not is_mock and (not os.path.exists(audio_path) or os.path.isdir(audio_path)):
            raise HTTPException(status_code=400, detail=f"文件不存在或为目录: {audio_path}")

        task_id = uuid.uuid4().hex
        filename = os.path.basename(audio_path) if not is_mock else "mock.wav"
        store = _get_store()
        try:
            store.create(task_id, filename, status="pending", full_text="")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"创建任务失败: {exc}") from exc

        _executor.submit(_run_transcribe, task_id, audio_path)
        return {"task_id": task_id, "status": "pending"}

    # ------------------------------------------------------------------
    @app.get("/status/{task_id}")
    def get_status(task_id: str) -> dict[str, str]:
        task = get_task_or_404(task_id)
        result: dict[str, str] = {
            "task_id": str(task.get("id") or task_id),
            "status": str(task.get("status") or "pending"),
            "filename": str(task.get("filename") or ""),
        }
        if task.get("status") == "error" and task.get("full_text"):
            result["error"] = str(task.get("full_text") or "")
        else:
            result["error"] = ""
        return result

    # ------------------------------------------------------------------
    @app.get("/tasks")
    def list_tasks(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
        store = _get_store()
        try:
            rows = store.list_tasks(limit=limit)
        except Exception:
            rows = []
        tasks = [
            {
                "task_id": str(r.get("id") or ""),
                "id": str(r.get("id") or ""),
                "filename": str(r.get("filename") or ""),
                "status": str(r.get("status") or "pending"),
            }
            for r in rows
        ]
        return {"tasks": tasks}

    # ------------------------------------------------------------------
    @app.post("/generate/{task_id}")
    def post_generate(task_id: str, body: dict[str, Any] | None = None) -> dict[str, str]:
        _ = body  # template 可选，当前忽略（默认 default）
        task = get_task_or_404(task_id)
        status = str(task.get("status") or "")
        if status != "done":
            raise HTTPException(status_code=400, detail="任务未完成，无法生成纪要")

        # 幂等：已有纪要直接返回
        with _minutes_lock:
            cached = _minutes.get(task_id)
        if cached:
            return {"task_id": task_id, "minutes": cached}

        # 构造 prompt（hermetic，仅用于演示，无真实 LLM）
        with _results_lock:
            cached_res = _results.get(task_id)
        if cached_res is not None:
            full_text = str(cached_res.get("full_text") or "")
        else:
            full_text = str(task.get("full_text") or "")

        # fake LLM 生成
        fake_llm = _FakeLLM()
        minutes = fake_llm.generate(
            system_prompt="你是会议纪要助手",
            user_message=full_text or "mock transcript",
        )
        with _minutes_lock:
            _minutes[task_id] = minutes
        # 同步更新 _results 的 minutes 字段以便 md 导出
        with _results_lock:
            if task_id in _results:
                _results[task_id]["minutes"] = minutes
        return {"task_id": task_id, "minutes": minutes}

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

        with _results_lock:
            cached = _results.get(task_id)
        with _minutes_lock:
            minutes_val = _minutes.get(task_id, "")

        if cached is not None:
            segments = cached.get("segments", [])
            duration = cached.get("duration", 0.0)
        else:
            full_text = str(task.get("full_text") or "")
            if full_text:
                segments = [{"speaker": "", "text": full_text, "start": 0, "end": 0}]
            else:
                segments = []
            duration = 0.0

        task_filename = str(task.get("filename") or "meeting")
        export_task: dict[str, Any] = {
            "filename": task_filename,
            "id": task_id,
            "result": {"segments": segments, "duration": duration},
            "minutes": minutes_val,
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
    """测试隔离：清空任务表与内存缓存。"""
    try:
        store = _get_store()
        with store._get_conn() as conn:  # type: ignore[attr-defined]
            conn.execute("DELETE FROM tasks")
            conn.commit()
    except Exception:
        pass
    with _results_lock:
        _results.clear()
    with _minutes_lock:
        _minutes.clear()


__all__ = ["app", "create_app", "reset_state", "ensure_task_or_404", "get_task_or_404"]
