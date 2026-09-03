---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# Docker Compose 编排

> 学完本节，你能回答：Compose 用什么原语描述多容器的依赖与联动？`depends_on` 的 `service_healthy` 与普通启动先后有何区别？为何 MeetingToText 用 Nginx + 后端的二服务足以演示“前端静态 + 后端动态”的联动？

## 为何需要编排：从单容器到拓扑

单个容器只解决“一个进程的可复现”，真实系统是多个进程的协作：前端静态资源需由 Nginx 托管、后端提供 `/api` 动态接口、持久化可能由数据库或文件卷承载。三者的关系是拓扑而非清单——谁依赖谁、谁先就绪、谁暴露哪一端口、谁共享哪一数据卷，都需要声明式地描述而非口头约定。

Docker Compose 用一个 `docker-compose.yml` 声明整个拓扑：`services` 定义每个容器如何构建与运行，`depends_on` 定义启动依赖，`ports` / `environment` / `volumes` / `healthcheck` 定义运行时契约。`docker compose up` 按拓扑一键拉起，`docker compose config` 可在不启动守护进程的前提下校验 YAML 是否合法。

类比：若 Dockerfile 是“一道菜的配方”，Compose 就是“一桌宴席的上菜顺序与摆盘图”。

## Compose 的核心原语

以下面的内联 Compose 拓扑为例（教学最小二服务，镜像 MeetingToText 的“前端静态 + 后端动态”分离）：

```yaml
services:
  backend:
    build: { context: ., dockerfile: Dockerfile }
    environment: { MTT_DATA_DIR: /data }
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request..."], interval: 30s }
    ports: ["8000:8000"]
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    depends_on: { backend: { condition: service_healthy } }
```

逐项解读：

- `services.backend.build`——后端的镜像如何构建（上下文与 Dockerfile 路径），构建输入与 11.2 节的层缓存直接相关。
- `services.backend.healthcheck`——后端何时算“就绪”。用 `urllib.request` 探测 `http://127.0.0.1:8000/api/health`，`interval` / `timeout` / `retries` / `start_period` 共同定义“多久探一次、探多久算超时、重试几次、启动后宽限多久”。
- `services.frontend.image`——前端用现成的 `nginx:alpine`，不需构建，拉取即可，体现“能用现成镜像就不自建”的最小可用原则。
- `services.frontend.depends_on.backend.condition: service_healthy`——前端仅在后端健康检查通过后才启动。若只写 `depends_on: [backend]`，则仅保证启动顺序，不保证后端已就绪；`service_healthy` 则把“启动先后”升级为“就绪先后”，避免前端在后端尚未监听时就转发而报 502。
- `ports`——`宿主机:容器` 的端口映射。`8000:8000` 让宿主机直连后端便于调试，`80:80` 让浏览器直连 Nginx。生产可改为仅暴露 80，由 Nginx 反向代理到后端内网端口。
- `restart: "no"`——教学演示选择不自动重启，便于观察失败；生产可按需改为 `unless-stopped`。

> **中立性说明**：Compose 适合单机或开发环境的声明式编排；多机与弹性伸缩需 Kubernetes 等编排器。教学选 Compose 是因为它零集群成本、YAML 即拓扑、校验可在本地完成，与“可复现的最小联动”目标最匹配。

> **环境约定**：本书面向 Linux，Compose 文件中的端口与路径在 在 Linux 环境均一致；`healthcheck` 的探测命令在容器内执行（Linux 环境），与宿主机操作系统无关；宿主机访问时统一用 `http://localhost:8000` 与 `http://localhost`。

## 可运行示例一：用 PyYAML 解析并校验内联 Compose 拓扑

示例：解析并校验内联 Compose 拓扑：

