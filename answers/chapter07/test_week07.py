"""week07 习题测试（hermetic，TestClient 真跑）。

覆盖：合法 200、非法参数 400、404、导出格式切换、response_model/OpenAPI、默认值。
"""

from __future__ import annotations

import importlib.util
import pathlib

from fastapi.testclient import TestClient

_spec = importlib.util.spec_from_file_location(
    "week07_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

make_ping_app = _mod.make_ping_app  # type: ignore[attr-defined]
make_transcribe_app = _mod.make_transcribe_app  # type: ignore[attr-defined]


def _client() -> TestClient:
    return TestClient(make_transcribe_app())


def test_ping_200() -> None:
    app = make_ping_app()
    c = TestClient(app)
    r = c.get("/ping")
    assert r.status_code == 200
    assert r.json() == {"msg": "pong"}


def test_transcribe_200_txt() -> None:
    c = _client()
    r = c.get("/transcribe/demo123?fmt=txt")
    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == "demo123"
    assert body["format"] == "txt"
    assert "大家好" in body["content"]
    assert body["status"] == "done"


def test_illegal_fmt_400() -> None:
    c = _client()
    r = c.get("/transcribe/demo123?fmt=pdf")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "支持" in detail or "可选" in detail

    r2 = c.get("/transcribe/demo123?fmt=docx")
    assert r2.status_code == 400

    r3 = c.get("/transcribe/demo123?fmt=")
    assert r3.status_code == 400


def test_not_found_404() -> None:
    c = _client()
    r = c.get("/transcribe/notfound?fmt=txt")
    assert r.status_code == 404
    assert r.json()["detail"] == "Task not found"

    r2 = c.get("/transcribe/does-not-exist")
    assert r2.status_code == 404


def test_export_format_switching() -> None:
    c = _client()
    r_txt = c.get("/transcribe/demo123?fmt=txt")
    r_srt = c.get("/transcribe/demo123?fmt=srt")
    r_md = c.get("/transcribe/demo123?fmt=md")
    assert r_txt.status_code == 200
    assert r_srt.status_code == 200
    assert r_md.status_code == 200
    txt = r_txt.json()["content"]
    srt = r_srt.json()["content"]
    md = r_md.json()["content"]
    # 三者互不相同
    assert txt != srt
    assert srt != md
    assert txt != md
    # 格式特征
    assert "-->" in srt
    assert "#" in md
    assert "说话人1" in txt or "大家好" in txt


def test_response_model_openapi() -> None:
    c = _client()
    r = c.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec["paths"]
    assert "/transcribe/{task_id}" in paths
    op = paths["/transcribe/{task_id}"]["get"]
    assert "200" in op["responses"]
    schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in schema
    assert "TranscribeResponse" in schema["$ref"]
    # components 中存在该 schema 且含四字段
    comp = spec["components"]["schemas"]["TranscribeResponse"]
    props = comp["properties"]
    for field in ("task_id", "status", "format", "content"):
        assert field in props


def test_default_fmt_is_txt() -> None:
    c = _client()
    r = c.get("/transcribe/demo123")
    assert r.status_code == 200
    body = r.json()
    assert body["format"] == "txt"
    # 与显式 txt 一致
    r2 = c.get("/transcribe/demo123?fmt=txt")
    assert body["content"] == r2.json()["content"]
