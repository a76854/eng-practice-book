"""week14 习题参考答案（hermetic，纯函数 + YAML 解析，不依赖 Docker 守护进程）。

本模块提供：compose 解析、VITE_API_BASE_URL 回退、URL 拼接、纯静态判定、
healthcheck 校验、client_max_body_size 解析，均为纯函数，便于 pytest hermetic。
"""

from __future__ import annotations

import re


def parse_compose(text: str) -> dict:
    """解析 docker-compose.yml 文本为字典。

    Args:
        text: YAML 文本。
    Returns:
        解析后的字典（yaml.safe_load 结果）。
    """
    import yaml  # type: ignore[import-untyped]

    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("compose YAML 顶层必须为 mapping")
    return data


def resolve_api_base(env: dict) -> str:
    """按 frontend/src/api/client.ts 逻辑解析 API_BASE。

    - 当 VITE_API_BASE_URL 非空（去空白后非空）时返回去尾斜杠后的值；
    - 否则回退为 "/api"。

    Args:
        env: 环境变量映射，key 为字符串。
    Returns:
        归一化的 API base。
    """
    raw = env.get("VITE_API_BASE_URL")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().rstrip("/")
    return "/api"


def build_api_url(base: str, path: str) -> str:
    """拼接 base 与 path，处理首尾斜杠重复。

    - base 为 "" 或 "/api" 时按相对路径语义返回 "/api/<path>"；
    - 否则按绝对 URL 拼接。

    Args:
        base: API base（如 "http://localhost:8000/api" 或 "/api"）。
        path: 路径（如 "/health" 或 "health"）。
    Returns:
        拼接后的完整 URL/路径。
    """
    p = path if path.startswith("/") else "/" + path
    if not base or base == "/api":
        return "/api" + p if p != "/api" else "/api"
        # 统一：/api + /health -> /api/health；避免 /api + /api 双写由上层保证
    b = base.rstrip("/")
    # 若 base 本身就是 /api 前缀，仍直接拼接
    if b == "/api":
        return "/api" + p
    return b + p


def is_pure_static_nginx(conf: str) -> bool:
    """判定 nginx 配置是否为纯静态托管（非反代）。

    判定条件（与 docker/nginx.conf 一致）：
    - 含 try_files（含 SPA 回退）
    - 含 location /api/ 且 return 404
    - 不含 proxy_pass

    Args:
        conf: nginx.conf 文本。
    Returns:
        是否为纯静态配置。
    """
    has_try_files = "try_files" in conf
    # 匹配 location /api/ 块内 return 404
    has_api_404 = bool(re.search(r"location\s+/api/\s*\{[^}]*return\s+404", conf, re.DOTALL))
    # 退化：若无块语法，仅检查两者同时出现
    if not has_api_404:
        has_api_404 = ("location /api/" in conf and "return 404" in conf)
    has_proxy = "proxy_pass" in conf
    return has_try_files and has_api_404 and not has_proxy


def validate_compose(data: dict) -> list[str]:
    """校验 compose 数据的健康依赖完整性。

    规则：若 frontend.depends_on.backend.condition == "service_healthy"
    则 backend 必须有 healthcheck，否则视为错误。

    Args:
        data: parse_compose 的返回值。
    Returns:
        错误消息列表，空表示通过。
    """
    errors: list[str] = []
    services = data.get("services", {}) if isinstance(data, dict) else {}
    if not isinstance(services, dict):
        return ["services 必须为 mapping"]
    frontend = services.get("frontend", {}) if isinstance(services, dict) else {}
    backend = services.get("backend", {}) if isinstance(services, dict) else {}
    # 取 condition
    cond: str | None = None
    if isinstance(frontend, dict):
        depends = frontend.get("depends_on", {})
        if isinstance(depends, dict):
            be = depends.get("backend", {})
            if isinstance(be, dict):
                cond = be.get("condition")
    if cond == "service_healthy":
        if not isinstance(backend, dict) or "healthcheck" not in backend:
            errors.append("healthcheck is required for service_healthy: backend missing healthcheck")
    return errors


def parse_client_max_body_size(conf: str) -> int | None:
    """解析 nginx client_max_body_size 为字节数。

    支持单位 k/m/g（不区分大小写，1k=1024），无指令或 off 返回 None。

    Args:
        conf: nginx.conf 文本。
    Returns:
        字节数或 None。
    """
    # 匹配 client_max_body_size <value>;
    m = re.search(r"client_max_body_size\s+([^;\s]+)\s*;", conf)
    if m is None:
        return None
    raw = m.group(1).strip()
    if raw.lower() == "off":
        return None
    # 纯数字（字节）
    if re.fullmatch(r"\d+", raw):
        return int(raw)
    um = re.fullmatch(r"(\d+)([kKmMgG])", raw)
    if um:
        num = int(um.group(1))
        unit = um.group(2).lower()
        mult = {"k": 1024, "m": 1024 * 1024, "g": 1024 * 1024 * 1024}[unit]
        return num * mult
    return None