```{code-cell} ipython3
import yaml

# 内联 Compose 拓扑示例（与正文 YAML 一致，无需依赖仓库中的真实文件）
COMPOSE_YAML = """\
services:
  backend:
    build: { context: ., dockerfile: Dockerfile }
    environment: { MTT_DATA_DIR: /data }
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"], interval: 30s, timeout: 5s, retries: 10, start_period: 30s }
    ports: ["8000:8000"]
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    depends_on: { backend: { condition: service_healthy } }
"""

data = yaml.safe_load(COMPOSE_YAML)

print("=== Compose 顶层键 ===")
print(list(data.keys()))
assert "services" in data, "缺少 services"

services = data["services"]
print("\nservices:", list(services.keys()))
assert "backend" in services and "frontend" in services
print("services 校验通过：含 backend 与 frontend")

# backend 校验
backend = services["backend"]
print("\n--- backend ---")
print("build:", backend.get("build"))
assert backend.get("build", {}).get("dockerfile") == "Dockerfile"
print("build.dockerfile OK:", backend["build"]["dockerfile"])
print("environment:", backend.get("environment"))
assert backend.get("environment", {}).get("MTT_DATA_DIR") == "/data"
print("environment MTT_DATA_DIR OK")
print("healthcheck:", backend.get("healthcheck"))
hc = backend.get("healthcheck", {})
assert "test" in hc and "interval" in hc
print("healthcheck interval:", hc["interval"], "timeout:", hc.get("timeout"))
assert "api/health" in str(hc["test"])
print("healthcheck 探测路径 OK：含 api/health")
print("ports:", backend.get("ports"))
assert "8000:8000" in backend.get("ports", [])

# frontend 校验
frontend = services["frontend"]
print("\n--- frontend ---")
print("image:", frontend.get("image"))
assert frontend.get("image") == "nginx:alpine"
print("image OK: nginx:alpine（复用现成镜像）")
print("depends_on:", frontend.get("depends_on"))
dep = frontend.get("depends_on", {})
# 新版 Compose 语法：depends_on: { backend: { condition: service_healthy } }
assert "backend" in dep
cond = dep["backend"].get("condition") if isinstance(dep["backend"], dict) else dep["backend"]
print("depends_on condition:", cond)
assert cond == "service_healthy"
print("depends_on OK：frontend 仅在 backend 健康后启动（就绪先后，非仅启动先后）")
print("ports:", frontend.get("ports"))
assert "80:80" in frontend.get("ports", [])

print("\n拓扑结论：Nginx(:80) --depends_on(healthy)--> backend(:8000) 的二服务联动声明完整")
# 预期输出:
# === Compose 顶层键 ===
# ['services']
# services: ['backend', 'frontend']
# services 校验通过：含 backend 与 frontend
# --- backend ---
# build: {'context': '.', 'dockerfile': 'Dockerfile'}
# build.dockerfile OK: Dockerfile
# environment: {'MTT_DATA_DIR': '/data'}
# environment MTT_DATA_DIR OK
# healthcheck: {'test': ['CMD', 'python', '-c', ...], 'interval': '30s', ...}
# healthcheck interval: 30s timeout: 5s
# healthcheck 探测路径 OK：含 api/health
# ports: ['8000:8000']
# --- frontend ---
# image: nginx:alpine
# image OK: nginx:alpine（复用现成镜像）
# depends_on: {'backend': {'condition': 'service_healthy'}}
# depends_on condition: service_healthy
# depends_on OK：frontend 仅在 backend 健康后启动（就绪先后，非仅启动先后）
# ports: ['80:80']
# 拓扑结论：Nginx(:80) --depends_on(healthy)--> backend(:8000) 的二服务联动声明完整
```

```bash
# 本地校验 Compose 合法性（无需守护进程，纯 YAML 校验；以内联文本为例）
.venv/bin/python - <<'PY'
import yaml
compose = """\
services:
  backend:
    build: { context: ., dockerfile: Dockerfile }
    environment: { MTT_DATA_DIR: /data }
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"], interval: 30s }
    ports: ["8000:8000"]
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    depends_on: { backend: { condition: service_healthy } }
"""
yaml.safe_load(compose)
print('yaml ok')
PY
# 若已安装 Docker，可进一步做配置校验（本章不要求守护进程，教学中可选）
# docker compose -f docker-compose.yml config -q && echo "compose config ok"
```

## 可运行示例二：拓扑推演与反例——为何需要 `service_healthy`

示例：拓扑推演与健康检查：

