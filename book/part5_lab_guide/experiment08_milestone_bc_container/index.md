# 实验八 里程碑 B 与 C 全栈容器化与答辩

本实验对应理论 [第11章 部署、容器化与持续集成](../../part4_advanced_engineering/chapter11_deploy_cicd/index.md)。建议先通读第11章 11.1 至 11.4 节的部署演进、Dockerfile 最佳实践、Compose 编排与 CI 流水线，再阅读 `deploy-demo/Dockerfile.backend` 与 `deploy-demo/docker-compose.yml` 的教学样例，最后动手。你会在本实验中把全栈应用容器化，用 Compose 在本地完成联调预演，并整理答辩材料，完成从可运行到可交付的收口。

## 实验目标

- 能编写层缓存友好的 Dockerfile，解释 COPY 顺序与多阶段对镜像体积与构建速度的影响，并读懂 `deploy-demo/Dockerfile.backend` 的选择性 COPY。
- 能用 `docker-compose.yml` 描述前后端与持久化的联动，理解 `depends_on`、健康检查与端口映射如何表达启动依赖。
- 能在不依赖真实构建的前提下，用纯文本与 YAML 解析完成交付预演，解释为何该方法能在无 Docker 守护进程时仍可验证拓扑与配置。
- 能把 MeetingToText 的“构建镜像、编排联调、自动化门禁”串为最小交付闭环，并说清环境固化与可回滚的价值。
- 能整理答辩陈述，主线覆盖需求切片、架构选型、外部集成、健壮性与交付，能回答镜像分层与 Compose 依赖等常见提问。

## 任务步骤

### 步骤 1 阅读理论与现状

1. 阅读 [第11章 11.1 部署演进史](../../part4_advanced_engineering/chapter11_deploy_cicd/11.1_deployment_evolution.md) 至 [11.2 Dockerfile 最佳实践](../../part4_advanced_engineering/chapter11_deploy_cicd/11.2_dockerfile_best_practices.md)，理解镜像分层、层缓存键与选择性 COPY 的权衡。
2. 阅读 [第11章 11.3 Docker Compose 编排](../../part4_advanced_engineering/chapter11_deploy_cicd/11.3_docker_compose_orchestration.md) 与 [11.4 CI/CD 流水线](../../part4_advanced_engineering/chapter11_deploy_cicd/11.4_cicd_pipeline.md)，重点关注声明式 YAML 如何表达服务拓扑，以及 GitHub Actions 的工作流、作业与步骤模型。
3. 打开 `deploy-demo/Dockerfile.backend` 与 `deploy-demo/docker-compose.yml`，逐行对照第11章的层缓存与编排讲解，明确本实验的起点是该教学资产的“最小两服务”形态。

> 跨平台提示：Dockerfile 与 Compose 的路径统一为 Linux 风格 `/app`、`/data`，在 Windows 宿主机上构建时同样生成 Linux 镜像。所有校验均可用纯文本解析完成，无需启动 Docker 守护进程，详见 `starter/README.md` 的本地预演命令。

### 步骤 2 读懂起手骨架

1. 进入 `labs/lab08_fullstack_container/starter`，阅读 `README.md`、`Dockerfile` 与 `docker-compose.yml`，梳理“后端镜像、前端静态托管、健康检查、启动依赖”四层的声明关系。
2. 运行 `python -c "import yaml; yaml.safe_load(open('docker-compose.yml', encoding='utf-8')); print('compose yaml ok')"` 确认 YAML 可解析，运行 `python -m py_compile` 思路的 Dockerfile 逐行检查，理解每条指令的缓存语义。
3. 对照 `deploy-demo/ci.yml` 的校验与测试链路，明确 CI 如何把 ruff、mypy、pytest 与 `docker compose config -q` 串为门禁。

### 步骤 3 编写 Dockerfile

1. 以 `starter/Dockerfile` 为起点，完善后端的容器化声明：
   - 基座选 `python:3.12-slim`，工作目录 `/app`，声明 `EXPOSE 8000` 与 `ENV MTT_DATA_DIR=/data`。
   - 系统层先装 `libsndfile1` 等最小依赖，并清理 `apt` 缓存，保持层缓存友好。
   - 先 `COPY pyproject.toml README.md` 再 `RUN pip install`，后 `COPY m2t/ ./m2t/`，避免业务代码的频繁变动使依赖层失效。
   - 安装用 `pip install --no-cache-dir -e .`，不保留 wheel 缓存，产物仅含 `m2t` 与运行时依赖。
2. 保持选择性 COPY，不 `COPY . .`，避免把 `labs/`、`book/`、`.venv`、模型权重误入镜像，产物可通过文本解析验证。
3. 启动命令用 `CMD ["python", "-m", "m2t.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]` 或等价的 FastAPI 启动，保持与 `deploy-demo/Dockerfile.backend` 的意图对齐。

### 步骤 4 编排 docker compose

