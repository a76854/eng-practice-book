"""week14 习题测试（hermetic，纯函数 + YAML 解析，不依赖 Docker/网络）。"""

from __future__ import annotations

import pathlib
import textwrap

import pytest
from solution import (
    build_api_url,
    is_pure_static_nginx,
    parse_client_max_body_size,
    parse_compose,
    resolve_api_base,
    validate_compose,
)

# ---------------------------------------------------------------------------
# Helpers: load deploy-demo compose if present, else inline fallback
# ---------------------------------------------------------------------------

def _load_demo_compose_text() -> str:
    p = pathlib.Path(__file__).parent.parent.parent / "deploy-demo" / "docker-compose.yml"
    # answers/week14/test -> repo/deploy-demo
    # also try alternate relative
    candidates = [
        p,
        pathlib.Path(__file__).resolve().parents[2] / "deploy-demo" / "docker-compose.yml",
        pathlib.Path("deploy-demo/docker-compose.yml"),
    ]
    for c in candidates:
        if c.exists():
            return c.read_text(encoding="utf-8")
    # fallback inline (matches deploy-demo)
    return textwrap.dedent("""
    services:
      backend:
        build: { context: ., dockerfile: Dockerfile.backend }
        ports: ["8000:8000"]
        healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
          interval: 30s
          retries: 10
          start_period: 30s
      frontend:
        image: nginx:alpine
        ports: ["80:80"]
        depends_on:
          backend: { condition: service_healthy }
    """)


NGINX_PURE = """server {
    listen 80;
    root /usr/share/nginx/html;
    location /api/ { return 404; }
    location / { try_files $uri $uri/ /index.html; }
}
"""

NGINX_PROXY = """server {
    listen 80;
    location /api/ { proxy_pass http://backend:8000; }
    location / { try_files $uri $uri/ /index.html; }
}
"""


def test_parse_compose_has_services() -> None:
    text = _load_demo_compose_text()
    data = parse_compose(text)
    assert "services" in data
    services = data["services"]
    assert "backend" in services
    assert "frontend" in services
    # verify ports/healthcheck presence
    assert "healthcheck" in services["backend"]
    assert "depends_on" in services["frontend"]


def test_parse_compose_invalid_top_level() -> None:
    with pytest.raises(ValueError):
        parse_compose("- just\n- a\n- list\n")


def test_resolve_api_base_from_env() -> None:
    assert resolve_api_base({"VITE_API_BASE_URL": "http://localhost:8000/api"}) == "http://localhost:8000/api"
    # trailing slash trimmed
    assert resolve_api_base({"VITE_API_BASE_URL": "http://localhost:8000/api/"}) == "http://localhost:8000/api"
    # whitespace trimmed
    assert resolve_api_base({"VITE_API_BASE_URL": "  http://localhost:8000/api  "}) == "http://localhost:8000/api"


def test_resolve_api_base_fallback() -> None:
    assert resolve_api_base({}) == "/api"
    assert resolve_api_base({"VITE_API_BASE_URL": ""}) == "/api"
    assert resolve_api_base({"VITE_API_BASE_URL": "   "}) == "/api"
    assert resolve_api_base({"VITE_API_BASE_URL": None}) == "/api"  # type: ignore[dict-item]


def test_build_api_url_absolute() -> None:
    assert build_api_url("http://localhost:8000/api", "/health") == "http://localhost:8000/api/health"
    assert build_api_url("http://localhost:8000/api/", "/health") == "http://localhost:8000/api/health"
    assert build_api_url("http://localhost:8000/api", "health") == "http://localhost:8000/api/health"


def test_build_api_url_relative() -> None:
    assert build_api_url("/api", "/health") == "/api/health"
    assert build_api_url("/api", "health") == "/api/health"
    assert build_api_url("", "/health") == "/api/health"
    assert build_api_url("", "health") == "/api/health"


def test_is_pure_static_true() -> None:
    assert is_pure_static_nginx(NGINX_PURE) is True
    # also ensure demo file path resolves (no-op, keeps hermetic)
    assert is_pure_static_nginx(NGINX_PURE) is True


def test_is_pure_static_false_when_proxy() -> None:
    assert is_pure_static_nginx(NGINX_PROXY) is False
    # pure but with proxy added
    assert is_pure_static_nginx(NGINX_PURE + "\nproxy_pass http://backend:8000;") is False


def test_validate_compose_ok() -> None:
    text = _load_demo_compose_text()
    data = parse_compose(text)
    assert validate_compose(data) == []


def test_validate_compose_missing_healthcheck() -> None:
    text = textwrap.dedent("""
    services:
      backend:
        image: python:3.12-slim
        ports: ["8000:8000"]
      frontend:
        image: nginx:alpine
        depends_on:
          backend: { condition: service_healthy }
    """)
    data = parse_compose(text)
    errs = validate_compose(data)
    assert len(errs) == 1
    assert "healthcheck" in errs[0].lower()


def test_validate_compose_service_started_no_healthcheck_ok() -> None:
    text = textwrap.dedent("""
    services:
      backend:
        image: python:3.12-slim
      frontend:
        image: nginx:alpine
        depends_on:
          backend: { condition: service_started }
    """)
    data = parse_compose(text)
    assert validate_compose(data) == []


def test_client_max_body_size_parsing() -> None:
    assert parse_client_max_body_size("server { client_max_body_size 1m; }") == 1024 * 1024
    assert parse_client_max_body_size("server { client_max_body_size 100m; }") == 100 * 1024 * 1024
    assert parse_client_max_body_size("server { client_max_body_size 10k; }") == 10 * 1024
    assert parse_client_max_body_size("server { client_max_body_size 1g; }") == 1024 * 1024 * 1024
    assert parse_client_max_body_size("server { client_max_body_size 1024; }") == 1024
    assert parse_client_max_body_size("server { }") is None
    assert parse_client_max_body_size("server { client_max_body_size off; }") is None


def test_client_max_body_size_predicts_413() -> None:
    # 模拟：若限制 1m，则 5m 上传应被 nginx 413
    limit = parse_client_max_body_size("client_max_body_size 1m;")
    assert limit is not None
    upload_size = 5 * 1024 * 1024
    assert upload_size > limit  # 预测 413
    # 放宽到 100m 则通过
    limit2 = parse_client_max_body_size("client_max_body_size 100m;")
    assert limit2 is not None
    assert upload_size < limit2


def test_vite_missing_predicts_404() -> None:
    # VITE_API_BASE_URL 缺失 -> API_BASE 回退 /api -> nginx 纯静态返回 404
    base = resolve_api_base({})
    url = build_api_url(base, "/tasks")
    assert url == "/api/tasks"
    # 纯静态 nginx 对 /api/ 返回 404
    assert is_pure_static_nginx(NGINX_PURE) is True
    # 而正确注入应为跨源直连
    base_ok = resolve_api_base({"VITE_API_BASE_URL": "http://localhost:8000/api"})
    url_ok = build_api_url(base_ok, "/tasks")
    assert url_ok == "http://localhost:8000/api/tasks"
    assert url_ok.startswith("http://localhost:8000")
