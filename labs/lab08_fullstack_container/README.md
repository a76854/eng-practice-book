# 实验八 里程碑 B 与 C 全栈容器化与答辩

> 对应理论 [第11章 部署、容器化与持续集成](../../book/part4_现代工程进阶与交付/chapter11_部署容器化与持续集成/index.md) · 4 学时 · 任务说明与验收标准同 `book/part5_实验指导书/experiment08_里程碑BC_全栈容器化与答辩/index.md`

## 实验目标

- 编写层缓存友好的 Dockerfile，理解 COPY 顺序与选择性 COPY 对构建速度与镜像体积的影响。
- 用 `docker-compose.yml` 声明前后端联动，掌握健康检查与 `depends_on` 的启动依赖。
- 在无 Docker 时用 YAML 解析完成交付预演，有 Docker 时用 `docker compose config -q` 做编排校验。
- 完成从构建镜像到编排联调到答辩陈述的交付闭环，能解释容器如何固化环境与可回滚。

## 任务步骤

### 步骤 1 阅读理论

通读第11章 11.1 至 11.4 节，关注部署演进、层缓存、多阶段与 Compose 编排，并对照 `deploy-demo/` 的教学资产。

### 步骤 2 读懂骨架

进入 `starter/`，阅读 `Dockerfile` 与 `docker-compose.yml` 的声明关系，用 `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"` 校验 YAML。

### 步骤 3 Dockerfile

补齐基座、系统层、先拷 `pyproject.toml` 再拷 `m2t/` 的顺序、`pip install --no-cache-dir` 与 `EXPOSE` / `CMD`。

### 步骤 4 Compose 编排

声明 `backend` 与 `frontend` 两服务，`backend` 带健康检查，`frontend` 依赖 `service_healthy`，端口与环境变量对齐。

### 步骤 5 部署与验收

按 `starter/README.md` 的部署步骤复述云上映射，以健康检查为锚点做功能验收，保证前后端时序。

### 步骤 6 答辩与自检

整理五节主线的陈述，准备镜像分层与依赖的提问，确认 YAML 可解析、`git status` 干净与 `myst build` 可构建。

## 验收标准

- [ ] Dockerfile 体现层缓存友好与选择性 COPY，Compose 含健康检查与 `depends_on`，均可被文本解析验证。
- [ ] YAML 在无 Docker 时用 `yaml.safe_load` 通过，有 Docker 时用 `docker compose config -q` 通过。
- [ ] 能解释多阶段对体积的影响，能说清 `EXPOSE` 与 `ports` 的分工，能回答跨域联调。
- [ ] 答辩覆盖五节主线，陈述与配置可对照，仓库干净且可构建。

## 提交要求

提交 `starter/Dockerfile`、`docker-compose.yml`、`README.md`，写清校验、部署复述与答辩要点。以演示与讨论验收，不要求真实构建与真实云密钥。

## 预估用时

4 学时。

## 起手代码

见 `starter/` 目录。先用 `python -c "import yaml; yaml.safe_load(open('starter/docker-compose.yml'))"` 做 YAML 预演，再对照 `deploy-demo/Dockerfile.backend` 与 `deploy-demo/docker-compose.yml` 理解最小两服务的意图。
