---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 周14 打包部署与CI

> 为什么要单列一周讲“打包部署与 CI（Continuous Integration，持续集成）”？前几周你已经能在本机用 `meetingtotext serve --reload` + `npm run dev` 调通 M2 的 Web API，但这些命令强依赖“你的机器装对了 Python 3.12、装对了 funasr、前端装对了 Node 20”。换一台机器、换一位同学，往往就跑不起来。打包（image）解决“环境可复制”，编排（compose）解决“多服务一键启动”，CI（推送即测）解决“每次提交都自动验证是否可构建、可测试”。本章以“把 M2 一键部署（`docker compose up --build`）”为目标，带你打通 Docker 多阶段构建、容器网络、Compose 编排与 GitHub Actions 流水线，并厘清本项目最新拓扑：nginx 纯静态托管 + 前端通过 `VITE_API_BASE_URL` 直连后端（跨源（CORS，Cross-Origin Resource Sharing）直连）。

## 学习目标

完成本章后，你将能够：

1. 能编写 Dockerfile 多阶段构建（multi-stage build），解释“构建阶段 vs 运行阶段”为何能减小镜像体积，并为 `m2t` 后端编写基于 `python:3.12-slim` 的最小镜像。
2. 能区分“纯静态托管（static hosting） vs 反向代理（reverse proxy）”两种前端部署形态，解释 MeetingToText 为何选择 nginx 纯静态 + `VITE_API_BASE_URL` 直连后端，并预测缺失该变量时的跨域/404 行为。
3. 能编写 `docker-compose.yml` 编排前后端两服务，正确配置 `healthcheck`、`depends_on: condition: service_healthy` 与端口映射，并用 `docker compose config -q` 做语法校验。
4. 能阅读并编写 `.github/workflows/ci.yml` 的 `on / jobs / steps` 结构，解释“推送即测（push-to-test）”如何阻断问题合并。

## 先修要求

- 完成 [周7 HTTP 与 REST API](week07_HTTP与REST_API.md) 与 [周8 数据持久化与SQL](week08_数据持久化与SQL.md)（会用 `m2t` 包与 `pytest`）。
- 会用命令行运行 `docker --version` 与 `docker compose version`（本章不要求真实构建大镜像，校验用 `config -q` 即可）。
- 已阅读 MeetingToText 的 `docker/{Dockerfile.backend,Dockerfile.frontend,nginx.conf,docker-compose.yml}` 与 `.github/workflows/ci.yml` 的 HEAD 版本（只读参考，不复制大段生产配置）。

## 正文

### 14.1 从“本地可跑”到“别人可跑”：为何要打包

本地开发的启动方式是两条独立命令：

```bash
# 终端 1 — 后端（需 Python 3.12 + 已安装 m2t）
meetingtotext serve --reload  # 监听 8000

# 终端 2 — 前端（需 Node 20 + npm ci）
cd frontend && npm run dev    # 监听 5173，vite 将 /api 代理到 8000
```

这对“你的机器”有效，对“别人的机器”往往失效：Python 版本不对、系统缺 `libsndfile1`、前端 `node_modules` 未装、端口被占用、环境变量未设。Docker 的思路是“把运行环境也写进代码”：`Dockerfile` 声明“从什么基础镜像开始、装哪些系统依赖、拷哪些文件、跑什么命令”，`docker build` 产出不可变的镜像（image），`docker run / docker compose up` 在任意装了 Docker 的机器上复现同一环境。

### 14.2 多阶段构建：以 `Dockerfile.frontend` 为例

MeetingToText 的前端镜像使用两阶段（stage）：

- **阶段 1 `build`：`node:20-alpine`** — 装 `npm ci`、执行 `vue-tsc --noEmit && vite build`，产出 `dist/` 静态文件。
- **阶段 2 `runtime`：`nginx:alpine`** — 仅拷贝 `dist/` 到 `/usr/share/nginx/html`，并拷贝 `docker/nginx.conf` 作为 nginx 配置。

只读对照 `docker/Dockerfile.frontend` 的形状（以 HEAD 为准）：

