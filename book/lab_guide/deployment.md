---
numbering: false
---

# 实验六 容器化部署与持续交付

本实验对应理论 [第 13 章 部署、容器化与持续集成](../advanced_engineering/deploy_cicd/index.md)。建议先通读 [部署演进](../advanced_engineering/deploy_cicd/deployment_evolution.md)、[Dockerfile 最佳实践](../advanced_engineering/deploy_cicd/dockerfile_best_practices.md)、[Compose 编排](../advanced_engineering/deploy_cicd/docker_compose_orchestration.md) 与 [CI/CD 流水线](../advanced_engineering/deploy_cicd/cicd_pipeline.md)，再动手。

本实验**基于实验三至五的成果**，把后端与前端打包成可一键启动、可持续集成的交付形态。你要写的是声明式配置，不提供起始代码。

## 实验目标

通过完成容器化部署，你将：

1. **编写层缓存友好的 Dockerfile**：容器化后端，解释 COPY 顺序与多阶段构建对构建速度的影响。
2. **用 Nginx 托管前端**：把前端构建产物交给 Nginx 静态托管，并把接口反向代理到后端。
3. **用 Compose 表达拓扑**：声明后端与 Nginx 两个服务，用健康检查表达启动依赖。
4. **建持续集成流水线**：用 GitHub Actions 跑通代码检查、编排校验与镜像构建。
5. **给出发布与回滚方案**：用不可变标签发布，用提交号回滚，回滚是改配置而不是改服务器。

## 背景故事

应用做完了：后端能搜索、能收藏、能摘要，前端能展示、能收藏、能登录。但现在的交付方式是“照着 README 一条条敲命令”，换一台机器就要重来一遍，出了问题也不知道怎么退回上一个版本。

团队要求你把交付形态固化下来：一条命令起来，一套配置描述清楚谁依赖谁，一个流水线自动检查，一个标签对应一个可回滚的版本。这就是本次实验要交付的东西。

## 预备知识

**交付形态**

- 两个服务：`backend`（FastAPI 应用）与 `nginx`（前端静态托管与接口反向代理）。
- 对外只暴露 Nginx 的 `80` 端口；后端 `8000` 只在容器网络内可见。
- 健康检查接口为 `GET /api/health`，返回 `{"status": "ok"}` 视为就绪。

**路径与端口约定**

| 位置 | 约定 |
|------|------|
| 后端工作目录 | `/app` |
| 后端数据目录 | `/data` |
| 后端端口 | `8000`（仅容器内） |
| Nginx 端口 | `80`（对外） |
| 前端产物 | Nginx 静态目录下的网站根 |
| 接口前缀 | `/api` 反向代理到后端 |

**目录约定**

```
Dockerfile                 # 后端镜像
nginx.conf                 # Nginx 站点配置
docker-compose.yml         # 两服务拓扑
.github/workflows/ci.yml   # 持续集成流水线
```

**环境变量**

| 变量 | 用途 |
|------|------|
| `DOCSEARCH_DATA_DIR` | 后端数据目录，容器内为 `/data` |
| `LLM_API_KEY` | 大模型密钥，缺失时摘要走降级 |
| `REDIS_URL` | 缓存地址，缺失时跳过缓存 |

**环境约定**

- 基础镜像用 `python:3.12-slim`，路径统一写 `/`。
- 依赖安装以书仓的 `uv` 口径为准，镜像内按 `pyproject.toml` 与锁文件安装。
- 本地若没有 Docker 守护进程，也要求配置能被纯文本与 YAML 解析校验。

---

# 任务一：容器化后端

## 任务目标

写一个层缓存友好的 Dockerfile，把后端打成镜像。

## 需求

1. 基础镜像用 `python:3.12-slim`，工作目录 `/app`，声明 `EXPOSE 8000` 与数据目录环境变量。
2. 先拷依赖清单（`pyproject.toml` 与锁文件）再安装依赖，最后才拷业务代码，让代码的频繁改动只使最后一层失效。
3. 用选择性的 COPY，不使用 `COPY . .`，避免把无关目录与数据带进镜像。
4. 启动命令用 `uvicorn` 启动后端应用，监听容器网络的 `8000`。
5. 若使用多阶段构建，说明构建阶段与运行阶段各装了什么、体积如何变化。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 分层合理 | 依赖层在前、代码层在后，改代码只脏最后一层 |
| 选择性 COPY | 只拷依赖清单与源码，不含无关目录与数据 |
| 可构建 | 有 Docker 时能构建成功；无 Docker 时配置可被文本解析校验 |
| 启动正确 | 容器启动后 `GET /api/health` 返回就绪 |

## 提交要求

```bash
git switch -c exp/01-backend-image
git add Dockerfile .dockerignore
git commit -m "build: add cache-friendly backend Dockerfile"
git push -u origin exp/01-backend-image
```

---

# 任务二：Nginx 托管前端与反向代理

## 任务目标

用 Nginx 托管前端构建产物，并把接口请求代理到后端。

## 需求

1. 用 Nginx 提供前端构建产物的静态托管，访问根路径返回前端页面。
2. 把 `/api` 前缀的请求反向代理到后端服务，转发必要的请求头。
3. 前端为单页应用时，对未知路径回退到入口页，避免刷新 404。
4. 静态资源设置合理缓存，接口响应不做缓存。

## 参考配置

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 前端可访问 | 访问根路径返回前端页面 |
| 代理生效 | `/api` 请求被转发到后端并能拿到结果 |
| 刷新不 404 | 单页应用未知路径回退到入口页 |
| 缓存区分 | 静态资源可缓存，接口响应不缓存 |

## 提交要求

