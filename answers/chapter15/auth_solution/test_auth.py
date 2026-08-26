"""认证作业测试：未带 token -> 401（hermetic，TestClient）。"""

from fastapi.testclient import TestClient

from .solution import VALID_TOKEN, create_app


def test_no_token_returns_401():
    app = create_app(token=VALID_TOKEN)
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Unauthorized"


def test_wrong_token_returns_401():
    app = create_app(token=VALID_TOKEN)
    client = TestClient(app)
    resp = client.get("/api/health", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_correct_token_passes():
    app = create_app(token=VALID_TOKEN)
    client = TestClient(app)
    resp = client.get("/api/health", headers={"Authorization": f"Bearer {VALID_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_public_path_without_token():
    app = create_app(token=VALID_TOKEN)
    client = TestClient(app)
    # 非 /api/* 不鉴权
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200


def test_api_tasks_needs_auth():
    app = create_app(token=VALID_TOKEN)
    client = TestClient(app)
    assert client.get("/api/tasks").status_code == 401
    assert (
        client.get("/api/tasks", headers={"Authorization": f"Bearer {VALID_TOKEN}"}).status_code
        == 200
    )