```{code-cell} ipython3
import yaml

# 内联 Compose 拓扑示例（与正文 YAML 一致）
COMPOSE_YAML = """\
services:
  backend:
    build: { context: ., dockerfile: Dockerfile }
    environment: { MTT_DATA_DIR: /data }
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"], interval: 30s, timeout: 5s, retries: 10, start_period: 30s }
    ports: ["8000:8000"]
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    depends_on: { backend: { condition: service_healthy } }
"""

data = yaml.safe_load(COMPOSE_YAML)
services = data["services"]

# 推演：若 depends_on 仅为启动先后，会发生什么
print("=== 依赖语义推演 ===")
backend_hc = services["backend"].get("healthcheck", {})
frontend_dep = services["frontend"].get("depends_on", {})

# 普通 depends_on（仅启动先后）的语义
print("语义 A：depends_on: [backend]（仅启动先后）")
print("  时序：frontend 容器创建 ← backend 容器创建（不等待健康）")
print("  风险：frontend 启动时 backend 可能仍在加载模型/迁移 DB，转发即 502")

# service_healthy 的语义
print("\n语义 B：depends_on: {backend: {condition: service_healthy}}（就绪先后）")
print(f"  时序：frontend 等待 backend 健康检查通过（interval={backend_hc.get('interval')}, retries={backend_hc.get('retries')}, start_period={backend_hc.get('start_period')})")
print("  保障：frontend 转发时 backend 已通过 /api/health 探测")

# 用代码校验“语义 B”的配置已在教学样例中落实
assert frontend_dep.get("backend", {}).get("condition") == "service_healthy"
assert "test" in backend_hc
print("\n配置校验：教学样例已采用语义 B（service_healthy）")

# 拓扑排序演示：按依赖求启动顺序
print("\n=== 拓扑启动顺序 ===")
# 极简拓扑排序：backend 无依赖先启动，frontend 依赖 backend 后启动
order = []
remaining = set(services.keys())
# backend 无 depends_on，先加入
if "backend" not in str(services.get("frontend", {}).get("depends_on", {})):
    pass
# 实际推导：谁被依赖，谁先启动
deps: dict[str, set[str]] = {}
for name, cfg in services.items():
    d = cfg.get("depends_on", {})
    if isinstance(d, dict):
        deps[name] = set(d.keys())
    elif isinstance(d, list):
        deps[name] = set(d)
    else:
        deps[name] = set()
print("依赖表:", {k: list(v) for k, v in deps.items()})
# 排序：被依赖的先启动
order = sorted(services.keys(), key=lambda n: len(deps[n]))
print("启动顺序:", " -> ".join(order))
assert order[0] == "backend" and order[-1] == "frontend"
print("拓扑顺序 OK：backend 先就绪，frontend 后启动")

# 扩展思考：若加入 DB 服务，依赖如何声明（仅文本推演，不改动样例）
print("\n扩展推演：若加入 db 服务（postgres），拓扑如何扩展")
print("  services.db: image: postgres:16, healthcheck: pg_isready")
print("  services.backend.depends_on.db: {condition: service_healthy}")
print("  services.frontend.depends_on.backend: {condition: service_healthy}")
print("  启动顺序：db -> backend -> frontend（三段健康依赖）")
print("编排结论：Compose 用声明式的 healthcheck + depends_on 把‘启动先后’升级为‘就绪先后’")
# 预期输出:
# === 依赖语义推演 ===
# 语义 A：depends_on: [backend]（仅启动先后）
#   时序：frontend 容器创建 ← backend 容器创建（不等待健康）
#   风险：frontend 启动时 backend 可能仍在加载模型/迁移 DB，转发即 502
# 语义 B：depends_on: {backend: {condition: service_healthy}}（就绪先后）
#   时序：frontend 等待 backend 健康检查通过（interval=30s, retries=10, start_period=30s)
#   保障：frontend 转发时 backend 已通过 /api/health 探测
# 配置校验：教学样例已采用语义 B（service_healthy）
# === 拓扑启动顺序 ===
# 依赖表: {'backend': [], 'frontend': ['backend']}
# 启动顺序: backend -> frontend
# 拓扑顺序 OK：backend 先就绪，frontend 后启动
# 扩展推演：若加入 db 服务（postgres），拓扑如何扩展
#   services.db: image: postgres:16, healthcheck: pg_isready
#   services.backend.depends_on.db: {condition: service_healthy}
#   services.frontend.depends_on.backend: {condition: service_healthy}
#   启动顺序：db -> backend -> frontend（三段健康依赖）
# 编排结论：...
```

> **工程启示**：Compose 的价值不在“把两个容器写在一个文件里”，而在把“谁依赖谁的就绪”显式化。`service_healthy` 把人肉的“等一等再访问”变为可校验的拓扑约束；`healthcheck` 的探测路径（`api/health`）则与 [第10章 错误边界](../robustness_security/error_boundary_graceful_degradation.md) 的可观测约定相互印证——无健康探针的服务无法参与可靠编排。

```bash
# 查看 Compose 拓扑
cat labs/lab08_fullstack_container/starter/docker-compose.yml
# 校验 YAML 合法性（本地，无需守护进程；以内联文本为例）
.venv/bin/python -c "import yaml; print(yaml.safe_load('services: {backend: {image: python:3.12-slim}, frontend: {image: nginx:alpine}}')['services'].keys())"
```