1. 在 `starter/docker-compose.yml` 中声明两服务：
   - `backend` 用 `build.context: .` 与 `dockerfile: Dockerfile` 构建，挂 `MTT_DATA_DIR`，声明健康检查 `python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"`，启动依赖由该检查表达。
   - `frontend` 用 `nginx:alpine` 托管静态产物，`ports: ["80:80"]`，`depends_on.backend.condition: service_healthy`，保证前端在后端就绪后才被认为可用。
2. 保持 compose 的 hermetic 风格，`restart: "no"` 让本地预演不自动重试，便于观察健康检查的时序，云上可按需改为 `unless-stopped`。
3. 用 `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"` 与 `docker compose -f docker-compose.yml config -q` 的思路做配置校验，前者在无 Docker 时仍可验证，后者在有 Docker 时做完整编排检查。

### 步骤 5 部署到云或 VM 与功能验收

1. 按 `starter/README.md` 的部署步骤，把 Compose 拓扑复述为云上的发布方式，核心是“后端镜像加前端静态”的两件套，不依赖真实云密钥也能在文档层面说清映射。
2. 健康检查为验收锚点，`GET /api/health` 返回 `{"status": "ok"}` 视为后端就绪，`GET /` 的静态页可访问视为前端就绪，二者的 `depends_on` 保证时序，验收时逐项打勾。
3. 在答辩前做一致性检查，后端是否持久化到 `/data`，是否把日志与错误脱敏，前端是否由 Nginx 以 `80` 对外，配置是否可通过 `yaml.safe_load` 的预演捕获。

### 步骤 6 整理答辩与自检清理

1. 按 `starter/README.md` 的答辩要点整理陈述，主线覆盖“需求切片、架构选型、外部集成与流式、健壮性与脱敏、容器化与交付”，每节 2 到 3 分钟，配合演示与配置文本佐证。
2. 准备提问清单，至少覆盖“为何先 COPY pyproject.toml 再 COPY m2t”“depends_on 与健康检查的区别”“COPY 不当如何导致缓存失效”“前端与后端如何跨域联调”。
3. 用 `git status` 确认无 `.venv`、`__pycache__`、`node_modules/`、`dist/`、镜像 tar 与云密钥等不应提交的内容，确认 `python -c "import yaml; yaml.safe_load(open('starter/docker-compose.yml'))"` 通过，`myst build --html --strict` 可构建，准备演示与答辩。

## 验收标准

逐条自查，全部勾选即视为完成：

- [ ] `starter/Dockerfile` 以 `python:3.12-slim` 为基座，含 `WORKDIR`、系统依赖、`COPY` 与 `pip install --no-cache-dir`、环境变量与 `EXPOSE` / `CMD`，且体现层缓存友好的 COPY 顺序。
- [ ] `starter/Dockerfile` 为选择性 COPY，仅含 `pyproject.toml` / `README.md` 与 `m2t/`，不含 `labs/`、`book/`、`.venv`、权重等无关上下文。
- [ ] `starter/docker-compose.yml` 声明 `backend` 与 `frontend` 两服务，`backend` 含健康检查，`frontend` 含 `depends_on` 的 `service_healthy`，端口映射与环境变量可被 `yaml.safe_load` 解析。
- [ ] Compose 配置可在无 Docker 时用 `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"` 预演，在有 Docker 时用 `docker compose config -q` 通过。
- [ ] 能说清从物理机到容器再到编排的演进动因，能解释多阶段构建对体积与缓存的影响，能解释为何 `EXPOSE` 仅声明而由 `ports` 发布。
- [ ] 答辩陈述覆盖五节主线，能回答 Dockerfile 分层与 Compose 依赖的常见提问，演示与配置文本可对照。
- [ ] `yaml.safe_load` 通过，`git status` 干净，无镜像产物、密钥与权重等不应提交内容，`myst build --html --strict` 可构建。

## 提交要求

- 提交包含 `starter/Dockerfile`、`starter/docker-compose.yml`、`starter/README.md` 与顶层 `README.md` 的目录，`README.md` 需写清本地校验、部署步骤复述与答辩要点，保证助教按文档可在 5 分钟内完成预演与陈述预检。
- 不需要提交真实镜像、`.venv`、`__pycache__`、`node_modules/`、`dist/`、云配置文件或密钥，以文本与 YAML 声明作为交付物。
- 不要求真实构建与真实云部署，本地用 `yaml.safe_load` 的预演即视为配置验收，有 Docker 时可用 `docker compose config -q` 进一步验证。
- 以演示与讨论作为验收，能现场展示 Dockerfile 的层意图、Compose 的服务依赖与答辩陈述。

## 预估用时

4 学时。

建议分配：步骤 1 至 2 约 50 分钟，步骤 3 至 4 约 70 分钟，步骤 5 至 6 约 120 分钟。剩余时间用于自检与课堂答辩预演。