```dockerfile
# Stage 1 — build frontend with node:20-alpine
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts ./
COPY frontend/index.html ./
COPY frontend/public ./public
COPY frontend/src ./src
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 2 — serve with nginx:alpine
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

要点：

- `ARG VITE_API_BASE_URL` 是**构建时（build-time）变量**：`vite build` 会在编译期把 `import.meta.env.VITE_API_BASE_URL` 静态替换为该值，写入 `dist/assets/*.js`。运行时改环境变量不会生效，必须重新 `build`。
- 选择性 `COPY`（只拷 `package.json` / `src/` 等）而非 `COPY . .`，配合 `.dockerignore`（排除 `data/` / `node_modules/` / `models/`），避免数 GB 的模型与依赖进入构建上下文。
- 两阶段后镜像仅含 `nginx:alpine` + 静态文件，体积远小于“在 `node:20-alpine` 里直接 `nginx`”的单阶段镜像。

```{code-cell} ipython3
# 演示：VITE_API_BASE_URL 缺失时的回退逻辑（对应 frontend/src/api/client.ts）
# export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api'
import os

def resolve_api_base(env: dict) -> str:
    raw = env.get("VITE_API_BASE_URL")
    if raw and raw.strip():
        return raw.strip().rstrip("/")
    return "/api"

# 场景 1：compose 正确注入 -> 前端直连后端
print(resolve_api_base({"VITE_API_BASE_URL": "http://localhost:8000/api"}))
# 场景 2：缺失 -> 回退到相对路径 /api（纯静态下会命中 nginx 的 404 规则）
print(resolve_api_base({}))
# 场景 3：空字符串或空白 -> 同缺失
print(resolve_api_base({"VITE_API_BASE_URL": "  "}))

assert resolve_api_base({"VITE_API_BASE_URL": "http://localhost:8000/api"}) == "http://localhost:8000/api"
assert resolve_api_base({}) == "/api"
print("—— 断言通过：VITE_API_BASE_URL 缺失时回退到 /api ——")
```

### 14.3 后端镜像：`python:3.12-slim` 的最小实践

只读对照 `docker/Dockerfile.backend` 的形状：`FROM python:3.12-slim`，装 `libsndfile1`（`soundfile` / `librosa` 依赖），按 `ARG MTT_TORCH_FLAVOR=cpu|cuda` 条件装不同 `torch`，随后 `COPY pyproject.toml + backend/` 再 `pip install -e .`，最后 `EXPOSE 8000` 与 `CMD ["meetingtotext", "serve", "--host", "0.0.0.0", "--port", "8000"]`。

教学最小版落在 `deploy-demo/Dockerfile.backend`（以本书仓库为准）：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY m2t/ ./m2t/
RUN pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["python", "-m", "m2t.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

教学取舍：不含 `torch`/`funasr` 等重依赖（列为 optional），以保持 demo 快速构建；生产镜像在 `pip install -e .` 之前先按 `MTT_TORCH_FLAVOR` 装 `torch`，并用 `ENV MTT_DATA_DIR=/data MODELSCOPE_CACHE=/data/models` 指向持久化卷。

层缓存（layer cache）技巧：先拷 `pyproject.toml` 再 `pip install`，最后拷常变的 `backend/`，可让依赖层被复用；`--no-cache-dir` 避免在镜像中残留 pip 缓存。

### 14.4 容器网络与「纯静态托管 vs 反向代理」

#### 容器网络与端口

- `EXPOSE` 仅声明“容器内监听的端口”，不自动发布到宿主机；`ports: ["8000:8000"]` 才把容器端口映射到宿主机端口，浏览器才能 `http://localhost:8000/api/health` 访问。
- Compose 默认创建同一 `bridge` 网络，服务间可用 `http://backend:8000` 互访（服务名即 DNS）；但本项目**浏览器不在该网络内**，故前端到后端的调用必须是浏览器可达的宿主机地址。

#### 纯静态托管 vs 反向代理（概念对比）

| 形态 | nginx 做什么 | 前端如何访问后端 | 适用场景 |
|---|---|---|---|
| 反向代理 | `location /api/ { proxy_pass http://backend:8000; }`，浏览器 `GET /api/*` 同源走到 nginx，再由 nginx 转发到后端 | 同源（same-origin），无 CORS | 传统“前后端同域”部署 |
| 纯静态托管（本项目现状） | `try_files $uri $uri/ /index.html;` 仅 serve 静态文件，`location /api/ { return 404; }` 明确不代理 | 跨源直连（cross-origin）：浏览器直接 `fetch("http://localhost:8000/api/...")`，后端通过 `MTT_CORS_ORIGINS` 放行 `http://localhost` | 前后端分离、端口分明的本地/单机部署 |

MeetingToText 的 `docker/nginx.conf` 即纯静态托管（以 HEAD 为准）：

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    location /api/ { return 404; }
    location / { try_files $uri $uri/ /index.html; }
}
```

`docker-compose.yml` 中 `frontend.args.VITE_API_BASE_URL: "http://localhost:8000/api"` 与 `backend.ports: ["8000:8000"]` 配合：构建期把后端地址写进前端 `dist`，运行期浏览器跨源直连后端，nginx 不参与 API 转发。开发期的 `vite.config.ts` 另有 `server.proxy: { '/api': { target: 'http://localhost:8000' } }`，仅在 `npm run dev` 时生效，与生产纯静态解耦。

```{code-cell} ipython3
# 演示：纯静态 vs 反代的 URL 构造差异（hermetic 纯函数）
def build_api_url(base: str, path: str) -> str:
    """拼接 API_BASE 与路径，处理首尾斜杠。"""
    if not base or base == "/api":
        # 相对路径形态（反代或 dev proxy 场景：浏览器发 /api/...）
        return "/api" + (path if path.startswith("/") else "/" + path)
    base = base.rstrip("/")
    path = path if path.startswith("/") else "/" + path
    return base + path

# 纯静态：前端直连后端
print(build_api_url("http://localhost:8000/api", "/transcribe/demo123"))
# 反代/开发：同源相对路径
print(build_api_url("/api", "/transcribe/demo123"))
# VITE_API_BASE_URL 缺失回退
print(build_api_url("", "/health"))

assert build_api_url("http://localhost:8000/api", "/health") == "http://localhost:8000/api/health"
assert build_api_url("/api", "/health") == "/api/health"
assert build_api_url("http://localhost:8000/api/", "/health") == "http://localhost:8000/api/health"
print("—— 断言通过：URL 拼接在两种拓扑下均正确 ——")
```

> 关键时序：`VITE_API_BASE_URL` 是构建时注入（`ARG` → `ENV` → `vite build` 静态替换），不是运行时 `docker run -e`。若在 `docker-compose.yml` 改了该值，必须 `docker compose up --build` 重新构建前端镜像，否则 `dist` 中的硬编码旧值不变。

### 14.5 Compose 编排：一键部署 M2

只读对照 `docker/docker-compose.yml` 的两服务形状：

- `backend`: `build: { context: .., dockerfile: docker/Dockerfile.backend }`、`volumes: ["../data:/data"]`、`environment: { MTT_DATA_DIR, MODELSCOPE_CACHE }`、`healthcheck: { test: urlopen http://127.0.0.1:8000/api/health, start_period: 300s }`、`ports: ["8000:8000"]`。
- `frontend`: `build: { context: .., dockerfile: docker/Dockerfile.frontend, args: { VITE_API_BASE_URL } }`、`ports: ["80:80"]`、`depends_on: { backend: { condition: service_healthy } }`。

`healthcheck` 与 `depends_on: service_healthy` 的协同：`healthcheck` 周期性在容器内 `urlopen` 探活，仅当连续成功才标记 `healthy`；`depends_on` 确保前端容器在后端 `healthy` 之前不启动，避免浏览器先拿到前端页面却因后端未就绪而请求失败。`start_period: 300s` 覆盖首次启动需下载 FunASR 模型（~1-2 GB）的窗口期。

`deploy-demo/docker-compose.yml` 为教学最小版（字段与生产一致，卷路径简化）：

```yaml
services:
  backend:
    build: { context: ., dockerfile: Dockerfile.backend }
    ports: ["8000:8000"]
    environment: { MTT_DATA_DIR: /data }
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 10
      start_period: 30s
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    depends_on:
      backend: { condition: service_healthy }
```

校验（hermetic，不需真实构建）：

```bash
docker compose -f deploy-demo/docker-compose.yml config -q && echo "compose valid"
```

该命令仅做 YAML 合并与 schema 校验，不拉镜像、不启动容器，适合 CI 与教材中的快速自检。

```{code-cell} ipython3
# 演示：解析 compose YAML 并校验关键字段（hermetic，不依赖 Docker 守护进程）
import pathlib, textwrap

try:
    import yaml  # pyyaml，部署与 CI 的常见依赖
except ModuleNotFoundError:
    print("pyyaml 未安装，跳过 YAML 解析演示（CI 环境需 pip install pyyaml）")
else:
    compose_text = pathlib.Path("deploy-demo/docker-compose.yml").read_text(encoding="utf-8") if pathlib.Path("deploy-demo/docker-compose.yml").exists() else textwrap.dedent("""
    services:
      backend:
        build: { context: ., dockerfile: Dockerfile.backend }
        ports: ["8000:8000"]
        healthcheck:
          test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
          interval: 30s
          retries: 10
          start_period: 30s
      frontend:
        image: nginx:alpine
        ports: ["80:80"]
        depends_on:
          backend: { condition: service_healthy }
    """)
    data = yaml.safe_load(compose_text)
    services = data.get("services", {})
    print("services:", list(services.keys()))
    backend = services.get("backend", {})
    frontend = services.get("frontend", {})
    has_healthcheck = "healthcheck" in backend
    has_depends = "depends_on" in frontend
    cond = frontend.get("depends_on", {}).get("backend", {}).get("condition") if isinstance(frontend.get("depends_on"), dict) else None
    print("backend has healthcheck:", has_healthcheck)
    print("frontend depends_on backend condition:", cond)
    assert "backend" in services and "frontend" in services
    assert has_healthcheck is True
    print("—— 校验通过：compose 含 healthcheck 与 service_healthy 依赖 ——")
```

### 14.6 CI「推送即测」：`.github/workflows/ci.yml`

只读对照 MeetingToText 的 `.github/workflows/ci.yml`：`on: [push, pull_request, workflow_dispatch]`，三 jobs：`backend`（`setup-python 3.12` → `pip install -e ".[dev]"` → `ruff check` → `mypy` → `pytest -q`）、`frontend`（`setup-node 20` → `npm ci` → `eslint` → `build` → `vitest`）、`system`（`workflow_dispatch` 触发、缓存 `~/.cache/modelscope`、跑真实 FunASR 模型测试）。

教学样例 `deploy-demo/ci.yml`（`.github` 风格，字段名与真实 CI 一致，精简为单 job 便于阅读）：

```yaml
name: CI
on: [push, pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[dev]" && pip install pyyaml
      - run: ruff check .
      - run: mypy m2t
      - run: pytest -q
      - run: docker compose -f deploy-demo/docker-compose.yml config -q
```

要点：

- `on: push` 即“推送即测”：每次 `git push` 自动触发，无需人工跑全量检查。
- `jobs.<name>.steps` 顺序即执行顺序；单 job 内失败即阻断，后续步骤不跑，PR 无法合并。
- `docker compose config -q` 作为 CI 步骤可零成本拦截 `docker-compose.yml` 语法/字段错误，早于镜像构建。

### 改动并预测

以下实验均可在本章 `{code-cell}` 或本地 `.venv` 中复现。按“改什么 → 预测 → 解释”三段式书写。

#### 改动并预测 实验 1：删掉 `healthcheck` → 预测依赖失效

- **改什么**：把 `deploy-demo/docker-compose.yml` 中 `backend.healthcheck` 整段删除，保留 `frontend.depends_on.backend.condition: service_healthy`，随后执行 `docker compose -f deploy-demo/docker-compose.yml config`（或 `config -q`）。
- **预测**：`config` 直接报错退出、非 0（`service "frontend" depends on service "backend" which is undefined: healthcheck is required for service_healthy` 或等价的 `depends_on condition service_healthy requires healthcheck`）；若把 `condition: service_healthy` 同步改为 `service_started` 则校验通过，但语义退化为“容器已启动即认为就绪”，前端可能在后端 `uvicorn` 尚未监听 `8000` 时就被浏览器访问，出现 `ERR_CONNECTION_REFUSED` 或 API 500。
- **解释**：Compose 的 `service_healthy` 是“健康语义”，必须有 `healthcheck` 才能判定 `healthy`；去掉健康探针等于去掉“就绪契约”，`depends_on` 无法等待，依赖失效。生产用 `healthcheck: test urlopen /api/health` + `start_period: 300s` 正是为了让依赖等待“真就绪”而非“进程已起”。

#### 改动并预测 实验 2：`client_max_body_size` 设为 `1m`（或过小）→ 预测上传 413

- **改什么**：在 `docker/nginx.conf`（或教学等价中）加入 `client_max_body_size 1m;`（nginx 默认即 `1m`），随后通过前端上传一个 `>1m` 的音频（如 `5m` 的 `wav`）到 `POST /api/upload`，若走纯静态直连则请求直达后端不受 nginx 限制，若为对比在反向代理形态下则经 nginx 转发。
- **预测**：经 nginx 转发的形态下，nginx 在请求体超过 `1m` 时直接返回 `413 Payload Too Large`（`413 Request Entity Too Large`），不转发到后端；浏览器 `fetch` 抛错，前端提示“上传失败 413”。纯静态直连下该指令不生效（请求不经 nginx），需改回由后端 `upload.py` 的文件大小校验返回 `413` 或 `400`；若把 `client_max_body_size` 改为 `100m` 则大文件可通过 nginx 层，后端再做二次校验。
- **解释**：`client_max_body_size` 是 nginx 的“请求体大小闸门”，与后端的应用层校验互补：网关层 413 发生在“进应用之前”，应用层 413/400 发生在“进处理器之后”。本项目纯静态下 API 不经 nginx，故该指令对 `/api/upload` 无效，这一区别正是“纯静态 vs 反代”在上传链路上的体现——调小该值仅影响反代形态，纯静态需靠后端校验。

#### 改动并预测 实验 3：`VITE_API_BASE_URL` 缺失或为空 → 预测 404 跨域直连失败

- **改什么**：把 `deploy-demo/docker-compose.yml` 中 `frontend.build.args.VITE_API_BASE_URL: "http://localhost:8000/api"` 删除或设为空字符串 `""`，重新 `docker compose up --build`，浏览器访问 `http://localhost` 并触发任意 API（如 `GET /tasks` 或 `POST /api/upload`）。
- **预测**：前端 `API_BASE` 回退为 `"/api"`（见 `client.ts: || '/api'`），浏览器发 `GET http://localhost/api/tasks`（同源相对路径），命中 nginx 的 `location /api/ { return 404; }`，响应 `404 Not Found`（非 CORS 失败）；`fetch` 抛 `detail: 404 Not Found`，前端列表为空且控制台可见 `404`；若改为正确值 `http://localhost:8000/api` 则请求为 `http://localhost:8000/api/tasks` 跨源直连，后端 `MTT_CORS_ORIGINS` 放行 `http://localhost` 时成功返回 `200`。
- **解释**：`VITE_API_BASE_URL` 是构建时注入的“前端到后端的地址契约”，缺失时前端退化为相对路径，而纯静态 nginx 故意对 `/api/` 返回 404（不代理），迫使问题显性暴露而非静默走错后端。修复必须重建前端镜像（`--build`），运行时 `docker run -e` 无法改写已编译的 `dist`。

#### 改动并预测 实验 4：删掉 `.dockerignore` 中的 `data/` → 预测构建上下文膨胀

- **改什么**：把 `deploy-demo/.dockerignore`（或根 `.dockerignore`）中的 `data/` 一行删除，`data/` 中放一个 `500 MB` 的占位文件（或已有模型缓存），随后 `docker build -f deploy-demo/Dockerfile.backend .` 观察 `Sending build context to Docker daemon` 的大小与耗时。
- **预测**：上下文从数 MB 膨胀至 `500 MB+`，`docker build` 的首步 `Sending context` 明显变慢，且 `COPY pyproject.toml` 等层的缓存命中率下降（因上下文 hash 改变）；若同时 `COPY . .`（而非选择性 `COPY pyproject.toml + m2t/`）则镜像内多出 `data/` 内容，镜像体积激增且可能泄露本地数据库/密钥。
- **解释**：`.dockerignore` 是“构建上下文的防火墙”，与 `Dockerfile` 的选择性 `COPY` 双保险：前者止于“上传到 daemon 前”，后者止于“拷入镜像时”。二者缺一都会让大文件进入镜像或拖慢构建，生产用 `.dockerignore` 排除 `data/`/`frontend/node_modules/`/`models/` 正是为了“上下文小、镜像小、缓存稳”。

## 习题

> 参考答案与测试在 `answers/week14/`，运行 `.venv/bin/pytest answers/week14/ -q` 验证。题目均为 hermetic（不依赖 Docker 守护进程、网络或真实模型），仅解析 YAML、构造 URL 与纯函数校验。

1. **Compose 解析**：实现 `parse_compose(text: str) -> dict`，用 `yaml.safe_load` 解析 `docker-compose.yml` 文本，返回字典。测试断言 `parse_compose` 对 `deploy-demo/docker-compose.yml` 的解析结果含 `services.backend` 与 `services.frontend`。
2. **API_BASE 回退**：实现 `resolve_api_base(env: dict) -> str`，当 `env["VITE_API_BASE_URL"]` 非空时返回其去尾斜杠后的值，否则返回 `"/api"`。测试断言缺失/空串/空白均回退 `"/api"`，`http://localhost:8000/api/` 去尾后为 `http://localhost:8000/api`。
3. **URL 拼接**：实现 `build_api_url(base: str, path: str) -> str`，处理 `base` 为绝对 URL 或 `"/api"` 相对路径时的拼接，且 `base` 尾斜杠与 `path` 首斜杠不重复。测试断言 `build_api_url("http://localhost:8000/api", "/health") == "http://localhost:8000/api/health"` 与 `build_api_url("/api", "health") == "/api/health"`。
4. **纯静态判定**：实现 `is_pure_static_nginx(conf: str) -> bool`，当 `conf` 含 `try_files` 且含 `location /api/` 的 `return 404` 且不含 `proxy_pass` 时返回 `True`。测试用 MeetingToText 的 `docker/nginx.conf` 文本断言为 `True`，含 `proxy_pass http://backend:8000` 的反代文本断言为 `False`。
5. **Healthcheck 校验**：实现 `validate_compose(data: dict) -> list[str]`，当 `services.frontend.depends_on.backend.condition == "service_healthy"` 但 `services.backend` 无 `healthcheck` 时返回含 `"healthcheck"` 的错误列表，否则返回空。测试断言缺 `healthcheck` 时错误非空，完整时为空。
6. *（附加）* **`client_max_body_size` 解析**：实现 `parse_client_max_body_size(conf: str) -> int | None`，解析 `client_max_body_size 10m;` 这类指令为字节数（支持 `k/m/g`），无指令时返回 `None`。测试断言 `1m -> 1048576`、`100m -> 104857600`、`"off"` 或缺失返回 `None`。

## 延伸挑战

1. 为 `deploy-demo/docker-compose.yml` 增加 `volumes: ["./data:/data"]` 持久化卷，对比 `docker compose down` 后 `data/` 是否保留，体会“卷的生命周期独立于容器”。
2. 在 `deploy-demo/ci.yml` 中增加 `docker compose -f deploy-demo/docker-compose.yml config -q` 步骤，故意把 `depends_on.condition` 拼错为 `service_healthy_typo`，观察 CI 的阻断效果（本地 `config -q` 同理）。
3. 把 `frontend` 的 `VITE_API_BASE_URL` 改为 `http://backend:8000/api`（容器网络内的服务名），预测浏览器访问 `http://localhost` 时 `fetch` 是否成功（提示：`backend` 仅在 Compose 网络内可解析，浏览器不在该网络内）。

> 本章内容原创，Docker 多阶段/层缓存/Compose 健康依赖/CORS 跨源直连与纯静态托管概念对应 MeetingToText 的 `docker/{Dockerfile.backend,Dockerfile.frontend,nginx.conf,docker-compose.yml}` 与 `.github/workflows/ci.yml`，`VITE_API_BASE_URL` 构建时注入与 `client.ts` 的回退逻辑为教学原创示例。