```bash
git switch -c exp/02-nginx-frontend
git add nginx.conf
git commit -m "build: serve frontend and proxy api with nginx"
git push -u origin exp/02-nginx-frontend
```

---

# 任务三：Compose 编排两服务

## 任务目标

用 Compose 声明后端与 Nginx 的拓扑、健康检查与启动依赖。

## 需求

1. 声明 `backend` 与 `nginx` 两个服务，后端由本次实验的 Dockerfile 构建。
2. 后端声明健康检查，探测 `GET /api/health`。
3. Nginx 用 `depends_on` 的 `condition: service_healthy` 表达“等后端就绪再启动”。
4. 只把 Nginx 的 `80` 端口映射到宿主机，后端端口不对外暴露。
5. 挂载后端的数据目录，保证重启后收藏数据仍在。

## 参考骨架

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      DOCSEARCH_DATA_DIR: /data
    volumes:
      - docdata:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]
      interval: 5s
      timeout: 3s
      retries: 5

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      backend:
        condition: service_healthy

volumes:
  docdata:
```

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 两服务齐全 | `backend` 与 `nginx` 均在配置中声明 |
| 依赖时序 | Nginx 以后端健康为启动条件 |
| 端口收敛 | 仅 Nginx 的 80 对外，后端端口不外露 |
| 数据持久 | 后端数据目录挂载，重启后数据仍在 |
| 配置可校验 | YAML 可解析；有 Docker 时 `docker compose config -q` 通过 |

## 提交要求

```bash
git switch -c exp/03-compose
git add docker-compose.yml
git commit -m "build: orchestrate backend and nginx with compose"
git push -u origin exp/03-compose
```

---

# 任务四：持续集成流水线

## 任务目标

用 GitHub Actions 把检查与构建自动化，让每次提交都过门禁。

## 需求

1. 在 `.github/workflows/ci.yml` 中定义流水线，触发条件覆盖推送与拉取请求。
2. 依次执行：安装依赖、`ruff check`、`mypy`、`pytest`。
3. 校验编排配置，例如运行 `docker compose config -q`。
4. 构建后端镜像，验证 Dockerfile 可用。
5. 任一步骤失败即视为流水线失败。

## 参考骨架

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: pip install uv
      - name: Sync dependencies
        run: uv sync --dev
      - name: Lint
        run: uv run ruff check src/
      - name: Type check
        run: uv run mypy src/
      - name: Test
        run: uv run pytest -q
      - name: Validate compose
        run: docker compose -f docker-compose.yml config -q
      - name: Build image
        run: docker build -t docsearch-backend:ci .
```

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 流水线存在 | `.github/workflows/ci.yml` 存在且触发条件正确 |
| 检查齐全 | Ruff、mypy、pytest 依次运行 |
| 编排校验 | 有 `docker compose config -q` 一步 |
| 镜像构建 | 有构建镜像的步骤 |
| 门禁有效 | 任一步失败流水线即为失败 |

## 提交要求

```bash
git switch -c exp/04-ci
git add .github/workflows/ci.yml
git commit -m "ci: add lint, test, compose validation and image build"
git push -u origin exp/04-ci
```

---

# 任务五：发布与回滚方案

## 任务目标

给出可操作的发布与回滚方案，让每次发布都对应一个不可变的版本。

## 需求

1. 镜像标签使用不可变标识（例如 `git` 提交号或语义化版本号），不用可变的 `latest` 作为发布依据。
2. 部署时按标签拉起对应版本，配置中记录当前使用的标签。
3. 回滚以“改回上一个标签再重新部署”为手段，不修改服务器本身。
4. 在本机演示一次回滚：发布一个新标签，再切回旧标签，确认服务恢复。
5. 在报告中说明：为什么不可变标签是可回滚的前提。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 标签不可变 | 发布标签唯一且不改写 |
| 回滚可操作 | 回滚步骤明确，能本机演示 |
| 配置驱动 | 版本由配置决定，不手改服务器 |
| 原理解释 | 能说清不可变标签与回滚的关系 |

## 提交要求

```bash
git switch -c exp/05-release-rollback
git add README.md
git commit -m "docs: document release tagging and rollback procedure"
git push -u origin exp/05-release-rollback
```

---

# 综合验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 后端镜像 | Dockerfile 分层合理、选择性 COPY、可构建 |
| 前端托管 | Nginx 完成静态托管与接口代理，刷新不 404 |
| 编排 | 两服务拓扑正确，健康检查与启动依赖生效 |
| 流水线 | 检查、编排校验、镜像构建均通过 |
| 回滚 | 有不可变标签与可演示的回滚步骤 |
| 可复现 | 助教按 README 能在约定时间内起服务并验证 |

---

# 实验报告要求

提交一份实验报告，包含：

1. **交付拓扑**：两个服务各自的职责与依赖关系。
2. **镜像分层**：Dockerfile 的分层顺序与理由，改代码时哪一层失效。
3. **Nginx 配置**：静态托管与反向代理的关键点。
4. **流水线**：各步骤做了什么，失败会怎样。
5. **发布与回滚**：标签策略与回滚步骤，本机演示结果。
6. **实验收获与反思**。

---

# 评分参考

| 部分 | 分值 | 说明 |
|------|------|------|
| 任务一：后端镜像 | 25% | 分层合理、选择性 COPY、可构建 |
| 任务二：Nginx | 20% | 托管与代理正确、刷新不 404 |
| 任务三：Compose | 20% | 两服务拓扑、健康检查、依赖时序 |
| 任务四：流水线 | 20% | 检查齐全、编排校验、镜像构建 |
| 任务五：发布与回滚 | 15% | 标签不可变、回滚可演示 |
