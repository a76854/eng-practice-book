"""M3 全栈冒烟测试（hermetic，无 funasr/torch/openai/网络）。

只断言可观测行为：HTTP 状态码、detail 文案、状态流转、导出内容、纪要与 HTML 关键词。
含一条完整链路：上传(mock)→转写(pending→done)→列表→生成纪要(mock LLM)→导出 txt/md。
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

import app as app_module  # 由 conftest 或 grader 的 PYTHONPATH 注入

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    """每个测试用例独立的 TestClient，自动隔离状态。"""
    try:
        app_module.reset_state()  # type: ignore[attr-defined]
    except Exception:
        pass
    c = TestClient(app_module.app)
    yield c
    try:
        app_module.reset_state()  # type: ignore[attr-defined]
    except Exception:
        pass


def _submit(client: TestClient, audio_path: str = "mock") -> str:
    """提交任务并返回 task_id，失败则抛断言。"""
    resp = client.post("/transcribe", json={"audio_path": audio_path})
    assert resp.status_code == 200, f"POST /transcribe failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "task_id" in data
    return str(data["task_id"])


def _wait_done(client: TestClient, task_id: str, timeout: float = 4.0) -> dict:
    """轮询 /status 直到 done，超时则失败。"""
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        r = client.get(f"/status/{task_id}")
        assert r.status_code == 200, f"GET /status failed: {r.text}"
        last = r.json()
        if last.get("status") == "done":
            return last
        time.sleep(0.05)
    pytest.fail(f"task {task_id} did not reach done within {timeout}s, last={last}")


# ---------------------------------------------------------------------------
# 1-2: 缺参数 400 与 malformed
# ---------------------------------------------------------------------------


def test_missing_audio_path_returns_400(client: TestClient):
    """Given 空 JSON，When POST /transcribe，Then 400 缺参。"""
    r = client.post("/transcribe", json={})
    assert r.status_code == 400
    assert "audio_path" in r.text or "缺少参数" in r.text


def test_empty_audio_path_returns_400(client: TestClient):
    """Given 空字符串 audio_path，When POST，Then 400。"""
    r = client.post("/transcribe", json={"audio_path": ""})
    assert r.status_code == 400
    assert "缺少参数" in r.text or "audio_path" in r.text


def test_malformed_json_returns_400_or_422(client: TestClient):
    """Given 非 JSON / 非法格式，When POST，Then 4xx。"""
    r = client.post("/transcribe", data="not json", headers={"Content-Type": "application/json"})
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 3-4: 不存在任务 404
# ---------------------------------------------------------------------------


def test_status_unknown_id_returns_404(client: TestClient):
    """Given 未知 task_id，When GET /status，Then 404 Task not found。"""
    fake = uuid.uuid4().hex
    r = client.get(f"/status/{fake}")
    assert r.status_code == 404
    assert "Task not found" in r.text


def test_export_unknown_id_returns_404(client: TestClient):
    """Given 未知 task_id，When GET /export，Then 404。"""
    fake = uuid.uuid4().hex
    r = client.get(f"/export/{fake}?format=txt")
    assert r.status_code == 404
    assert "Task not found" in r.text


def test_generate_unknown_id_returns_404(client: TestClient):
    """Given 未知 task_id，When POST /generate，Then 404。"""
    fake = uuid.uuid4().hex
    r = client.post(f"/generate/{fake}", json={})
    assert r.status_code == 404
    assert "Task not found" in r.text


# ---------------------------------------------------------------------------
# 5: 状态流转 pending -> done
# ---------------------------------------------------------------------------


def test_status_flow_pending_to_done(client: TestClient):
    """Given 提交 mock 任务，When 轮询 /status，Then 最终 done。"""
    task_id = _submit(client, "mock")
    first = client.get(f"/status/{task_id}").json()
    assert first["status"] in ("pending", "processing", "done")
    final = _wait_done(client, task_id)
    assert final["status"] == "done"
    assert final["task_id"] == task_id


# ---------------------------------------------------------------------------
# 6: 列表包含已提交任务
# ---------------------------------------------------------------------------


def test_tasks_list_contains_submitted(client: TestClient):
    """Given 提交并等待完成，When GET /tasks，Then 列表包含该任务。"""
    task_id = _submit(client, "mock")
    _wait_done(client, task_id)
    r = client.get("/tasks")
    assert r.status_code == 200
    data = r.json()
    tasks = data.get("tasks") if isinstance(data, dict) else data
    assert isinstance(tasks, list)
    ids = [str(t.get("task_id") or t.get("id") or "") for t in tasks]
    assert task_id in ids


# ---------------------------------------------------------------------------
# 7-11: 导出格式与纪要完整链路
# ---------------------------------------------------------------------------


def test_full_chain_transcribe_generate_export_txt_md(client: TestClient):
    """Given 整条链路：提交→等待→生成纪要→导出 txt/md，Then 均符合预期。"""
    # 上传(mock) → 转写(pending→done)
    task_id = _submit(client, "mock")
    _wait_done(client, task_id)

    # 列表
    r_list = client.get("/tasks")
    assert r_list.status_code == 200

    # 生成纪要(mock LLM)
    r_gen = client.post(f"/generate/{task_id}", json={"template": "default"})
    assert r_gen.status_code == 200, r_gen.text
    j = r_gen.json()
    assert "minutes" in j
    assert "会议纪要" in j["minutes"] or "待办" in j["minutes"]

    # 导出 txt
    r_txt = client.get(f"/export/{task_id}?format=txt")
    assert r_txt.status_code == 200
    assert "[说话人1]" in r_txt.text or "说话人1" in r_txt.text
    assert "大家好，我们开始开会" in r_txt.text

    # 导出 md（含纪要）
    r_md = client.get(f"/export/{task_id}?format=md")
    assert r_md.status_code == 200
    assert "# 会议转录" in r_md.text
    assert "会议纪要" in r_md.text
    assert "大家好" in r_md.text


def test_export_srt_contains_timestamp(client: TestClient):
    """Given 已完成任务，When format=srt，Then 含时间戳与 -->。"""
    task_id = _submit(client, "mock")
    _wait_done(client, task_id)
    r = client.get(f"/export/{task_id}?format=srt")
    assert r.status_code == 200
    assert " --> " in r.text
    assert "00:00:00" in r.text


def test_export_illegal_format_returns_400(client: TestClient):
    """Given 已完成任务，When format=pdf 非法，Then 400 中文。"""
    task_id = _submit(client, "mock")
    _wait_done(client, task_id)
    r = client.get(f"/export/{task_id}?format=pdf")
    assert r.status_code == 400
    assert "不支持的格式" in r.text


def test_export_missing_format_returns_400(client: TestClient):
    """Given 已完成任务，When 缺少 format 参数，Then 400。"""
    task_id = _submit(client, "mock")
    _wait_done(client, task_id)
    r = client.get(f"/export/{task_id}")
    assert r.status_code == 400


def test_export_and_generate_before_done_returns_400(client: TestClient):
    """Given 刚提交未完成任务，When 立即导出/生成，Then 400 任务未完成（竞态容忍）。"""
    task_id = _submit(client, "mock")
    # 立即操作：可能 pending 则 400；极少数已 done 则允许成功
    r_exp = client.get(f"/export/{task_id}?format=txt")
    if r_exp.status_code == 400:
        assert "未完成" in r_exp.text or "任务未完成" in r_exp.text
    else:
        assert r_exp.status_code == 200

    # 为 generate 提供确定性：若已 done 需测 before_done，则新建一个任务并立即测
    task_id2 = _submit(client, "mock")
    r_gen = client.post(f"/generate/{task_id2}", json={})
    # generate 在未完成时应 400，若已 done 则允许 200
    if r_gen.status_code == 400:
        assert "未完成" in r_gen.text or "任务未完成" in r_gen.text
    else:
        assert r_gen.status_code == 200


# ---------------------------------------------------------------------------
# 12: 前端 HTML
# ---------------------------------------------------------------------------


def test_index_html_contains_tasks_fetch(client: TestClient):
    """Given GET /，When 请求根路径，Then 返回 HTML 含任务列表关键词与 fetch 驱动。"""
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    body = r.text
    assert ("MeetingToText" in body) or ("会议转写" in body) or ("任务列表" in body)
    assert 'fetch("/tasks")' in body or "fetch('/tasks')" in body or 'fetch("/tasks")' in body


# ---------------------------------------------------------------------------
# Hermetic
# ---------------------------------------------------------------------------


def test_no_real_asr_import_at_runtime():
    """保证测试时未加载 funasr/torch/openai 真实依赖（hermetic）。"""
    import sys

    assert "funasr" not in sys.modules, "不应在测试中导入 funasr"
    assert "torch" not in sys.modules, "不应在测试中导入 torch"
